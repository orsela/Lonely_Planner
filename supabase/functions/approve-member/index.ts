// Lonely Planner (Plan_Travel) Edge Function `approve-member` · version 3.0.0-alpha.6.0 · F05
// CHANGE 2026-10-19 F05-FN-02: new file (no previous version). An active manager approves a pending member with a role
//   (D3: viewer / editor / manager; none → the trip's default role) or rejects the request (the pending row is deleted,
//   D6). docs/F05_spec.md §3. Runs with the service role; verify_jwt is OFF — the caller's JWT is verified here with
//   auth.getUser(jwt); the manager check itself is done by the database function approve_member (0012_f05.sql).
//
// POST {member_id, decision:'approve'|'reject', role?}  →  rpc approve_member
//   200 {status:'active', member_id, role, display_name, trip_id}  |  200 {status:'rejected', member_id, display_name}
// Errors: {error:<code>} — 401 unauthorized · 400 invalid_request / role_invalid · 403 not_manager · 409 not_pending ·
//   405 method_not_allowed · 500 server_error.
//
// Testability: importable without a server (main.ts calls startServer()); setDeps({getUser?, rpc?}) / resetDeps(); handler(req).
// Logs: one JSON line per request with status and error code only — never the JWT, ids or names.

import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2.45.4";

export const FN_VERSION = "3.0.0-alpha.6.0";

export type ErrorCode =
  | "unauthorized" | "invalid_request" | "role_invalid" | "not_manager" | "not_pending" | "method_not_allowed"
  | "server_error";
const STATUS: Record<ErrorCode, number> = {
  unauthorized: 401, invalid_request: 400, role_invalid: 400, not_manager: 403, not_pending: 409,
  method_not_allowed: 405, server_error: 500,
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
    h["Access-Control-Max-Age"] = "600";
  }
  return h;
}
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ROLES = ["viewer", "editor", "manager"];

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
  console.log(JSON.stringify({ fn: "approve-member", v: FN_VERSION, ...fields }));
}
function json(origin: string | null, status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders(origin), "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
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

export async function handler(req: Request): Promise<Response> {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(origin) });
  if (req.method !== "POST") {
    log({ status: 405, code: "method_not_allowed" });
    return json(origin, 405, { error: "method_not_allowed" });
  }
  try {
    let body: Record<string, unknown>;
    try {
      const b = await req.json();
      body = b && typeof b === "object" && !Array.isArray(b) ? b as Record<string, unknown> : {};
    } catch {
      body = {};
    }
    const m = /^Bearer\s+(\S+)\s*$/i.exec(req.headers.get("authorization") || "");
    if (!m) throw new HttpError("unauthorized");
    const user = await deps.getUser(m[1]);
    if (!user || !user.id) throw new HttpError("unauthorized");

    const decision = body.decision;
    if (!UUID_RE.test(String(body.member_id || "")) || (decision !== "approve" && decision !== "reject")) {
      throw new HttpError("invalid_request");
    }
    let role: string | null = null;
    if (decision === "approve" && body.role != null && body.role !== "") {
      if (typeof body.role !== "string" || !ROLES.includes(body.role)) throw new HttpError("role_invalid");
      role = body.role;
    }
    const r = await deps.rpc("approve_member", { p_user: user.id, p_member: body.member_id, p_decision: decision, p_role: role });
    if (r.error) throw new HttpError("server_error");
    const d = asObject(r.data);
    if (!d) throw new HttpError("server_error");
    if (typeof d.error === "string") {
      const code = d.error as ErrorCode;
      throw new HttpError(code in STATUS && code !== "server_error" ? code : "server_error");
    }
    const out = d.status === "active"
      ? { status: "active", member_id: d.member_id ?? null, role: d.role ?? null, display_name: d.display_name ?? null, trip_id: d.trip_id ?? null }
      : { status: "rejected", member_id: d.member_id ?? null, display_name: d.display_name ?? null };
    log({ status: 200, decision });
    return json(origin, 200, out);
  } catch (e) {
    const he = e instanceof HttpError ? e : new HttpError("server_error");
    log({ status: he.status, code: he.code });
    return json(origin, he.status, { error: he.code });
  }
}

export function startServer(): void {
  Deno.serve(handler);
}

if (import.meta.main) startServer();
