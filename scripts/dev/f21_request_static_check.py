# CHANGE 2026-10-27 F21-REQ-STATIC-01: new file (no previous version). Dev self-check for the F21 /request/ page (not the QA
#   suite), no network: node --check on every inline <script>; no duplicate static ids; version comment 3.0.0-alpha.8 with
#   the "new file" CHANGE line; flag REQUEST_FEATURE ('on'|'off') and TURNSTILE_SITE_KEY constants; the only device keys are
#   pt:_device:rq_lang / pt:_device:rq_resume and every storage access goes through the try/catch wrappers; the resume
#   entry is written with {request_id, email, sentAt, lang, v} only (never the code); no supabase-js, no secret key, only the
#   allowed external URLs; the in-app detection is a marked copy of /invite/'s (same UA regexes).
# usage: python3 scripts/dev/f21_request_static_check.py
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f05_static_check import node_check, scripts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print("  %s %s%s" % ("ok  " if cond else "FAIL", name, "" if cond else "  :: " + str(detail)[:300]))


def main():
    src = (ROOT / "request" / "index.html").read_text(encoding="utf-8")
    inv = (ROOT / "invite" / "index.html").read_text(encoding="utf-8")
    js = "\n".join(scripts(src))

    print("node --check:")
    blocks = [b for b in scripts(src) if b.strip()]
    check("inline script blocks found", len(blocks) >= 1, len(blocks))
    for i, b in enumerate(blocks):
        results.append(node_check(b, "request/index.html #%d (%d chars)" % (i, len(b))))

    print("ids:")
    html = re.sub(r"<script\b.*?</script>", "", src, flags=re.S)
    ids = re.findall(r'\bid="([A-Za-z][\w-]*)"', html)
    dup = sorted(k for k, v in Counter(ids).items() if v > 1)
    check("no duplicate static ids in the markup (%d)" % len(ids), not dup, dup)
    # screen templates in the script are painted one at a time (paint() replaces #rqApp); per-screen uniqueness is checked
    # at runtime by f21_request_smoke.py on every screen.

    print("version / markers:")
    check("version comment 3.0.0-alpha.8", re.search(r"request page · version 3\.0\.0-alpha\.8\b", src) is not None)
    check("CHANGE 2026-10-27 F21-REQ-01: new file (no previous version)", "CHANGE 2026-10-27 F21-REQ-01: new file (no previous version)" in src)
    marks = re.findall(r"CHANGE 2026-10-\d\d (F21-[A-Z0-9-]+)", src)
    check("every CHANGE marker is F21-REQ-*", marks and all(m.startswith("F21-REQ-") for m in marks), marks)
    check("flag REQUEST_FEATURE ('on'|'off')", re.search(r"const REQUEST_FEATURE='(on|off)';", src) is not None)
    m = re.search(r"const TURNSTILE_SITE_KEY='([^']*)';", src)
    check("TURNSTILE_SITE_KEY constant", m is not None and re.match(r"^[0-9x][A-Za-z0-9_-]{10,}$", m.group(1) or ""), m and m.group(1))
    check("site-key comment names the deploy step", re.search(r"Or\s+replaces it with the real site key|real site key", src) is not None)

    print("storage:")
    keys = sorted(set(re.findall(r"'(pt:[^']*)'", js)))
    check("device keys exactly rq_lang + rq_resume", keys == ["pt:_device:rq_lang", "pt:_device:rq_resume"], keys)
    raw = re.findall(r"localStorage\.\w+\(", js)
    check("localStorage used only inside the three try/catch wrappers", len(raw) == 3, raw)
    for fn in ("lsGet", "lsSet", "lsDel"):
        check("%s wraps storage in try/catch" % fn, re.search(r"function %s\([^)]*\)\{try\{(?:return )?localStorage\." % fn, js) is not None)
    check("no sessionStorage / IndexedDB", "sessionStorage" not in js and "indexedDB" not in js)
    w = re.search(r"function writeResume\(\)\{(.*?)\}\n", js)
    body = w.group(1) if w else ""
    fields = re.findall(r"(\w+):", re.search(r"JSON\.stringify\(\{(.*?)\}\)", body).group(1)) if w else []
    check("resume entry fields = request_id,email,sentAt,lang,v", fields == ["request_id", "email", "sentAt", "lang", "v"], fields)
    check("resume never mentions the code", "code" not in body.lower(), body)

    print("network / secrets:")
    urls = sorted(set(re.findall(r"https?://[^'\"\s)<>]+", js)))
    allowed = ("https://zwufpxnioqaweobnvffs.supabase.co", "https://challenges.cloudflare.com/turnstile/v0/api.js")
    bad = [u for u in urls if not u.startswith(allowed)]
    check("external URLs only supabase + Turnstile", not bad, bad)
    check("countries from ../app/countries.json", "'../app/countries.json'" in js)
    check("no supabase-js", "supabase-js@" not in src and "createClient(" not in src and "/npm/@supabase" not in src)
    check("no secret key material", not re.search(r"sb_secret_|service_role|TURNSTILE_SECRET\s*=|eyJhbGciOi", src))
    check("fetch only to FN_URL and countries", sorted(set(re.findall(r"fetch\((\w+)", js))) == ["COUNTRIES_URL", "FN_URL"],
          re.findall(r"fetch\((\w+)", js))
    check("request-trip endpoint", "/functions/v1/request-trip'" in js)

    print("in-app copy of /invite/:")
    check("marked 'copy of /invite/ inApp()'", re.search(r"CHANGE 2026-10-27 F21-REQ-\d+, copy of /invite/ inApp\(\)", src) is not None)
    for name in ("IS_IOS", "IS_ANDROID", "IN_APP"):
        a = re.search(r"%s=([^;]+);" % name, inv)
        b = re.search(r"%s=([^;]+);" % name, js)
        check("%s detection identical to /invite/" % name, a and b and a.group(1) == b.group(1), (a and a.group(1), b and b.group(1)))

    print("layout guards:")
    check("viewport meta", 'name="viewport" content="width=device-width,initial-scale=1"' in src)
    check("email input LTR", re.search(r'id="rqEmail"[^>]*dir="ltr"', src) is not None)
    check("OTP row LTR", ".rq-otp-row{display:flex;gap:8px;direction:ltr" in src)

    print("\n%d/%d checks passed" % (sum(results), len(results)))
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
