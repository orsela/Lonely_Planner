# Lonely Planner · dev self-check for the hotfix 3.0.0-alpha.7.2 · version 1.0.0
# CHANGE 2026-10-26 FIX-DEVCHK-01: new file (no previous version). No network. Against the base ref (default d148d74 =
#   alpha.7.1 + QA-DEBT tests): node --check on every inline <script> of app/, invite/, join/; protected functions
#   byte-identical; APP_VERSION / PT_VERSION and the /invite/ + /join/ version comments = tests/qa_versions.json "app";
#   every changed region (diff hunk) carries a `CHANGE 2026-10-26 FIX-…` comment inside the hunk or in the 3 lines above.
# usage: python3 scripts/dev/fix772_static_check.py [base_ref=d148d74]
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from f05_static_check import PROTECTED, extract, node_check, scripts  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else "d148d74"
FILES = ["app/index.html", "invite/index.html", "join/index.html"]
MARK = re.compile(r"CHANGE 2026-10-2\d FIX-[A-Z0-9-]+")
EXP = json.loads((ROOT / "tests" / "qa_versions.json").read_text())["app"]


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT)] + list(a), capture_output=True, text=True).stdout


def main():
    ok = True
    new = {f: (ROOT / f).read_text(encoding="utf-8") for f in FILES}
    old = {f: git("show", BASE + ":" + f) for f in FILES}
    print("node --check:")
    for f in FILES:
        for i, b in enumerate(scripts(new[f])):
            if b.strip():
                ok &= node_check(b, "%s #%d" % (f, i))
    print("protected (byte-identical to %s):" % BASE)
    for n in PROTECTED:
        same = extract(new["app/index.html"], n) == extract(old["app/index.html"], n)
        print("  %-20s %s" % (n, "ok" if same else "CHANGED"))
        ok &= same
    vers = [v for v in re.findall(r"const (?:PT|APP)_VERSION='([^']+)'", new["app/index.html"]) if v[:1].isdigit()]
    inv = re.search(r"invite page · version (\S+)", new["invite/index.html"])
    jn = re.search(r"join page · version (\S+)", new["join/index.html"])
    v_ok = vers == [EXP, EXP] and inv and inv.group(1) == EXP and jn and jn.group(1) == EXP
    print("versions: app %r · invite %s · join %s · expected %s → %s" % (vers, inv and inv.group(1), jn and jn.group(1), EXP, "ok" if v_ok else "BAD"))
    ok &= bool(v_ok)
    print("CHANGE FIX-… marker on every changed region vs %s:" % BASE)
    for f in FILES:
        diff = git("diff", "-U0", BASE, "--", f)
        lines = new[f].split("\n")
        bad = []
        for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
            start, cnt = int(m.group(1)), int(m.group(2) or 1)
            if cnt == 0:
                continue
            win = "\n".join(lines[max(0, start - 4):start - 1 + cnt])
            if not MARK.search(win):
                bad.append(start)
        print("  %-18s unmarked %s" % (f, bad or "none"))
        ok &= not bad
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
