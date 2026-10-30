// Lonely Planner Edge Function `request-trip` · version 3.0.0-alpha.8.0 · F21
// CHANGE 2026-10-27 F21-FN-01: new file (no previous version). Public endpoint of the /request/ page (docs/F21_spec.md
//   §1.2–1.4, §3.1, §4): a visitor asks to open a trip, verifies the email with our own 6-digit code (D1), and the verified
//   request waits for the super-admin. No identity, no session: verify_jwt is OFF and the page calls it with the anon apikey.
//
// Actions (POST body {action, …}):
//   start  {lang, name, email, countries, month, travellers, note, turnstile_token}
//          → Turnstile siteverify → rpc request_start → code email → {ok:true, request_id, sent_at}
//   verify {request_id, code}  → rpc request_verify → {ok:true, request_id}
//   resend {request_id}        → new code → rpc request_resend → code email → {ok:true, request_id, sent_at}
// Refusals: {ok:false, code:<code>, error:<code>, …extra} with an HTTP status (see STATUS):
//   invalid_request {field} · turnstile_failed · rate_limited {retry_in?} · daily_limit · code_wrong {attempts_left} ·
//   code_expired · code_locked · request_unknown · email_failed · server_error · method_not_allowed
//   The client reads `code` (or `error`, same value) from the body whatever the status.
// C4: the answer of `start` never depends on the email's history (the database treats every address alike).
// Hashes: ip_hash = SHA-256 hex of the first X-Forwarded-For address; email_hash = SHA-256 hex of the normalized email;
//   code hash = SHA-256 hex of (request_id ‖ code) — the request id is created here (crypto.randomUUID) before the rpc.
// Logs: one JSON line per request {fn, v, action, status, code} — never the email, name, note, code, token or address.
// Imports the MIME + SMTP helpers from ../invite-manager/index.ts (no copy; the deploy must include that file).
// Secrets: GMAIL_USER, GMAIL_APP_PASSWORD (existing), TURNSTILE_SECRET (new), optional TURNSTILE_ALLOW_LOCALHOST=1.
//   Provided by Supabase: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or PT_SERVICE_KEY = an sb_secret_… key).
//
// Testability (same contract as create-trip): importable without starting a server (main.ts calls startServer()).
//   setDeps({rpc?, sendMail?, fetch?, now?, random?, uuid?, env?}) replaces the real calls; resetDeps() restores them.

import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2.45.4";
import { corsHeaders, gmailSender, htmlEscape, isValidEmail, type MailMessage, mailErr, normalizeEmail, sha256Hex } from "../invite-manager/index.ts";

export const FN_VERSION = "3.0.0-alpha.8.1"; // CHANGE 2026-10-30 F21-FN-03: Turnstile failure reason logged (was "3.0.0-alpha.8.0")
export const ACTIONS = ["start", "verify", "resend"] as const;
export const SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";
export const TURNSTILE_HOST = "orsela.github.io";

export type ErrorCode =
  | "invalid_request" | "turnstile_failed" | "rate_limited" | "daily_limit" | "code_wrong" | "code_expired" | "code_locked"
  | "request_unknown" | "email_failed" | "server_error" | "method_not_allowed";

const STATUS: Record<ErrorCode, number> = {
  invalid_request: 400, turnstile_failed: 403, rate_limited: 429, daily_limit: 429, code_wrong: 400, code_expired: 410,
  code_locked: 423, request_unknown: 404, email_failed: 502, server_error: 500, method_not_allowed: 405,
};
export function statusFor(code: string): number {
  return (STATUS as Record<string, number>)[code] ?? 500;
}

export interface RpcResult {
  data: unknown;
  error: { message: string; details?: string; code?: string } | null;
}
export interface Deps {
  rpc: (name: string, args: Record<string, unknown>) => Promise<RpcResult>;
  sendMail: (m: MailMessage) => Promise<void>;
  fetch: (url: string, init: RequestInit) => Promise<Response>;
  now: () => number;
  random: (n: number) => Uint8Array;
  uuid: () => string;
  env: (k: string) => string | undefined;
}

