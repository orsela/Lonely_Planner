// Lonely Planner (Plan_Travel) Edge Function `vault-delete` · version 3.0.0-alpha.18.0 · F12 (shared document vault)
// CHANGE 2026-11-24 F12-FN-01: new file (no previous version). A trip manager deletes one document of the vault
//   (claude/Plan_Travel_F12_spec.md §3): the Storage object FIRST, then the trip_docs row — so a failure in the middle leaves a
//   row without an object (retry-able, shown as "unavailable"), never an object without a row. Runs with the service role;
//   verify_jwt is OFF — the caller's JWT is verified here with auth.getUser(jwt), exactly as in manage-members; the permission
//   check (active MANAGER of the document's trip) is done twice by the database functions of 0023_f12.sql:
//   vault_delete_prepare (before touching Storage) and vault_delete_finish (before deleting the row).
//
// POST {doc_id}   with `Authorization: Bearer <user JWT>`
//   → 200 {ok:true, deleted:true|false, version}     (deleted:false = the row was already gone — a retry after success)
// Errors: {error:<code>, version} — 401 unauthorized · 400 invalid_request · 403 not_manager · 404 not_found
//   (also for a non-member: no hint that the document exists) · 405 method_not_allowed · 500 server_error.
// Every response carries the header X-Function-Version (exposed through CORS). No other function is changed by F12.
//
// Testability (same contract as manage-members): importable without a server (main.ts calls startServer());
//   setDeps({getUser?, rpc?, removeObject?}) / resetDeps(); handler(req); statusFor(code).
// Logs: one JSON line per request with status and error code only — never the JWT, ids, paths or document names.

import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2.45.4";

export const FN_VERSION = "3.0.0-alpha.18.0";
export const VERSION_HEADER = "X-Function-Version";
export const BUCKET = "trip-docs";

export type ErrorCode =
  | "unauthorized" | "invalid_request" | "not_manager" | "not_found" | "method_not_allowed" | "server_error";
const STATUS: Record<ErrorCode, number> = {
  unauthorized: 401, invalid_request: 400, not_manager: 403, not_found: 404, method_not_allowed: 405, server_error: 500,
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
export interface RemoveResult {
  error: { message: string } | null;
}
export interface Deps {
  getUser: (jwt: string) => Promise<AuthUser | null>;
  rpc: (name: string, args: Record<string, unknown>) => Promise<RpcResult>;
  /** Removes one object of the `trip-docs` bucket; a path that does not exist is NOT an error (retry after a half-done delete). */
  removeObject: (path: string) => Promise<RemoveResult>;
}

/** Identical to approve-member / manage-members. */
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
export function isUuid(v: unknown): v is string {
  return typeof v === "string" && UUID_RE.test(v);
}
/** The only path shape the database accepts: "<trip uuid>/<doc uuid>.<pdf|jpg|png|webp>" — checked again before Storage is touched. */
const PATH_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(pdf|jpg|png|webp)$/;
export function isVaultPath(v: unknown): v is string {
  return typeof v === "string" && PATH_RE.test(v);
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
  async removeObject(path) {
    // storage-js answers { data: [], error: null } for a path that is not there — treated as success (idempotent)
    const { error } = await db().storage.from(BUCKET).remove([path]);
    return { error: error ? { message: error.message } : null };
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
  console.log(JSON.stringify({ fn: "vault-delete", v: FN_VERSION, ...fields }));
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

/** Calls a service-role database function; a returned {error:code} becomes the matching HTTP error. */
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

export async function handler(req: Request): Promise<Response> {
  const origin = req.headers.get("origin");
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: { ...corsHeaders(origin), [VERSION_HEADER]: FN_VERSION } });
  }
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
    const user = await deps.getUser(m[1]); // a thrown error (auth server down) → 500 server_error, not 401
    if (!user || !user.id) throw new HttpError("unauthorized");
    if (!isUuid(body.doc_id)) throw new HttpError("invalid_request");

    // 1 · may this user delete this document? (manager of its trip) — nothing is touched yet
    const prep = await call("vault_delete_prepare", { p_user: user.id, p_doc: body.doc_id });
    if (!isVaultPath(prep.storage_path)) throw new HttpError("server_error");   // never hand an odd path to Storage
    // 2 · the object first …
    const rm = await deps.removeObject(prep.storage_path);
    if (rm.error) throw new HttpError("server_error");                          // the row stays → the manager can retry
    // 3 · … then the row (re-checks the manager)
    const fin = await call("vault_delete_finish", { p_user: user.id, p_doc: body.doc_id });
    log({ status: 200 });
    return json(origin, 200, { ok: true, deleted: fin.deleted !== false });
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
