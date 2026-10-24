// Lonely Planner (Plan_Travel) Edge Function `manage-members` · version 3.0.0-alpha.7.0 · F06
// CHANGE 2026-10-22 F06-FN-01: new file (no previous version). A manager changes a member's role or name, removes a member,
//   resets the trip's join link; any member leaves the trip or records "last seen" (docs/F06_spec.md §3.1, D13: one function
//   with several actions instead of `update-member` + `rotate-join-link`). Runs with the service role; verify_jwt is OFF —
//   the caller's JWT is verified here with auth.getUser(jwt), exactly as in approve-member; every permission check
//   (active manager of THAT trip, last manager, name rules) is done by the database functions of 0014_f06.sql.
//
// POST {action, …} (every action needs `Authorization: Bearer <user JWT>`):
//   set_role    {member_id, role}          → rpc member_set_role  → {member_id, trip_id, role, display_name, changed}
//   rename      {member_id, display_name}  → rpc member_rename    → {member_id, trip_id, display_name, changed}
//   remove      {member_id}                → rpc member_remove    → {member_id, trip_id, status:'removed', display_name}
//   leave       {trip_id}                  → rpc member_leave     → {ok:true, trip_id, member_id}
//   rotate_link {trip_id}                  → rpc rotate_join_code → {code, link_version}  (spec clarification C4: the
//                                                                   body field `version` is FN_VERSION)
//   touch       {trip_id}                  → rpc member_touch     → {ok:true, touched}
// Every success body also carries `version` (= FN_VERSION) and every response the header `X-Function-Version`
// (closes F05 QA finding D1 for this function).
// Errors: {error:<code>, version} — 401 unauthorized · 400 invalid_request / role_invalid / name_invalid ·
//   403 not_manager / not_member · 409 not_active / name_taken / last_manager · 405 method_not_allowed · 500 server_error.
//
// Testability (same contract as approve-member): importable without a server (main.ts calls startServer());
//   setDeps({getUser?, rpc?}) / resetDeps(); handler(req); statusFor(code).
// Logs: one JSON line per request with action, status and error code only — never the JWT, ids, codes or names.

import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2.45.4";

export const FN_VERSION = "3.0.0-alpha.7.0";
export const VERSION_HEADER = "X-Function-Version";
export const ACTIONS = ["set_role", "rename", "remove", "leave", "rotate_link", "touch"] as const;
export type Action = typeof ACTIONS[number];

export type ErrorCode =
  | "unauthorized" | "invalid_request" | "role_invalid" | "name_invalid" | "not_manager" | "not_member" | "not_active"
  | "name_taken" | "last_manager" | "method_not_allowed" | "server_error";
const STATUS: Record<ErrorCode, number> = {
  unauthorized: 401, invalid_request: 400, role_invalid: 400, name_invalid: 400, not_manager: 403, not_member: 403,
  not_active: 409, name_taken: 409, last_manager: 409, method_not_allowed: 405, server_error: 500,
};
export function statusFor(code: string): number {
  return (STATUS as Record<string, number>)[code] ?? 500;
}

export interface AuthUser {
  id: string;
}
export interface RpcResult {
  data: unknown;
  error: { message: string; details?: string; code?: string } | null;
}
export interface Deps {
  getUser: (jwt: string) => Promise<AuthUser | null>;
  rpc: (name: string, args: Record<string, unknown>) => Promise<RpcResult>;
}

/** Identical to approve-member / join-trip. */
export function isAllowedOrigin(origin: string | null): boolean {
  if (!origin) return false;
  return origin === "https://orsela.github.io" || /^http:\/\/localhost(:\d{1,5})?$/.test(origin);
}
export function corsHeaders(origin: string | null): Record<string, string> {
  const h: Record<string, string> = { "Vary": "Origin" };
  if (isAllowedOrigin(origin)) {
    h["Access-Control-Allow-Origin"] = origin as string;
    h["Access-Control-Allow-Methods"] = "POST, OPTIONS";
    h["Access-Control-Allow-Headers"] = "authorization, x-client-info, apikey, content-type";
    h["Access-Control-Expose-Headers"] = VERSION_HEADER;
    h["Access-Control-Max-Age"] = "600";
  }
  return h;
}
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ROLES = ["viewer", "editor", "manager"];
export function isUuid(v: unknown): v is string {
  return typeof v === "string" && UUID_RE.test(v);
}

