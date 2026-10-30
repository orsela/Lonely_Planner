// Plan_Travel Edge Function `create-trip` · version 3.0.0-alpha.8.0 · F21 (first version: F04)
// CHANGE 2026-10-27 F21-FN-20: what changed from 3.0.0-alpha.4.1 (docs/F21_spec.md §3.3): `lookup` passes `prefill`
//   {name, countries, month, lang} through from find_invite_for_email when the invite came from an F21 request (shape-checked
//   by cleanPrefill; the key is absent otherwise, so an F03 invite's lookup answer is unchanged). `create` unchanged.
// CHANGE 2026-10-12 F04-FN-01: new file (no previous version). An invited manager whose email is verified looks up
//   their invite and creates the trip (docs/F04_spec.md §3.1). Runs with the service role; verify_jwt is OFF for this
//   function — it verifies the caller's JWT itself with auth.getUser(jwt) and requires a confirmed email.
//
// Actions (POST body {action, …}, every action needs `Authorization: Bearer <user JWT>`):
//   lookup → rpc find_invite_for_email(user.email) → {found, draft_name, inviter_name, expires_at, prefill?}  (no ids, no email)
//   create → rpc create_trip_from_invite(user.id, user.email, payload) → {trip_id, join_code, join_url, created}
// Errors: {error:<code>, field?}: 401 unauthorized · 403 email_not_verified · 400 invalid_request / invalid_payload
//   {field} / too_many_currencies · 409 invite_invalid · 429 rate_limited · 405 method_not_allowed · 500 server_error.
//
// Testability (QA contract): this module is importable without starting a server (main.ts calls startServer()).
//   setDeps({getUser?, rpc?, now?}) replaces the real Supabase calls; resetDeps() restores them and clears the
//   rate limiter. handler(req) is the request handler used by startServer().
// Secrets: optional JOIN_URL (default https://orsela.github.io/Lonely_Planner/join/). Provided by Supabase: SUPABASE_URL,
//   SUPABASE_SERVICE_ROLE_KEY (or PT_SERVICE_KEY = an sb_secret_… key, preferred when present).
// Logs: one JSON line per request with action, status and error code only — never the JWT, email, payload or names.

import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2.45.4";

export const FN_VERSION = "3.0.0-alpha.8.0"; // CHANGE 2026-10-27 F21-FN-20: lookup passes prefill (was "3.0.0-alpha.4.1"); // CHANGE 2026-10-12 F04-NAME-02: default join URL → /Lonely_Planner/join/ (was "3.0.0-alpha.4.0")
export const DEFAULT_JOIN_URL = "https://orsela.github.io/Lonely_Planner/join/"; // CHANGE 2026-10-12 F04-NAME-02: was /Plan_Travel/join/ (repo renamed)
export const RATE_WINDOW_MS = 10 * 60 * 1000;
export const RATE_MAX: Record<string, number> = { create: 10, lookup: 30 };

export type ErrorCode =
  | "unauthorized" | "email_not_verified" | "invalid_request" | "invalid_payload" | "too_many_currencies"
  | "invite_invalid" | "rate_limited" | "method_not_allowed" | "server_error";

export interface AuthUser {
  id: string;
  email?: string | null;
  email_confirmed_at?: string | null;
  is_anonymous?: boolean;
}
export interface RpcResult {
  data: unknown;
  error: { message: string; details?: string; code?: string } | null;
}
export interface Deps {
  getUser: (jwt: string) => Promise<AuthUser | null>;
  rpc: (name: string, args: Record<string, unknown>) => Promise<RpcResult>;
  now: () => number;
}

// -----------------------------------------------------------------------------------------------------
// helpers (exported for tests)
// -----------------------------------------------------------------------------------------------------
export function isAllowedOrigin(origin: string | null): boolean {
  if (!origin) return false;
  return origin === "https://orsela.github.io" || /^http:\/\/localhost(:\d{1,5})?$/.test(origin);
}

/** Identical to invite-manager's CORS headers. */
export function corsHeaders(origin: string | null): Record<string, string> {
  const h: Record<string, string> = { "Vary": "Origin" };
  if (isAllowedOrigin(origin)) {
    h["Access-Control-Allow-Origin"] = origin as string;
    h["Access-Control-Allow-Methods"] = "POST, OPTIONS";
    h["Access-Control-Allow-Headers"] = "authorization, x-client-info, apikey, content-type";
    h["Access-Control-Max-Age"] = "600";
  }
  return h;
}

