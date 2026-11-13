// Lonely Planner Edge Functions · shared approval module · version 3.0.0-alpha.12 · F23
// CHANGE 2026-11-13 F23-FN-01: new file (no previous version). The part of "approve a trip request" that both
//   invite-manager (admin action approve_request, F21) and request-trip (auto-approval right after the email code, F23 C1)
//   run — one implementation, called in-process (never an HTTP call between the functions):
//     newInviteToken()      a fresh invite token + the hash that is stored
//     sendApprovalInvite()  the invite email of an approved request, in the request's language, with the /invite/ link
//     draftTripName()       F21 D16 draft trip name ("<countries> · <month>") in the request's language
//   This file imports nothing from the functions (they pass their own renderer / link builder / mailer), so it can be
//   deployed next to either of them without a circular import. The database half of the approval is the SQL transaction
//   (public.request_approve for the admin, private.f23_auto_approve for the automatic path, 0020_f23.sql).

export interface ApprovalMail {
  to: string;
  subject: string;
  text: string;
  html: string;
}

export interface ApprovalIo {
  sendMail(m: ApprovalMail): Promise<void>;
  /** invite-manager's renderInviteEmail */
  render(p: { to: string; inviter: string; draftName: string | null; link: string; expiresAt: string; lang?: string; greetName?: string | null }): ApprovalMail;
  /** invite-manager's inviteLink */
  link(appUrl: string, token: string): string;
}

export interface ApprovalInvite {
  appUrl: string;
  token: string;
  email: string;
  inviter: string;
  draftName: string | null;
  expiresAt: string;
  lang: "he" | "en";
  /** requester name for the English greeting; ignored for Hebrew */
  greetName: string | null;
}

function b64url(bytes: Uint8Array): string {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

async function sha256(s: string): Promise<string> {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  return Array.from(d, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** 32 random bytes → 43-char base64url token (same format as invite-manager's makeToken) + its SHA-256 hex. */
export async function newInviteToken(random: (n: number) => Uint8Array): Promise<{ token: string; hash: string }> {
  const token = b64url(random(32));
  return { token, hash: await sha256(token) };
}

/** Sends the invite email of an approved request. Hebrew: exactly the F03 call (no lang / greetName keys), so the email
 *  is byte-identical to a plain manager invite; English: the F21 English template with the requester's name. Throws what
 *  the mailer throws — the caller decides what a failed send means (admin: undo; auto: keep the invite, C4). */
export async function sendApprovalInvite(io: ApprovalIo, p: ApprovalInvite): Promise<void> {
  const link = io.link(p.appUrl, p.token);
  await io.sendMail(p.lang === "en"
    ? io.render({ to: p.email, inviter: p.inviter, draftName: p.draftName, link, expiresAt: p.expiresAt, lang: "en", greetName: p.greetName })
    : io.render({ to: p.email, inviter: p.inviter, draftName: p.draftName, link, expiresAt: p.expiresAt }));
}

const MONTHS = {
  he: ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"],
  en: ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
} as const;

/** F21 D16 (docs/F21_spec.md §5.2), same rule as the app's approve sheet: first two countries joined with " ו" / " & ",
 *  " ועוד N" / " +N" when more, " · <month year>" when a month exists; cut to 80 characters. */
export function draftTripName(
  countries: string[], month: string | null | undefined, lang: string, names: Record<string, { he: string; en: string }>,
): string {
  const l = lang === "en" ? "en" : "he";
  const cs = Array.isArray(countries) ? countries : [];
  let s = cs.slice(0, 2).map((c) => names[String(c).toUpperCase()]?.[l] || String(c).toUpperCase()).join(l === "en" ? " & " : " ו");
  if (cs.length > 2) s += l === "en" ? ` +${cs.length - 2}` : ` ועוד ${cs.length - 2}`;
  const m = /^(\d{4})-(\d{2})/.exec(String(month || ""));
  if (m && +m[2] >= 1 && +m[2] <= 12) s += (s ? " · " : "") + `${MONTHS[l][+m[2] - 1]} ${m[1]}`;
  return s.slice(0, 80);
}
