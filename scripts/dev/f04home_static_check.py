# CHANGE 2026-10-26 F04H-DEVCHK-01: new file (no previous version). Dev self-check for F04-HOME (not the QA suite), no
#   network: node --check on every inline <script> of app/index.html and invite/index.html; no new duplicate static ids
#   (vs the base ref); protected functions byte-identical to the base ref; APP_VERSION / PT_VERSION = 3.0.0-alpha.7.1 and the
#   /invite/ version comment alpha.7.1; the flag HOME_INSTALL_FEATURE='on' in both files (app: next to MEMBERS_FEATURE);
#   every changed region (diff hunk vs the base ref) carries a `CHANGE 2026-10-26 F04H-…` comment (inside the hunk or in the
#   3 lines above it); flag-off sanity: every existing line that was changed is replaced by a hunk that is gated
#   (HOMEI / HOME_INSTALL_FEATURE) or is a version / exported-object line; the resume key is never written with a code/token.
# usage: python3 scripts/dev/f04home_static_check.py [base_ref=origin/main]
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f05_static_check import PROTECTED, extract, node_check, scripts  # noqa: E402  (same parsers as F05/F06)

ROOT = Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
MARK = re.compile(r"CHANGE 2026-10-2\d F04H-[A-Z0-9]+")
FILES = ["app/index.html", "invite/index.html"]
GATED = re.compile(r"HOMEI|HOME_INSTALL_FEATURE|_VERSION=|gateTop|resumeBoot|clearResume|NOTE_BTN")


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT)] + list(a), capture_output=True, text=True).stdout


def main():
    ok = True
    new = {f: (ROOT / f).read_text(encoding="utf-8") for f in FILES}
    old = {f: git("show", BASE + ":" + f) for f in FILES}
    assert old["app/index.html"], "base ref %s not readable" % BASE

    print("node --check:")
    for f in FILES:
        for i, b in enumerate(scripts(new[f])):
            if b.strip():
                ok &= node_check(b, "%s #%d (%d chars)" % (f, i, len(b)))

    print("duplicate static ids:")
    for f in FILES:
        dn = {k for k, v in Counter(re.findall(r'\bid="([A-Za-z][\w-]*)"', new[f])).items() if v > 1}
        do = {k for k, v in Counter(re.findall(r'\bid="([A-Za-z][\w-]*)"', old[f])).items() if v > 1}
        print("  %-18s base %s, now %s, new %s" % (f, sorted(do), sorted(dn), sorted(dn - do)))
        ok &= not (dn - do)

    print("protected (byte-identical to %s):" % BASE)
    for n in PROTECTED:
        a, b = extract(old["app/index.html"], n), extract(new["app/index.html"], n)
        same = a is not None and a == b
        print("  %-22s %s (%s bytes)" % (n, "identical" if same else "CHANGED/MISSING", len(b or "")))
        ok &= same

    vers = [v for v in re.findall(r"const (?:PT|APP)_VERSION='([^']+)'", new["app/index.html"]) if v[:1].isdigit()]
    iv = re.search(r"invite page · version (\S+)", new["invite/index.html"])
    print("versions: app", vers, "· invite comment", iv and iv.group(1))
    ok &= vers == ["3.0.0-alpha.7.1", "3.0.0-alpha.7.1"] and bool(iv) and iv.group(1) == "3.0.0-alpha.7.1"

    fl = [len(re.findall(r"const HOME_INSTALL_FEATURE='on';", new[f])) for f in FILES]
    near = re.search(r"const MEMBERS_FEATURE='on';\n(?:/\*[\s\S]*?\*/\n)?const HOME_INSTALL_FEATURE='on';", new["app/index.html"])
    print("flag HOME_INSTALL_FEATURE='on': app %d, invite %d, app next to MEMBERS_FEATURE: %s" % (fl[0], fl[1], bool(near)))
    ok &= fl == [1, 1] and bool(near)

    print("CHANGE markers on every changed region vs %s:" % BASE)
    for f in FILES:
        text = new[f].splitlines()
        bad, hunks = [], 0
        for h in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", git("diff", "-U0", BASE, "--", f), re.M):
            start, cnt = int(h.group(1)), int(h.group(2) if h.group(2) is not None else 1)
            hunks += 1
            lo, hi = max(0, start - 1 - 3), start - 1 + max(cnt, 1)
            if not any(MARK.search(l) for l in text[lo:hi]):
                bad.append(start)
        print("  %-18s %d hunks, unmarked %s" % (f, hunks, bad or "none"))
        ok &= not bad

    print("flag-off sanity — existing lines changed vs %s and their replacements:" % BASE)
    for f in FILES:
        diff = git("diff", "-U0", BASE, "--", f)
        for hunk in re.split(r"^(?=@@ )", diff, flags=re.M)[1:]:
            minus = [l[1:] for l in hunk.splitlines()[1:] if l.startswith("-")]
            plus = [l[1:] for l in hunk.splitlines()[1:] if l.startswith("+")]
            if not minus:
                continue
            gated = any(GATED.search(p) for p in plus)
            header = f == "invite/index.html" and all(m.strip().startswith("<!-- Plan_Travel invite page") for m in minus)
            kept = all(m in plus for m in minus)   # diff artefact: the "removed" line is re-added unchanged
            good = gated or header or kept
            how = "gated" if gated else ("header comment" if header else ("kept unchanged (insert before it)" if kept else "UNGATED"))
            print("  %-18s -%d/+%d %s :: %s" % (f, len(minus), len(plus), how, minus[0].strip()[:90]))
            ok &= good

    print("resume key contents (source): written only by writeResume with {email,sentAt,kind,origin,v}:")
    app = new["app/index.html"]
    w = re.findall(r"RAWLS\.set\(RESUME_KEY,([^\n]+)", app)
    good = len(w) == 1 and "email:wz.email,sentAt:wz.sentAt,kind:" in w[0] and "origin:wz.origin,v:1" in w[0] and not re.search(r"token|codeValue|otp", w[0], re.I)
    print("  writes: %d %s" % (len(w), "ok" if good else "CHECK: " + (w[0][:160] if w else "none")))
    ok &= good
    tok_store = re.findall(r"(?:localStorage|sessionStorage)[^\n]{0,80}token", new["invite/index.html"])
    print("  /invite/ token storage writes: %d" % len(tok_store))
    ok &= not tok_store

    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
