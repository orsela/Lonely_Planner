// Lonely Planner · invite-manager F21 unit tests · version 3.0.0-alpha.8.0 · F21
// CHANGE 2026-10-27 F21-FN-14: new file (no previous version). Tests for docs/F21_spec.md §3.2 (approve_request,
//   reject_request, English invite, reject email, resend in the invite's lang) with stubbed RPCs and SMTP; plus the proof that
//   renderInviteEmail with lang 'he' (or no lang) is byte-identical to alpha.7.2 (3.0.0-alpha.4.1 of this function).
//
// Run offline (no Deno binary):
//   node --experimental-transform-types --no-warnings --import ./tests/f05/deno_shim.mjs scripts/dev/deno_test_node.mjs \
//        supabase/functions/invite-manager/test_f21.ts
// With Deno: deno test --no-check --import-map=supabase/functions/invite-manager/test_import_map.json supabase/functions/invite-manager/test_f21.ts

import {
  type Deps, EMAIL_SUBJECT, EMAIL_SUBJECT_EN, FN_VERSION, type InviteRow, type InviteStore, type MailMessage, makeHandler,
  type NewInvite, REJECT_TEXT, renderInviteEmail, renderRejectEmail, sha256Hex,
} from "./index.ts";

function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
function eq<T>(a: T, b: T, msg = "") {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) throw new Error(`${msg} expected ${sb}, got ${sa}`);
}

class Store implements InviteStore {
  rows = new Map<string, InviteRow>();
  n = 0;
  isPlatformAdmin(uid: string) { return Promise.resolve(uid === ADMIN); }
  inviterName(uid: string) { return Promise.resolve(uid === ADMIN ? "אור" : null); }
  findOpenByEmail(email: string) {
    return Promise.resolve([...this.rows.values()].find((r) => r.email === email && !r.used_at && !r.revoked_at) ?? null);
  }
  getById(id: string) { const r = this.rows.get(id); return Promise.resolve(r ? { ...r } : null); }
  findByHash(h: string) { return Promise.resolve([...this.rows.values()].find((r) => r.token_hash === h) ?? null); }
  insert(row: NewInvite) {
    const id = `00000000-0000-4000-8000-${String(++this.n).padStart(12, "0")}`;
    this.rows.set(id, { id, ...row, used_at: null, revoked_at: null, opened_at: null, created_at: row.last_sent_at, lang: "he" });
    return Promise.resolve(id);
  }
  deleteById(id: string) { this.rows.delete(id); return Promise.resolve(); }
  revokeOpen(id: string, at: string) { const r = this.rows.get(id); if (!r || r.revoked_at || r.used_at) return Promise.resolve(0); r.revoked_at = at; return Promise.resolve(1); }
  updateOpen(id: string, f: Partial<InviteRow>) { const r = this.rows.get(id); if (!r || r.revoked_at || r.used_at) return Promise.resolve(0); this.rows.set(id, { ...r, ...f }); return Promise.resolve(1); }
  markOpened() { return Promise.resolve(); }
}

const ADMIN = "aaaaaaaa-0000-4000-8000-000000000001";
const REQ = "cccccccc-0000-4000-8000-000000000001";
const INV = "dddddddd-0000-4000-8000-000000000001";
const OLD = "dddddddd-0000-4000-8000-000000000002";
const APP = "https://orsela.github.io/Lonely_Planner/app/";
const LINK_BASE = "https://orsela.github.io/Lonely_Planner/invite/#invite=";
const NOW = new Date("2026-10-27T09:00:00Z");
const EXP = "2026-11-03T09:00:00.000Z";