// -----------------------------------------------------------------------------------------------------
// helpers (exported for tests)
// -----------------------------------------------------------------------------------------------------
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** 6 random digits, uniform (rejection sampling on 32-bit values). */
export function makeCode(random: (n: number) => Uint8Array): string {
  for (;;) {
    const b = random(4);
    const v = ((b[0] << 24) >>> 0) + (b[1] << 16) + (b[2] << 8) + b[3];
    if (v < 4_294_000_000) return String(v % 1_000_000).padStart(6, "0");
  }
}

export function codeHash(requestId: string, code: string): Promise<string> {
  return sha256Hex(requestId.toLowerCase() + code);
}

/** SHA-256 hex of the first X-Forwarded-For address (null when absent). */
export async function ipHash(req: Request): Promise<string | null> {
  const raw = (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
  return raw ? await sha256Hex(raw) : null;
}
export function firstIp(req: Request): string {
  return (req.headers.get("x-forwarded-for") || "").split(",")[0].trim();
}

/** Calendar month "YYYY-MM" in Asia/Jerusalem, shifted by `add` months (C3). */
export function jerusalemMonth(nowMs: number, add = 0): string {
  const p = new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Jerusalem", year: "numeric", month: "2-digit" }).formatToParts(new Date(nowMs));
  const y = Number(p.find((x) => x.type === "year")!.value), m = Number(p.find((x) => x.type === "month")!.value) - 1 + add;
  const yy = y + Math.floor(m / 12), mm = ((m % 12) + 12) % 12 + 1;
  return `${yy}-${String(mm).padStart(2, "0")}`;
}

export interface StartPayload {
  lang: "he" | "en";
  name: string;
  email: string;
  countries: string[];
  month: string | null;
  travellers: number;
  note: string | null;
}

/** Same rules as the form and request_start (spec §1.2): returns the normalized payload or the first invalid field. */
export function validateStart(body: Record<string, unknown>, nowMs: number): { ok: true; p: StartPayload } | { ok: false; field: string } {
  const lang = body.lang;
  if (lang !== "he" && lang !== "en") return { ok: false, field: "lang" };
  if (typeof body.name !== "string") return { ok: false, field: "name" };
  const name = body.name.trim();
  // deno-lint-ignore no-control-regex
  if (name.length < 1 || name.length > 40 || /[\u0000-\u001f\u007f]/.test(name)) return { ok: false, field: "name" };
  const email = normalizeEmail(body.email);
  if (!isValidEmail(email)) return { ok: false, field: "email" };
  const c = body.countries;
  if (!Array.isArray(c) || c.length < 1 || c.length > 10) return { ok: false, field: "countries" };
  const countries: string[] = [];
  for (const x of c) {
    const v = typeof x === "string" ? x.trim().toUpperCase() : "";
    if (!/^[A-Z]{2}$/.test(v) || countries.includes(v)) return { ok: false, field: "countries" };
    countries.push(v);
  }
  let month: string | null = null;
  if (body.month !== null && body.month !== undefined) {
    if (typeof body.month !== "string" || !/^\d{4}-(0[1-9]|1[0-2])(-01)?$/.test(body.month)) return { ok: false, field: "month" };
    month = body.month.slice(0, 7);
    if (month < jerusalemMonth(nowMs, 0) || month > jerusalemMonth(nowMs, 17)) return { ok: false, field: "month" };
  }
  const t = body.travellers;
  if (typeof t !== "number" || !Number.isInteger(t) || t < 1 || t > 30) return { ok: false, field: "travellers" };
  let note: string | null = null;
  if (body.note !== null && body.note !== undefined) {
    if (typeof body.note !== "string") return { ok: false, field: "note" };
    note = body.note.trim() || null;
    if (note && note.length > 200) return { ok: false, field: "note" };
  }
  return { ok: true, p: { lang, name, email, countries, month, travellers: t, note } };
}

/** Cloudflare Turnstile server-side check: success and an allowed hostname. Never throws. */
export async function verifyTurnstile(
  fetchFn: Deps["fetch"], secret: string, token: string, ip: string, allowLocalhost: boolean,
): Promise<boolean> {
  if (!secret || !token || token.length > 2048) { // CHANGE 2026-10-30 F21-FN-03: reason logged (was a silent false)
    log({ action: "start", event: "turnstile_reject", codes: [!secret ? "no_secret" : !token ? "no_token" : "token_too_long"] });
    return false;
  }
  try {
    const form = new URLSearchParams({ secret, response: token });
    if (ip) form.set("remoteip", ip);
    const r = await fetchFn(SITEVERIFY_URL, { method: "POST", body: form });
    const d = await r.json() as { success?: boolean; hostname?: string; "error-codes"?: unknown };
    // CHANGE 2026-10-30 F21-FN-03: one diagnostic log line when the check fails — Cloudflare's error-codes and the
    //   hostname only (never the secret, the token or the address). Was: a silent false (live failure on 30/10).
    if (d?.success !== true) {
      log({ action: "start", event: "turnstile_reject", codes: Array.isArray(d?.["error-codes"]) ? d["error-codes"] : [] });
      return false;
    }
    const okHost = d.hostname === TURNSTILE_HOST || (allowLocalhost && d.hostname === "localhost");
    if (!okHost) log({ action: "start", event: "turnstile_host", host: String(d.hostname || "").slice(0, 80) });
    return okHost;
  } catch (e) {
    log({ action: "start", event: "turnstile_error", name: e instanceof Error ? e.name : "unknown" });
    return false;
  }
}

/** Code email (artboard F21_CodeEmail, spec §1.10): code in the subject, no link, HTML + text, dir per language. */
export const CODE_TEXT = {
  he: {
    subject: (c: string) => `${c} – קוד האימות לבקשה ב-Lonely Planner`,
    lead: "קוד האימות לבקשה שלך:",
    body: "חוזרים לדף הבקשה ומקלידים את הקוד. הוא תקף 10 דקות.",
    ignore: "לא ביקשת? אפשר להתעלם מהמייל.",
  },
  en: {
    subject: (c: string) => `${c} – your Lonely Planner verification code`,
    lead: "Your verification code:",
    body: "Go back to the request page and enter the code. It is valid for 10 minutes.",
    ignore: "Didn't ask for this? You can ignore this email.",
  },
} as const;
export function renderCodeEmail(p: { to: string; code: string; lang: string }): MailMessage {
  const l = p.lang === "en" ? "en" : "he";
  const t = CODE_TEXT[l];
  const dir = l === "he" ? "rtl" : "ltr";
  const subject = t.subject(p.code);
  const text = ["Lonely Planner", "", t.lead, p.code, "", t.body, t.ignore].join("\n");
  const html = `<!doctype html><html lang="${l}" dir="${dir}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${htmlEscape(subject)}</title></head>` +
    `<body dir="${dir}" style="margin:0;padding:24px 12px;background:#f7f6f1;color:#17211b;font-family:Arial,'Segoe UI',sans-serif">` +
    `<div dir="${dir}" style="max-width:420px;margin:0 auto;background:#ffffff;border:1px solid #e4e6df;border-radius:18px;padding:24px 18px;text-align:center">` +
    `<div style="font-size:18px;font-weight:900;color:#0f6b4f">Lonely Planner</div>` +
    `<p style="margin:18px 0 8px;font-size:15px;color:#3a443d">${htmlEscape(t.lead)}</p>` +
    `<div dir="ltr" style="display:inline-block;font-family:Menlo,Consolas,monospace;font-size:32px;font-weight:800;letter-spacing:6px;background:#f7f6f1;border:1px dashed #d6d9cf;border-radius:12px;padding:10px 18px">${htmlEscape(p.code)}</div>` +
    `<p style="margin:18px 0 0;font-size:13.5px;line-height:1.6;color:#5f6861">${htmlEscape(t.body)}<br>${htmlEscape(t.ignore)}</p>` +
    `</div></body></html>`;
  return { to: p.to, subject, text, html };
}

/** mailErr() of invite-manager (addresses masked) + any 6-digit run masked, so a code can never reach the logs. */
function safeMailErr(e: unknown): Record<string, unknown> {
  const m = mailErr(e);
  return { ...m, message: String(m.message).replace(/\d{6}/g, "<n>") };
}

class HttpError extends Error {
  constructor(public code: ErrorCode, public extra: Record<string, unknown> = {}) {
    super(code);
  }
}

// -----------------------------------------------------------------------------------------------------
// dependencies (production defaults are lazy)
// -----------------------------------------------------------------------------------------------------
let serviceClient: SupabaseClient | null = null;
function envGet(k: string): string | undefined {
  try {
    return Deno.env.get(k);
  } catch {
    return undefined;
  }
}
function db(): SupabaseClient {
  if (!serviceClient) {
    const e = (k: string) => envGet(k) || "";
    serviceClient = createClient(e("SUPABASE_URL"), e("PT_SERVICE_KEY") || e("SUPABASE_SERVICE_ROLE_KEY"), {
      auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
    });
  }
  return serviceClient;
}
let mailer: ((m: MailMessage) => Promise<void>) | null = null;
const DEFAULT_DEPS: Deps = {
  async rpc(name, args) {
    const { data, error } = await db().rpc(name, args);
    return { data, error: error ? { message: error.message, details: error.details, code: error.code } : null };
  },
  sendMail(m) {
    if (!mailer) mailer = gmailSender(envGet("GMAIL_USER") || "", envGet("GMAIL_APP_PASSWORD") || "");
    return mailer(m);
  },
  fetch: (url, init) => fetch(url, init),
  now: () => Date.now(),
  random: (n) => crypto.getRandomValues(new Uint8Array(n)),
  uuid: () => crypto.randomUUID(),
  env: envGet,
};
let deps: Deps = { ...DEFAULT_DEPS };
export function setDeps(d: Partial<Deps>): void {
  deps = { ...deps, ...Object.fromEntries(Object.entries(d).filter(([, v]) => typeof v === "function")) } as Deps;
}
export function resetDeps(): void {
  deps = { ...DEFAULT_DEPS };
}

function log(fields: Record<string, unknown>): void {
  console.log(JSON.stringify({ fn: "request-trip", v: FN_VERSION, ...fields }));
}

// -----------------------------------------------------------------------------------------------------
// handler
// -----------------------------------------------------------------------------------------------------
function json(origin: string | null, status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      ...corsHeaders(origin), "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
      "X-Function-Version": FN_VERSION,
    },
  });
}

