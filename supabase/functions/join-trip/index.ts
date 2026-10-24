// Lonely Planner (Plan_Travel) Edge Function `join-trip` · version 3.0.0-alpha.7.0 · F05 (+F06)
// CHANGE 2026-10-22 F06-FN-07: what changed from 3.0.0-alpha.6.0: version only (FN_VERSION) plus the response header
//   `X-Function-Version` (closes F05 QA finding D1). No logic change: F06 D2 (a removed member may ask again) comes from the
//   SQL in 0014_f06.sql — `member_removed` stays in the code list but the database no longer produces it.
// CHANGE 2026-10-19 F05-FN-01: new file (no previous version). A device joins a trip from the group link, waits for the
//   manager, and (iPhone, D1) moves its membership to the installed app with a transfer code (docs/F05_spec.md §3).
//   Runs with the service role; verify_jwt is OFF for this function — it verifies the caller's JWT itself with
//   auth.getUser(jwt). Any signed-in identity is accepted, anonymous included (no email needed, by design).
//
// Actions (POST body {action, …}, every action needs `Authorization: Bearer <user JWT>`):
//   preview        {code}               → rpc join_preview   → {trip_id, name, start_date, end_date, days, members, manager, me}
//   request        {code, display_name} → rpc join_request   → {trip_id, member_id, status, role, display_name, created}
//   cancel         {trip_id}            → rpc join_cancel    → {ok:true}
//   issue_transfer {trip_id}            → rpc issue_transfer → {code, expires_at}
//   claim_transfer {code}               → rpc claim_transfer → {trip_id, member_id, role, display_name}
// Errors: {error:<code>} with HTTP status — 401 unauthorized · 400 invalid_request / name_invalid · 404 code_invalid ·
//   409 name_taken / not_pending / transfer_invalid / already_member · 403 member_removed / not_member · 429 rate_limited ·
//   405 method_not_allowed · 500 server_error. Rate limits live in the database (spec §2.4); the caller's address is passed
//   only as a SHA-256 hash (ip_hash), never stored or logged in clear.
//
// Testability (QA contract, same as create-trip): importable without starting a server (main.ts calls startServer()).
//   setDeps({getUser?, rpc?, now?}) replaces the real Supabase calls; resetDeps() restores them. handler(req) is the
//   request handler. ipHash(req) and statusFor(code) are exported.
// Logs: one JSON line per request with action, status and error code only — never the JWT, code, names or addresses.

import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2.45.4";

export const FN_VERSION = "3.0.0-alpha.7.0"; // CHANGE 2026-10-22 F06-FN-07: was "3.0.0-alpha.6.0"
export const ACTIONS = ["preview", "request", "cancel", "issue_transfer", "claim_transfer"] as const;
export type Action = typeof ACTIONS[number];

export type ErrorCode =
  | "unauthorized" | "invalid_request" | "code_invalid" | "name_invalid" | "name_taken" | "rate_limited"
  | "member_removed" | "not_pending" | "not_member" | "transfer_invalid" | "already_member" | "method_not_allowed"
  | "server_error";

const STATUS: Record<ErrorCode, number> = {
  unauthorized: 401, invalid_request: 400, name_invalid: 400, code_invalid: 404, name_taken: 409, not_pending: 409,
  transfer_invalid: 409, already_member: 409, member_removed: 403, not_member: 403, rate_limited: 429,
  method_not_allowed: 405, server_error: 500,
};
export function statusFor(code: string): number {
  return (STATUS as Record<string, number>)[code] ?? 500;
}