/** JOIN_URL secret → base. Must parse as a URL, start with https://, have a host and end with '/'; else the default. */
export function resolveJoinBase(v: string | undefined | null): { url: string; fallback: boolean } {
  const s = typeof v === "string" ? v.trim() : "";
  if (!s) return { url: DEFAULT_JOIN_URL, fallback: false };
  try {
    const u = new URL(s);
    if (s.startsWith("https://") && u.protocol === "https:" && u.host && s.endsWith("/") && !u.search && !u.hash) {
      return { url: s, fallback: false };
    }
  } catch { /* fall through */ }
  return { url: DEFAULT_JOIN_URL, fallback: true };
}

export function joinUrl(base: string, code: string): string {
  return `${base}#code=${code}`;
}

/** Sliding-window in-memory limiter per user id + action. */
export class RateLimiter {
  private hits = new Map<string, number[]>();
  hit(key: string, max: number, now: number): boolean {
    const arr = (this.hits.get(key) || []).filter((t) => now - t < RATE_WINDOW_MS);
    if (arr.length >= max) {
      this.hits.set(key, arr);
      return false;
    }
    arr.push(now);
    this.hits.set(key, arr);
    return true;
  }
  clear() {
    this.hits.clear();
  }
}

class HttpError extends Error {
  constructor(public status: number, public code: ErrorCode, public extra?: Record<string, unknown>) {
    super(code);
  }
}

const PAYLOAD_FIELDS = [
  "name", "display_name", "start_date", "end_date", "home_currency", "default_lang", "default_role", "countries",
  "currencies", "center",
] as const;

/** Picks only the documented fields (the database validates each one). */
export function pickPayload(body: Record<string, unknown>): Record<string, unknown> {
  const p: Record<string, unknown> = {};
  for (const k of PAYLOAD_FIELDS) if (k in body) p[k] = body[k];
  return p;
}

/** CHANGE 2026-10-27 F21-FN-20: new (no previous version). The F21 pre-fill as the wizard may use it, or null when absent
 *  or malformed: name 1–40 chars, countries 1–10 distinct ISO-2 codes, month "YYYY-MM-01" or null, lang 'he' | 'en'. */
export interface Prefill {
  name: string;
  countries: string[];
  month: string | null;
  lang: "he" | "en";
}
export function cleanPrefill(v: unknown): Prefill | null {
  if (!v || typeof v !== "object" || Array.isArray(v)) return null;
  const o = v as Record<string, unknown>;
  const name = typeof o.name === "string" ? o.name.trim() : "";
  if (!name || name.length > 40) return null;
  const c = Array.isArray(o.countries) ? o.countries : [];
  if (c.length < 1 || c.length > 10 || !c.every((x) => typeof x === "string" && /^[A-Z]{2}$/.test(x)) || new Set(c).size !== c.length) return null;
  let month: string | null = null;
  if (o.month !== null && o.month !== undefined) {
    if (typeof o.month !== "string" || !/^\d{4}-(0[1-9]|1[0-2])-01$/.test(o.month)) return null;
    month = o.month;
  }
  if (o.lang !== "he" && o.lang !== "en") return null;
  return { name, countries: [...c] as string[], month, lang: o.lang };
}

// -----------------------------------------------------------------------------------------------------
// dependencies (production defaults are lazy: the Supabase client is created on first use)
// -----------------------------------------------------------------------------------------------------
let serviceClient: SupabaseClient | null = null;
function db(): SupabaseClient {
  if (!serviceClient) {
    const env = (k: string) => Deno.env.get(k) || "";
    serviceClient = createClient(env("SUPABASE_URL"), env("PT_SERVICE_KEY") || env("SUPABASE_SERVICE_ROLE_KEY"), {
      auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
    });
  }
  return serviceClient;
}
const DEFAULT_DEPS: Deps = {
  async getUser(jwt) {
    const { data, error } = await db().auth.getUser(jwt);
    if (error || !data?.user) return null;
    const u = data.user as unknown as AuthUser;
    return { id: u.id, email: u.email ?? null, email_confirmed_at: u.email_confirmed_at ?? null, is_anonymous: !!u.is_anonymous };
  },
  async rpc(name, args) {
    const { data, error } = await db().rpc(name, args);
    return { data, error: error ? { message: error.message, details: error.details, code: error.code } : null };
  },
  now: () => Date.now(),
};
let deps: Deps = { ...DEFAULT_DEPS };
const limiter = new RateLimiter();

export function setDeps(d: Partial<Deps>): void {
  deps = { ...deps, ...Object.fromEntries(Object.entries(d).filter(([, v]) => typeof v === "function")) } as Deps;
}
export function resetDeps(): void {
  deps = { ...DEFAULT_DEPS };
  limiter.clear();
}