function asObject(v: unknown): Record<string, unknown> | null {
  if (typeof v === "string") {
    try {
      v = JSON.parse(v);
    } catch {
      return null;
    }
  }
  return v && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : null;
}

/** rpc → object; a returned {"error":code} becomes an HttpError with its extra fields; a database error → server_error. */
async function call(name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const r = await deps.rpc(name, args);
  if (r.error) throw new HttpError("server_error");
  const d = asObject(r.data);
  if (!d) throw new HttpError("server_error");
  if (typeof d.error === "string") {
    const { error, ...extra } = d;
    const known = (STATUS as Record<string, number>)[error as string] !== undefined;
    throw new HttpError(known ? error as ErrorCode : "server_error", known ? extra : {});
  }
  return d;
}

function requestId(body: Record<string, unknown>): string {
  const id = typeof body.request_id === "string" ? body.request_id.trim().toLowerCase() : "";
  if (!UUID_RE.test(id)) throw new HttpError("invalid_request", { field: "request_id" });
  return id;
}

async function actStart(req: Request, body: Record<string, unknown>) {
  const v = validateStart(body, deps.now());
  if (!v.ok) throw new HttpError("invalid_request", { field: v.field });
  const token = typeof body.turnstile_token === "string" ? body.turnstile_token : "";
  const passed = await verifyTurnstile(deps.fetch, deps.env("TURNSTILE_SECRET") || "", token, firstIp(req),
    deps.env("TURNSTILE_ALLOW_LOCALHOST") === "1");
  if (!passed) throw new HttpError("turnstile_failed");
  const id = deps.uuid().toLowerCase();
  const code = makeCode(deps.random);
  const d = await call("request_start", {
    p_request: id, p_payload: v.p, p_email_hash: await sha256Hex(v.p.email), p_ip: await ipHash(req),
    p_code_hash: await codeHash(id, code),
  });
  try {
    await deps.sendMail(renderCodeEmail({ to: v.p.email, code, lang: v.p.lang }));
  } catch (e) {
    log({ action: "start", event: "email_error", ...safeMailErr(e) });
    try {
      await call("request_mail_failed", { p_request: id, p_action: "start" });
    } catch { /* logged by the outer handler as server_error is not wanted here: the answer stays email_failed */ }
    throw new HttpError("email_failed");
  }
  return { ok: true, request_id: id, sent_at: d.sent_at ?? new Date(deps.now()).toISOString() };
}