export interface AuthUser {
  id: string;
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

/** Identical to create-trip / invite-manager. */
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

const JOIN_CODE_RE = /^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$/;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Join code as typed or pasted: whole link, "#code=…", spaces, lower case → the 8-char code, or null. */
export function normJoinCode(v: unknown): string | null {
  if (typeof v !== "string") return null;
  let s = v.trim();
  const m = /[#?&]code=([A-Za-z0-9]+)/.exec(s);
  if (m) s = m[1];
  s = s.replace(/[\s-]/g, "").toUpperCase();
  return JOIN_CODE_RE.test(s) ? s : null;
}

export function isUuid(v: unknown): v is string {
  return typeof v === "string" && UUID_RE.test(v);
}

/** SHA-256 hex of the caller's first forwarded address (prefixed, so it cannot be matched against a plain IP hash). */
export async function ipHash(req: Request): Promise<string | null> {
  const raw = (req.headers.get("x-forwarded-for") || req.headers.get("cf-connecting-ip") || req.headers.get("x-real-ip") || "")
    .split(",")[0].trim();
  if (!raw) return null;
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("lp-f05:" + raw));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

class HttpError extends Error {
  status: number;
  code: ErrorCode;
  constructor(status: number, code: ErrorCode) {
    super(code);
    this.status = status;
    this.code = code;
  }
}
function fail(code: ErrorCode): HttpError {
  return new HttpError(statusFor(code), code);
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
    return { id: u.id, is_anonymous: !!u.is_anonymous };
  },
  async rpc(name, args) {
    const { data, error } = await db().rpc(name, args);
    return { data, error: error ? { message: error.message, details: error.details, code: error.code } : null };
  },
  now: () => Date.now(),
};
let deps: Deps = { ...DEFAULT_DEPS };

export function setDeps(d: Partial<Deps>): void {
  deps = { ...deps, ...Object.fromEntries(Object.entries(d).filter(([, v]) => typeof v === "function")) } as Deps;
}
export function resetDeps(): void {
  deps = { ...DEFAULT_DEPS };
}

function log(fields: Record<string, unknown>): void {
  console.log(JSON.stringify({ fn: "join-trip", v: FN_VERSION, ...fields }));
}

// -----------------------------------------------------------------------------------------------------
// handler
// -----------------------------------------------------------------------------------------------------
function json(origin: string | null, status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    // CHANGE 2026-10-22 F06-FN-07: + X-Function-Version (was: no version header)
    headers: { ...corsHeaders(origin), "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", "X-Function-Version": FN_VERSION },
  });
}

async function signedInUser(req: Request): Promise<AuthUser> {
  const m = /^Bearer\s+(\S+)\s*$/i.exec(req.headers.get("authorization") || "");
  if (!m) throw fail("unauthorized");
  const u = await deps.getUser(m[1]); // a thrown error (auth server down) → 500 server_error, not 401
  if (!u || !u.id) throw fail("unauthorized");
  return u;
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

/** Calls a service-role function; a returned {error:code} becomes the matching HTTP error. */
async function call(name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const r = await deps.rpc(name, args);
  if (r.error) throw fail("server_error");
  const d = asObject(r.data);
  if (!d) throw fail("server_error");
  if (typeof d.error === "string") {
    const code = d.error as ErrorCode;
    if (!(code in STATUS) || code === "server_error") throw fail("server_error");
    throw fail(code);
  }
  return d;
}

function pick(d: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  const o: Record<string, unknown> = {};
  for (const k of keys) o[k] = k in d ? d[k] : null;
  return o;
}

async function act(action: Action, user: AuthUser, body: Record<string, unknown>, ip: string | null) {
  switch (action) {
    case "preview": {
      const code = normJoinCode(body.code);
      if (!code) throw fail("code_invalid");
      const d = await call("join_preview", { p_user: user.id, p_code: code, p_ip: ip });
      const me = asObject(d.me);
      return {
        ...pick(d, ["trip_id", "name", "start_date", "end_date", "days", "members", "manager"]),
        me: me ? pick(me, ["member_id", "status", "role", "display_name"]) : null,
      };
    }
    case "request": {
      const code = normJoinCode(body.code);
      if (!code) throw fail("code_invalid");
      if (typeof body.display_name !== "string") throw fail("name_invalid");
      const d = await call("join_request", { p_user: user.id, p_code: code, p_name: body.display_name.slice(0, 200), p_ip: ip });
      return pick(d, ["trip_id", "member_id", "status", "role", "display_name", "created"]);
    }
    case "cancel": {
      if (!isUuid(body.trip_id)) throw fail("invalid_request");
      await call("join_cancel", { p_user: user.id, p_trip: body.trip_id });
      return { ok: true };
    }
    case "issue_transfer": {
      if (!isUuid(body.trip_id)) throw fail("invalid_request");
      const d = await call("issue_transfer", { p_user: user.id, p_trip: body.trip_id });
      if (typeof d.code !== "string" || !/^\d{6}$/.test(d.code)) throw fail("server_error");
      return pick(d, ["code", "expires_at"]);
    }
    case "claim_transfer": {
      if (typeof body.code !== "string") throw fail("transfer_invalid");
      const d = await call("claim_transfer", { p_user: user.id, p_code: body.code.slice(0, 32), p_ip: ip });
      return pick(d, ["trip_id", "member_id", "role", "display_name"]);
    }
  }
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
    const user = await signedInUser(req);
    if (!(ACTIONS as readonly string[]).includes(action)) throw fail("invalid_request");
    const out = await act(action as Action, user, body, await ipHash(req));
    log({ action, status: 200 });
    return json(origin, 200, out);
  } catch (e) {
    const he = e instanceof HttpError ? e : fail("server_error");
    log({ action: (ACTIONS as readonly string[]).includes(action) ? action : "", status: he.status, code: he.code });
    return json(origin, he.status, { error: he.code });
  }
}

export function startServer(): void {
  Deno.serve(handler);
}

if (import.meta.main) startServer();