function env(k: string): string | undefined {
  try {
    return Deno.env.get(k);
  } catch {
    return undefined; // no --allow-env (tests)
  }
}
function log(fields: Record<string, unknown>): void {
  console.log(JSON.stringify({ fn: "create-trip", v: FN_VERSION, ...fields }));
}
let joinWarned = false;
function joinBase(): string {
  const r = resolveJoinBase(env("JOIN_URL"));
  if (r.fallback && !joinWarned) {
    joinWarned = true;
    log({ event: "join_url_invalid_fallback" }); // the value itself is never logged
  }
  return r.url;
}

// -----------------------------------------------------------------------------------------------------
// handler
// -----------------------------------------------------------------------------------------------------
function json(origin: string | null, status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders(origin), "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

async function verifiedUser(req: Request): Promise<AuthUser & { email: string }> {
  const m = /^Bearer\s+(\S+)\s*$/i.exec(req.headers.get("authorization") || "");
  if (!m) throw new HttpError(401, "unauthorized");
  const u = await deps.getUser(m[1]); // a thrown error (auth server down) → 500 server_error, not 401
  if (!u || !u.id) throw new HttpError(401, "unauthorized");
  const email = typeof u.email === "string" ? u.email.trim().toLowerCase() : "";
  if (!email || !u.email_confirmed_at) throw new HttpError(403, "email_not_verified");
  return { ...u, email };
}

function mapRpcError(e: { message: string; details?: string }): HttpError {
  const msg = String(e.message || "");
  if (msg === "invite_invalid") return new HttpError(409, "invite_invalid");
  if (msg === "too_many_currencies") return new HttpError(400, "too_many_currencies");
  if (msg === "invalid_payload") {
    const f = typeof e.details === "string" && /^[a-z_]{1,40}$/.test(e.details) ? e.details : "payload";
    return new HttpError(400, "invalid_payload", { field: f });
  }
  return new HttpError(500, "server_error");
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

async function actLookup(user: AuthUser & { email: string }) {
  const r = await deps.rpc("find_invite_for_email", { p_email: user.email });
  if (r.error) throw mapRpcError(r.error);
  const d = asObject(r.data);
  if (!d || d.found !== true) return { found: false };
  const out: Record<string, unknown> = {
    found: true,
    draft_name: typeof d.draft_name === "string" ? d.draft_name : null,
    inviter_name: typeof d.inviter_name === "string" ? d.inviter_name : null,
    expires_at: d.expires_at ?? null,
  };
  const prefill = cleanPrefill(d.prefill); // CHANGE 2026-10-27 F21-FN-20: + prefill (only when the invite came from a request)
  if (prefill) out.prefill = prefill;
  return out;
}

async function actCreate(user: AuthUser & { email: string }, body: Record<string, unknown>) {
  const r = await deps.rpc("create_trip_from_invite", { p_user: user.id, p_email: user.email, p_payload: pickPayload(body) });
  if (r.error) throw mapRpcError(r.error);
  const d = asObject(r.data);
  if (!d || typeof d.trip_id !== "string" || typeof d.join_code !== "string") throw new HttpError(500, "server_error");
  return { trip_id: d.trip_id, join_code: d.join_code, join_url: joinUrl(joinBase(), d.join_code), created: d.created !== false };
}

export async function handler(req: Request): Promise<Response> {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(origin) });
  if (req.method !== "POST") {
    log({ action: "", status: 405, code: "method_not_allowed" });
    return json(origin, 405, { error: "method_not_allowed" });
  }
  let action = "";
  try {
    let body: Record<string, unknown>;
    try {
      const b = await req.json();
      body = b && typeof b === "object" && !Array.isArray(b) ? b as Record<string, unknown> : {};
    } catch {
      body = {};
    }
    action = typeof body.action === "string" ? body.action : "";
    const user = await verifiedUser(req);
    if (action !== "lookup" && action !== "create") throw new HttpError(400, "invalid_request");
    if (!limiter.hit(`${user.id}:${action}`, RATE_MAX[action], deps.now())) throw new HttpError(429, "rate_limited");
    const out = action === "lookup" ? await actLookup(user) : await actCreate(user, body);
    log({ action, status: 200 });
    return json(origin, 200, out);
  } catch (e) {
    const he = e instanceof HttpError ? e : new HttpError(500, "server_error");
    log({ action: ["lookup", "create"].includes(action) ? action : "", status: he.status, code: he.code });
    return json(origin, he.status, { error: he.code, ...(he.extra || {}) });
  }
}

export function startServer(): void {
  joinBase(); // validate the JOIN_URL secret once at start (logs join_url_invalid_fallback if it is unusable)
  Deno.serve(handler);
}

if (import.meta.main) startServer();