async function actVerify(req: Request, body: Record<string, unknown>) {
  const id = requestId(body);
  const code = typeof body.code === "string" ? body.code.replace(/\s+/g, "") : "";
  if (!/^\d{6}$/.test(code)) throw new HttpError("invalid_request", { field: "code" });
  await call("request_verify", { p_request: id, p_code_hash: await codeHash(id, code), p_ip: await ipHash(req) });
  return { ok: true, request_id: id };
}

async function actResend(body: Record<string, unknown>) {
  const id = requestId(body);
  const code = makeCode(deps.random);
  const d = await call("request_resend", { p_request: id, p_code_hash: await codeHash(id, code) });
  const email = typeof d.email === "string" ? d.email : "";
  if (!email) throw new HttpError("server_error");
  try {
    await deps.sendMail(renderCodeEmail({ to: email, code, lang: String(d.lang || "he") }));
  } catch (e) {
    log({ action: "resend", event: "email_error", ...safeMailErr(e) });
    try {
      await call("request_mail_failed", { p_request: id, p_action: "resend" });
    } catch { /* answer stays email_failed */ }
    throw new HttpError("email_failed");
  }
  return { ok: true, request_id: id, sent_at: d.sent_at ?? new Date(deps.now()).toISOString() };
}

export async function handler(req: Request): Promise<Response> {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(origin) });
  let action = "";
  try {
    if (req.method !== "POST") throw new HttpError("method_not_allowed");
    let body: Record<string, unknown>;
    try {
      body = asObject(await req.json()) ?? {};
    } catch {
      body = {};
    }
    action = typeof body.action === "string" && (ACTIONS as readonly string[]).includes(body.action) ? body.action : "";
    if (!action) throw new HttpError("invalid_request", { field: "action" });
    const out = action === "start" ? await actStart(req, body) : action === "verify" ? await actVerify(req, body) : await actResend(body);
    log({ action, status: 200 });
    return json(origin, 200, out);
  } catch (e) {
    const he = e instanceof HttpError ? e : new HttpError("server_error");
    if (!(e instanceof HttpError)) log({ action, event: "error", name: e instanceof Error ? e.name : "unknown" });
    const status = statusFor(he.code);
    log({ action, status, code: he.code });
    return json(origin, status, { ok: false, code: he.code, error: he.code, ...he.extra });
  }
}

export function startServer(): void {
  Deno.serve(handler);
}

if (import.meta.main) startServer();