class HttpError extends Error {
  status: number;
  code: ErrorCode;
  constructor(code: ErrorCode) {
    super(code);
    this.status = statusFor(code);
    this.code = code;
  }
}

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
    return { id: (data.user as unknown as AuthUser).id };
  },
  async rpc(name, args) {
    const { data, error } = await db().rpc(name, args);
    return { data, error: error ? { message: error.message, details: error.details, code: error.code } : null };
  },
};
let deps: Deps = { ...DEFAULT_DEPS };
export function setDeps(d: Partial<Deps>): void {
  deps = { ...deps, ...Object.fromEntries(Object.entries(d).filter(([, v]) => typeof v === "function")) } as Deps;
}
export function resetDeps(): void {
  deps = { ...DEFAULT_DEPS };
}
function log(fields: Record<string, unknown>): void {
  console.log(JSON.stringify({ fn: "manage-members", v: FN_VERSION, ...fields }));
}
function json(origin: string | null, status: number, body: Record<string, unknown>): Response {
  return new Response(JSON.stringify({ ...body, version: FN_VERSION }), {
    status,
    headers: {
      ...corsHeaders(origin),
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      [VERSION_HEADER]: FN_VERSION,
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
function pick(d: Record<string, unknown>, keys: string[]): Record<string, unknown> {
  const o: Record<string, unknown> = {};
  for (const k of keys) o[k] = k in d ? d[k] : null;
  return o;
}

/** Calls a service-role function; a returned {error:code} becomes the matching HTTP error. */
async function call(name: string, args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const r = await deps.rpc(name, args);
  if (r.error) throw new HttpError("server_error");
  const d = asObject(r.data);
  if (!d) throw new HttpError("server_error");
  if (typeof d.error === "string") {
    const code = d.error as ErrorCode;
    throw new HttpError(code in STATUS && code !== "server_error" ? code : "server_error");
  }
  return d;
}

async function act(action: Action, uid: string, body: Record<string, unknown>): Promise<Record<string, unknown>> {
  switch (action) {
    case "set_role": {
      // C6: missing / null → invalid_request; any other value outside the lower-case list → role_invalid
      if (!isUuid(body.member_id) || body.role == null) throw new HttpError("invalid_request");
      if (typeof body.role !== "string" || !ROLES.includes(body.role)) throw new HttpError("role_invalid");
      const d = await call("member_set_role", { p_user: uid, p_member: body.member_id, p_role: body.role });
      return pick(d, ["member_id", "trip_id", "role", "display_name", "changed"]);
    }
    case "rename": {
      if (!isUuid(body.member_id) || body.display_name == null) throw new HttpError("invalid_request");   // C6
      if (typeof body.display_name !== "string") throw new HttpError("name_invalid");
      const d = await call("member_rename", { p_user: uid, p_member: body.member_id, p_name: body.display_name.slice(0, 200) });
      return pick(d, ["member_id", "trip_id", "display_name", "changed"]);
    }
    case "remove": {
      if (!isUuid(body.member_id)) throw new HttpError("invalid_request");
      const d = await call("member_remove", { p_user: uid, p_member: body.member_id });
      return pick(d, ["member_id", "trip_id", "status", "display_name"]);
    }
    case "leave": {
      if (!isUuid(body.trip_id)) throw new HttpError("invalid_request");
      const d = await call("member_leave", { p_user: uid, p_trip: body.trip_id });
      return { ok: true, trip_id: d.trip_id ?? body.trip_id, member_id: d.member_id ?? null };
    }
    case "rotate_link": {
      if (!isUuid(body.trip_id)) throw new HttpError("invalid_request");
      const d = await call("rotate_join_code", { p_user: uid, p_trip: body.trip_id });
      if (typeof d.code !== "string" || !/^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{8}$/.test(d.code)) throw new HttpError("server_error");
      // C4: the link's version is `link_version`; `version` in the body stays the function version (spec §3.1)
      return { code: d.code, link_version: d.link_version ?? null };
    }
    case "touch": {
      if (!isUuid(body.trip_id)) throw new HttpError("invalid_request");
      const d = await call("member_touch", { p_user: uid, p_trip: body.trip_id });
      return { ok: true, touched: !!d.touched };
    }
  }
}

export async function handler(req: Request): Promise<Response> {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: { ...corsHeaders(origin), [VERSION_HEADER]: FN_VERSION } });
  }
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
    const m = /^Bearer\s+(\S+)\s*$/i.exec(req.headers.get("authorization") || "");
    if (!m) throw new HttpError("unauthorized");
    const user = await deps.getUser(m[1]); // a thrown error (auth server down) → 500 server_error, not 401
    if (!user || !user.id) throw new HttpError("unauthorized");
    if (!(ACTIONS as readonly string[]).includes(action)) throw new HttpError("invalid_request");
    const out = await act(action as Action, user.id, body);
    log({ action, status: 200 });
    return json(origin, 200, out);
  } catch (e) {
    const he = e instanceof HttpError ? e : new HttpError("server_error");
    log({ action: (ACTIONS as readonly string[]).includes(action) ? action : "", status: he.status, code: he.code });
    return json(origin, he.status, { error: he.code });
  }
}

export function startServer(): void {
  Deno.serve(handler);
}

if (import.meta.main) startServer();
