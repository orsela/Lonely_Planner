# CHANGE 2026-10-22 F06-DEVCHK-01: new file (no previous version). Dev self-check (not the QA suite), no network:
#   node --check on every inline <script> of app/index.html + join/index.html + join/flow.js, no new duplicate static ids
#   (vs the base ref), protected functions byte-identical to the base ref, versions = 3.0.0-alpha.7, the count of removed /
#   changed existing lines in app/index.html, and: every changed region (diff hunk vs the base ref) in the F06 files carries a
#   `CHANGE 2026-10-2x F06-…` comment (inside the hunk or in the 3 lines above it; a new file anywhere in it).
# usage: python3 scripts/dev/f06_static_check.py [base_ref=main]
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f05_static_check import PROTECTED, extract, node_check, scripts  # noqa: E402  (same parsers as F05)

ROOT = Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else "main"
MARK = re.compile(r"CHANGE 2026-10-2\d F06-[A-Z]+")
SKIP = ("docs/F06_spec.md",)   # the approved contract (committed before development)


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT)] + list(a), capture_output=True, text=True).stdout


def main():
    ok = True
    new = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    old = git("show", BASE + ":app/index.html")

    print("node --check:")
    for i, b in enumerate(scripts(new)):
        if b.strip():
            ok &= node_check(b, "app inline script %d (%d chars)" % (i, len(b)))
    for b in scripts((ROOT / "join" / "index.html").read_text(encoding="utf-8")):
        ok &= node_check(b, "join/index.html inline")
    ok &= node_check((ROOT / "join" / "flow.js").read_text(encoding="utf-8"), "join/flow.js")

    from collections import Counter
    for path in ["app/index.html", "join/index.html"]:
        n, o = (ROOT / path).read_text(encoding="utf-8"), git("show", BASE + ":" + path)
        dn = {k for k, v in Counter(re.findall(r'\bid="([A-Za-z][\w-]*)"', n)).items() if v > 1}
        do = {k for k, v in Counter(re.findall(r'\bid="([A-Za-z][\w-]*)"', o)).items() if v > 1}
        print("duplicate static ids %-16s base %s, now %s, new %s" % (path, sorted(do), sorted(dn), sorted(dn - do)))
        ok &= not (dn - do)

    print("protected (byte-identical to %s):" % BASE)
    for n in PROTECTED:
        a, b = extract(old, n), extract(new, n)
        same = a is not None and a == b
        print("  %-22s %s (%s bytes)" % (n, "identical" if same else "CHANGED/MISSING", len(b or "")))
        ok &= same

    vers = [v for v in re.findall(r"const (?:PT|APP)_VERSION='([^']+)'", new) if v[:1].isdigit()]   # skip the update-check regex
    print("versions:", vers)
    ok &= vers == ["3.0.0-alpha.7", "3.0.0-alpha.7"]

    rem = [l for l in git("diff", "-U0", BASE, "--", "app/index.html").splitlines() if l.startswith("-") and not l.startswith("---")]
    print("existing lines removed/changed in app/index.html vs %s: %d" % (BASE, len(rem)))
    for l in rem:
        print("   ", l[:150])

    print("CHANGE markers on every changed region vs %s:" % BASE)
    files = [f for f in git("diff", "--name-only", BASE).split() if f not in SKIP]
    added = set(git("diff", "--name-only", "--diff-filter=A", BASE).split())
    for f in files:
        p = ROOT / f
        if not p.exists():
            print("  %-56s deleted" % f)
            continue
        text = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if f in added and f.endswith(".json"):
            print("  %-56s new file, JSON (no comments possible) — exempt" % f)
            continue
        if f in added:
            good = any(MARK.search(l) for l in text)
            print("  %-56s new file, marker %s" % (f, "yes" if good else "MISSING"))
            ok &= good
            continue
        bad = []
        hunks = 0
        for h in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", git("diff", "-U0", BASE, "--", f), re.M):
            start, cnt = int(h.group(1)), int(h.group(2) if h.group(2) is not None else 1)
            hunks += 1
            lo = max(0, start - 1 - 3)
            hi = start - 1 + max(cnt, 1)
            if not any(MARK.search(l) for l in text[lo:hi]):
                bad.append(start)
        print("  %-56s %d hunks, unmarked %s" % (f, hunks, bad or "none"))
        ok &= not bad
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