type Rpc = (name: string, args: Record<string, unknown>) => unknown;
function setup(rpcImpl: Rpc, opts: { failMail?: boolean } = {}) {
  const store = new Store();
  const sent: MailMessage[] = [];
  const logs: string[] = [];
  const calls: { name: string; args: Record<string, unknown> }[] = [];
  const ctl = { failMail: !!opts.failMail };
  const deps: Deps = {
    store,
    verifyJwt: (j) => Promise.resolve(j === "jwt-admin" ? ADMIN : j === "jwt-user" ? "bbbbbbbb-0000-4000-8000-000000000002" : null),
    sendMail: (m) => (ctl.failMail ? Promise.reject(new Error("smtp down for tom@example.co.uk")) : (sent.push(m), Promise.resolve())),
    now: () => new Date(NOW),
    random: (n) => new Uint8Array(n).fill(7),
    appUrl: APP,
    log: (e, f) => logs.push(JSON.stringify({ e, ...(f || {}) })),
    rpc: (name, args) => {
      calls.push({ name, args });
      try {
        return Promise.resolve(rpcImpl(name, args));
      } catch (e) {
        return Promise.reject(e);
      }
    },
  };
  const h = makeHandler(deps);
  async function call(body: unknown, jwt: string | null = "jwt-admin") {
    const headers: Record<string, string> = { "content-type": "application/json", origin: "https://orsela.github.io" };
    if (jwt) headers.authorization = `Bearer ${jwt}`;
    const res = await h(new Request("https://x.supabase.co/functions/v1/invite-manager", { method: "POST", headers, body: JSON.stringify(body) }));
    return { status: res.status, body: await res.json() };
  }
  return { store, sent, logs, calls, call, ctl };
}

const approveOk = (lang: "he" | "en", revoked: string | null = null): Rpc => (name) =>
  name === "request_approve"
    ? { invite_id: INV, expires_at: EXP, revoked_invite_id: revoked, email: "tom@example.co.uk", name: "Tom Baker", lang, draft_name: "Portugal" }
    : name === "request_approve_undo" ? { ok: true } : null;

// ---------------------------------------------------------------------------------------------------
// renderInviteEmail: Hebrew byte-identical to alpha.7.2; English template
// ---------------------------------------------------------------------------------------------------
// sha256(JSON.stringify([to, subject, text, html])) of renderInviteEmail() as shipped in 3.0.0-alpha.7.2 (function
// 3.0.0-alpha.4.1, index.ts sha256 4c8b4599…4fd5), computed before any F21 edit for these two inputs.
const HE_CASES = [
  { to: "dana@example.com", inviter: "אור", draftName: "יפן <2027> & \"Co\"", link: "https://orsela.github.io/Lonely_Planner/invite/#invite=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", expiresAt: "2026-11-03T08:00:00Z" },
  { to: "x@example.com", inviter: "מנהל המערכת", draftName: null, link: "https://orsela.github.io/Lonely_Planner/invite/#invite=B", expiresAt: "2026-12-31T23:30:00Z" },
];
const HE_HASHES = [
  "b1b338e8bfa5f20e310089ab9affed800ac141a927227283048a1cb737116729",
  "c57d6924aefec4d83cf1a028f6c29ed38c19b0a601c7af022162ffc4f18a8c4a",
];

Deno.test("F21 version 3.0.0-alpha.8.0", () => {
  eq(FN_VERSION, "3.0.0-alpha.8.0");
});

Deno.test("F21 renderInviteEmail lang he / absent → byte-identical to alpha.7.2 (snapshot hashes)", async () => {
  for (let i = 0; i < HE_CASES.length; i++) {
    const plain = renderInviteEmail(HE_CASES[i]);
    const he = renderInviteEmail({ ...HE_CASES[i], lang: "he", greetName: "ignored" });
    eq(await sha256Hex(JSON.stringify([plain.to, plain.subject, plain.text, plain.html])), HE_HASHES[i], `case ${i} (no lang)`);
    eq(JSON.stringify(he), JSON.stringify(plain), `case ${i} lang he`);
    eq(plain.subject, EMAIL_SUBJECT);
  }
  // an unknown lang falls back to Hebrew too
  eq(JSON.stringify(renderInviteEmail({ ...HE_CASES[0], lang: "fr" })), JSON.stringify(renderInviteEmail(HE_CASES[0])));
});

