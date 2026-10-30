# CHANGE 2026-10-27 F21-DEVCHK-01: new file (no previous version). Dev self-check for the F21 app side (not the QA suite), no
#   network: node --check on every inline <script> of app/index.html; no new duplicate static ids (vs the base ref); protected
#   functions byte-identical to the base ref; APP_VERSION / PT_VERSION = 3.0.0-alpha.8 with a "was '3.0.0-alpha.7.2'" CHANGE
#   comment; the flag REQUEST_FEATURE='on' right after HOME_INSTALL_FEATURE; every changed region (diff hunk vs the base ref)
#   carries a `CHANGE 2026-10-2x F21-…` comment; the only existing lines changed are the two version lines (everything else
#   additive); every F21 hook line is gated by REQ; admin_trip_requests is called only from REQ-gated code; app/sw.js unchanged.
# usage: python3 scripts/dev/f21_static_check.py [base_ref=313eb14 (hotfix 3.0.0-alpha.7.2)]
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f05_static_check import PROTECTED, extract, node_check, scripts  # noqa: E402  (same parsers as F05/F06/F04-HOME)

ROOT = Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else "313eb14"
MARK = re.compile(r"CHANGE 2026-10-(?:2\d|3[01]) F21-[A-Z0-9]+-\d+")
EXP, WAS = "3.0.0-alpha.8", "3.0.0-alpha.7.2"
APPF = "app/index.html"


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT)] + list(a), capture_output=True, text=True).stdout


def main():
    ok = True
    new = (ROOT / APPF).read_text(encoding="utf-8")
    old = git("show", BASE + ":" + APPF)
    assert "const APP_VERSION='%s'" % WAS in old, "base ref %s is not %s" % (BASE, WAS)

    print("node --check:")
    for i, b in enumerate(scripts(new)):
        if b.strip():
            ok &= node_check(b, "%s #%d (%d chars)" % (APPF, i, len(b)))

    print("duplicate static ids:")
    dn = {k for k, v in Counter(re.findall(r'\bid="([A-Za-z][\w-]*)"', new)).items() if v > 1}
    do = {k for k, v in Counter(re.findall(r'\bid="([A-Za-z][\w-]*)"', old)).items() if v > 1}
    print("  base %s, now %s, new %s" % (sorted(do), sorted(dn), sorted(dn - do)))
    ok &= not (dn - do)

    print("protected (byte-identical to %s):" % BASE)
    for n in PROTECTED:
        a, b = extract(old, n), extract(new, n)
        same = a is not None and a == b
        print("  %-22s %s (%s bytes)" % (n, "identical" if same else "CHANGED/MISSING", len(b or "")))
        ok &= same

    vers = [v for v in re.findall(r"const (?:PT|APP)_VERSION='([^']+)'", new) if v[:1].isdigit()]
    was = [bool(re.search(r"const %s_VERSION='%s';\s*/\* CHANGE 2026-10-2\d F21-VER-0\d: was '%s'" % (k, re.escape(EXP), re.escape(WAS)), new))
           for k in ("PT", "APP")]
    print("versions:", vers, "· 'was %s' comments (PT, APP):" % WAS, was)
    ok &= vers == [EXP, EXP] and all(was)

    near = re.search(r"const HOME_INSTALL_FEATURE='on';\n(?:/\*[\s\S]*?\*/\n)?const REQUEST_FEATURE='on';", new)
    print("flag REQUEST_FEATURE='on' (count %d), next to HOME_INSTALL_FEATURE: %s" % (new.count("const REQUEST_FEATURE='on';"), bool(near)))
    ok &= new.count("const REQUEST_FEATURE=") == 1 and bool(near)

    diff = git("diff", "-U0", BASE, "--", APPF)
    text = new.splitlines()
    print("CHANGE markers on every changed region vs %s:" % BASE)
    bad, hunks = [], 0
    for h in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        start, cnt = int(h.group(1)), int(h.group(2) if h.group(2) is not None else 1)
        hunks += 1
        lo, hi = max(0, start - 1 - 3), start - 1 + max(cnt, 1)
        if not any(MARK.search(l) for l in text[lo:hi]):
            bad.append(start)
    print("  %d hunks, unmarked %s" % (hunks, bad or "none"))
    ok &= not bad

    print("existing lines changed (must be only PT_VERSION / APP_VERSION):")
    changed = []
    for hunk in re.split(r"^(?=@@ )", diff, flags=re.M)[1:]:
        minus = [l[1:] for l in hunk.splitlines()[1:] if l.startswith("-")]
        plus = [l[1:] for l in hunk.splitlines()[1:] if l.startswith("+")]
        changed += [m for m in minus if m not in plus]
    for m in changed:
        print("  -", m.strip()[:100])
    ok &= len(changed) == 2 and all(re.match(r"const (PT|APP)_VERSION=", m) for m in changed)

    print("F21 hook lines gated by REQ:")
    added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    hooks = [l for l in added if re.search(r"F21-(ADMIN|CHOOSE|WIZ)-0[1-4]: new line \(", l)]
    ungated = [l.strip()[:90] for l in hooks if not l.lstrip().startswith("if(REQ")]
    print("  %d hook lines, ungated %s" % (len(hooks), ungated or "none"))
    ok &= len(hooks) >= 9 and not ungated
    consts = [l for l in added if l.startswith("const REQ=")]
    good_c = len(consts) == 3 and all("REQUEST_FEATURE==='on'" in l for l in consts)
    print("  REQ constants: %d %s" % (len(consts), "ok" if good_c else "CHECK"))
    ok &= good_c

    calls = [m.start() for m in re.finditer(r"c\.rpc\('admin_trip_requests'\)", new)]
    gated = []
    for pos in calls:
        fn = new.rfind("\nfunction ", 0, pos)
        body = new[fn:pos]
        gated.append("REQ" in body)
    print("admin_trip_requests call sites: %d, gated %s" % (len(calls), gated))
    ok &= len(calls) == 2 and all(gated) and "admin_trip_requests" not in old

    sw = git("diff", "--stat", BASE, "--", "app/sw.js").strip()
    print("app/sw.js unchanged:", not sw)
    ok &= not sw

    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