Deno.test("F21 English invite: subject, LTR, greeting, trip, button, same /invite/ link, Hebrew note, dd/mm/yyyy, escaping, no images", () => {
  const link = LINK_BASE + "T";
  const m = renderInviteEmail({ to: "tom@example.co.uk", inviter: "אור", draftName: "Portugal <& co>", link, expiresAt: EXP, lang: "en", greetName: "Tom" });
  eq(m.subject, EMAIL_SUBJECT_EN);
  eq(m.subject, "Your trip request was approved");
  assert(m.html.includes('lang="en" dir="ltr"') && !m.html.includes('dir="rtl"'), "LTR");
  assert(m.text.startsWith("Hi Tom,") && m.html.includes(">Hi Tom,</h1>"), "greeting");
  assert(m.text.includes('set up the trip "Portugal <& co>"') && m.html.includes("\"Portugal &lt;&amp; co&gt;\"") && !m.html.includes("<& co>"), "trip + escaping");
  assert(m.html.includes(">Accept and set up the trip</a>") && m.html.includes(`href="${link}"`) && m.text.includes(link), "button/link");
  assert(m.text.includes("Heads-up: the setup screens and the app are in Hebrew for now."), "Hebrew note");
  assert(m.text.includes("valid until 03/11/2026") && m.html.includes("valid until 03/11/2026"), "date");
  assert(m.text.includes("Sent by Lonely Planner. Please don't reply to this email."), "footer");
  assert(!/<img|background-image|url\(/i.test(m.html), "no remote images");
  assert(!/[֐-׿]/.test(m.html + m.text), "no Hebrew in the English email (inviter name is not used)");
  const n = renderInviteEmail({ to: "a@b.co", inviter: "x", draftName: null, link, expiresAt: EXP, lang: "en" });
  assert(n.text.startsWith("Hi,") && n.text.includes("set up a new trip"), "no name / no draft");
});

Deno.test("F21 reject email (§5.1): he RTL / en LTR texts, no link, no reason", () => {
  const he = renderRejectEmail({ to: "d@x.co", lang: "he" });
  eq(he.subject, "הבקשה שלך ל-Lonely Planner");
  assert(he.text.startsWith("תודה על ההתעניינות ב-Lonely Planner. כרגע לא נוכל לפתוח את הטיול שלך. אפשר לשלוח בקשה חדשה בעתיד."));
  assert(he.html.includes('dir="rtl"'));
  const en = renderRejectEmail({ to: "t@x.co", lang: "en" });
  eq(en.subject, "Your Lonely Planner request");
  assert(en.text.startsWith(REJECT_TEXT.en.body) && en.html.includes('dir="ltr"'));
  eq(REJECT_TEXT.en.body, "Thanks for your interest in Lonely Planner. We can't open your trip right now. You're welcome to send a new request in the future.");
  for (const m of [he, en]) assert(!/<a\s|https?:\/\//i.test(m.html + m.text), "a link in the reject email");
  eq(renderRejectEmail({ to: "a@b.co" }).subject, he.subject, "default he");
});

// ---------------------------------------------------------------------------------------------------
// approve_request
// ---------------------------------------------------------------------------------------------------
Deno.test("F21 approve/reject refuse non-admins (403) and bad ids (400); no rpc, no mail", async () => {
  const s = setup(approveOk("he"));
  for (const action of ["approve_request", "reject_request"]) {
    for (const jwt of ["jwt-user", null, "garbage"]) {
      const r = await s.call({ action, request_id: REQ, send_mail: true }, jwt);
      eq([r.status, r.body.error], [403, "not_platform_admin"], `${action}/${jwt}`);
    }
    eq((await s.call({ action, request_id: "nope" })).body.error, "invalid_request");
  }
  eq((await s.call({ action: "approve_request", request_id: REQ, draft_name: "x".repeat(81) })).body.error, "invalid_name");
  eq((await s.call({ action: "reject_request", request_id: REQ, send_mail: "yes" })).body.error, "invalid_request");
  eq(s.calls.length, 0);
  eq(s.sent.length, 0);
});

Deno.test("F21 approve_request (he): rpc args with the token's hash, Hebrew email = renderInviteEmail(he), result shape", async () => {
  const s = setup(approveOk("he"));
  const r = await s.call({ action: "approve_request", request_id: REQ, draft_name: "  פורטוגל · אפריל 2027 " });
  eq(r.status, 200);
  eq(r.body, { ok: true, request_id: REQ, invite_id: INV, email: "tom@example.co.uk", draft_name: "פורטוגל · אפריל 2027", expires_at: EXP, lang: "he", revoked_invite_id: null });
  eq(s.calls.length, 1);
  eq(s.calls[0].name, "request_approve");
  const tok = /#invite=([A-Za-z0-9_-]{43})/.exec(s.sent[0].text)![1];
  eq(s.calls[0].args, { p_admin: ADMIN, p_request: REQ, p_token_hash: await sha256Hex(tok), p_draft: "פורטוגל · אפריל 2027", p_inviter: "אור" });
  const expected = renderInviteEmail({ to: "tom@example.co.uk", inviter: "אור", draftName: "פורטוגל · אפריל 2027", link: LINK_BASE + tok, expiresAt: EXP });
  eq(JSON.stringify(s.sent[0]), JSON.stringify(expected), "Hebrew approval email");
  assert(!JSON.stringify(r.body).includes(tok), "token in response");
});

Deno.test("F21 approve_request (en, D11b/D12): English email greeting the requester; revoked id passed through", async () => {
  const s = setup(approveOk("en", OLD));
  const r = await s.call({ action: "approve_request", request_id: REQ, draft_name: "Portugal" });
  eq(r.status, 200);
  eq(r.body.revoked_invite_id, OLD);
  eq(r.body.lang, "en");
  eq(s.sent.length, 1);
  eq(s.sent[0].subject, "Your trip request was approved");
  assert(s.sent[0].text.startsWith("Hi Tom Baker,") && s.sent[0].text.includes(LINK_BASE), "en body");
});

Deno.test("F21 approve_request: request_closed → 409, no mail; rpc failure → 500; empty draft → null", async () => {
  let s = setup(() => ({ error: "request_closed" }));
  let r = await s.call({ action: "approve_request", request_id: REQ, draft_name: "x" });
  eq([r.status, r.body], [409, { error: "request_closed" }]);
  eq(s.sent.length, 0);
  s = setup(() => { throw new Error("db down"); });
  r = await s.call({ action: "approve_request", request_id: REQ });
  eq([r.status, r.body.error], [500, "server_error"]);
  s = setup(approveOk("he"));
  await s.call({ action: "approve_request", request_id: REQ, draft_name: "   " });
  eq(s.calls[0].args.p_draft, null);
});

Deno.test("F21 approve_request: email failure → request_approve_undo(invite, revoked, request) and 502 email_failed (criterion 14)", async () => {
  const s = setup(approveOk("he", OLD), { failMail: true });
  const r = await s.call({ action: "approve_request", request_id: REQ, draft_name: "x" });
  eq([r.status, r.body], [502, { error: "email_failed" }]);
  eq(s.calls.map((c) => c.name), ["request_approve", "request_approve_undo"]);
  eq(s.calls[1].args, { p_invite: INV, p_revoked: OLD, p_request: REQ });
  assert(!s.logs.join("\n").includes("tom@example"), "address leaked into the logs");
});

// ---------------------------------------------------------------------------------------------------
// reject_request
// ---------------------------------------------------------------------------------------------------
Deno.test("F21 reject_request with mail: reject email in the request's language; mail_sent true", async () => {
  const s = setup(() => ({ mail: true, lang: "en", email: "tom@example.co.uk", name: "Tom" }));
  const r = await s.call({ action: "reject_request", request_id: REQ, send_mail: true });
  eq([r.status, r.body], [200, { ok: true, request_id: REQ, mail_sent: true }]);
  eq(s.calls[0], { name: "request_reject", args: { p_admin: ADMIN, p_request: REQ, p_mail: true } });
  eq(s.sent.length, 1);
  eq(s.sent[0].to, "tom@example.co.uk");
  eq(s.sent[0].subject, "Your Lonely Planner request");
});

Deno.test("F21 reject_request: mail fails → ok + mail_skipped email_failed; cap → mail_skipped daily_limit; no mail chosen → no send", async () => {
  let s = setup(() => ({ mail: true, lang: "he", email: "d@x.co", name: "דנה" }), { failMail: true });
  eq((await s.call({ action: "reject_request", request_id: REQ, send_mail: true })).body, { ok: true, request_id: REQ, mail_sent: false, mail_skipped: "email_failed" });
  s = setup(() => ({ mail: false, reason: "daily_limit" }));
  eq((await s.call({ action: "reject_request", request_id: REQ, send_mail: true })).body, { ok: true, request_id: REQ, mail_sent: false, mail_skipped: "daily_limit" });
  eq(s.sent.length, 0);
  s = setup(() => ({ mail: false, reason: "not_requested" }));
  eq((await s.call({ action: "reject_request", request_id: REQ, send_mail: false })).body, { ok: true, request_id: REQ, mail_sent: false });
  eq(s.calls[0].args.p_mail, false);
  eq(s.sent.length, 0);
  s = setup(() => ({ error: "request_closed" }));
  eq((await s.call({ action: "reject_request", request_id: REQ, send_mail: true })).status, 409);
});

// ---------------------------------------------------------------------------------------------------
// resend uses the stored lang; create unchanged
// ---------------------------------------------------------------------------------------------------
Deno.test("F21 resend of an English invite → English email with the requester's name from prefill; Hebrew invite unchanged", async () => {
  const s = setup((name) => name === "find_invite_for_email" ? { found: true, prefill: { name: "Tom", countries: ["PT"], month: null, lang: "en" } } : null);
  const base = { email: "tom@example.co.uk", token_hash: "h", draft_name: "Portugal", inviter_name: "אור", expires_at: EXP, used_at: null, revoked_at: null,
    opened_at: null, send_count: 1, last_sent_at: NOW.toISOString(), created_at: NOW.toISOString() };
  s.store.rows.set(INV, { id: INV, ...base, lang: "en" });
  s.store.rows.set(OLD, { id: OLD, ...base, email: "dana@example.com", token_hash: "h2", draft_name: "יפן", lang: "he" });
  eq((await s.call({ action: "resend", invite_id: INV })).status, 200);
  eq(s.sent[0].subject, "Your trip request was approved");
  assert(s.sent[0].text.startsWith("Hi Tom,"));
  eq(s.calls[0], { name: "find_invite_for_email", args: { p_email: "tom@example.co.uk" } });
  eq((await s.call({ action: "resend", invite_id: OLD })).status, 200);
  const tok = /#invite=([A-Za-z0-9_-]{43})/.exec(s.sent[1].text)![1];
  eq(JSON.stringify(s.sent[1]), JSON.stringify(renderInviteEmail({ to: "dana@example.com", inviter: "אור", draftName: "יפן", link: LINK_BASE + tok,
    expiresAt: s.store.rows.get(OLD)!.expires_at })), "Hebrew resend");
  eq(s.calls.length, 1, "no rpc for a Hebrew resend");
});

Deno.test("F21 create keeps invite_exists (D12 is approval-only) and sends Hebrew", async () => {
  const s = setup(() => null);
  eq((await s.call({ action: "create", email: "a@example.com" })).status, 200);
  eq((await s.call({ action: "create", email: "a@example.com" })).body.error, "invite_exists");
  eq(s.sent[0].subject, EMAIL_SUBJECT);
  eq(s.calls.length, 0);
});

Deno.test("F21 logs: no email, name, token or draft name for approve / reject", async () => {
  const s = setup(approveOk("en", OLD));
  await s.call({ action: "approve_request", request_id: REQ, draft_name: "Portugal" });
  const s2 = setup(() => ({ mail: true, lang: "en", email: "tom@example.co.uk", name: "Tom Baker" }));
  await s2.call({ action: "reject_request", request_id: REQ, send_mail: true });
  const all = s.logs.concat(s2.logs).join("\n");
  const tok = /#invite=([A-Za-z0-9_-]{43})/.exec(s.sent[0].text)![1];
  for (const x of ["tom@", "Tom", "Portugal", tok, "jwt-admin"]) assert(!all.includes(x), "log leaked " + x);
  assert(all.includes("approve_request") && all.includes("reject_request"), "events logged");
});
