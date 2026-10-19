# CHANGE 2026-10-19 F05-DEVCHK-01: new file (no previous version). Dev self-check (not the QA suite), no network:
#   node --check on every inline <script> of app/index.html (HTML comments respected) + join/index.html + join/flow.js,
#   duplicate static ids (vs the base ref), protected functions byte-identical to the base ref, versions, and the list of
#   removed/changed lines vs the base ref (so every edit of an existing line is visible).
# usage: python3 scripts/dev/f05_static_check.py [base_ref=origin/main]
import re
import subprocess
import sys
import tempfile
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
PROTECTED = ["drawMap", "drawGoogleMap", "drawSchematicMap", "fallbackToSchematic", "SEED_DATA", "stayBlock", "bookingUrl"]


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out, self.cur = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "script" and not dict(attrs).get("src"):
            self.cur = []

    def handle_endtag(self, tag):
        if tag == "script" and self.cur is not None:
            self.out.append("".join(self.cur))
            self.cur = None

    def handle_data(self, data):
        if self.cur is not None:
            self.cur.append(data)


def scripts(html):
    p = Scripts()
    p.feed(html)
    return p.out


def node_check(code, label):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(code)
    r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
    print("  %-34s %s" % (label, "OK" if r.returncode == 0 else "FAIL " + r.stderr[:400]))
    return r.returncode == 0


def extract(src, name):
    """Source text of a protected top-level function/const, by brace matching from its declaration."""
    m = re.search(r"(?:async\s+)?function\s+%s\s*\(|const\s+%s\s*=" % (name, name), src)
    if not m:
        return None
    i = src.index("{", m.end()) if "function" in m.group(0) else m.end()
    if "function" not in m.group(0):
        j = m.end()
        while src[j] in " \t":
            j += 1
        i = j
    opener = src[i]
    closer = {"{": "}", "[": "]"}.get(opener)
    if not closer:
        return src[m.start(): src.index("\n", m.end())]
    depth, k, q = 0, i, None
    while k < len(src):
        c = src[k]
        if q:
            if c == "\\":
                k += 2
                continue
            if c == q:
                q = None
        elif c in "'\"`":
            q = c
        elif c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return src[m.start(): k + 1]
        k += 1
    return None


def main():
    ok = True
    new = (ROOT / "app" / "index.html").read_text(encoding="utf-8")
    old = subprocess.run(["git", "-C", str(ROOT), "show", BASE + ":app/index.html"], capture_output=True, text=True).stdout
    print("node --check (app/index.html):")
    for i, b in enumerate(scripts(new)):
        if b.strip():
            ok &= node_check(b, "inline script %d (%d chars)" % (i, len(b)))
    for b in scripts((ROOT / "join" / "index.html").read_text(encoding="utf-8")):
        ok &= node_check(b, "join/index.html inline")
    ok &= node_check((ROOT / "join" / "flow.js").read_text(encoding="utf-8"), "join/flow.js")

    ids_new = Counter(re.findall(r'\bid="([A-Za-z][\w-]*)"', new))
    ids_old = Counter(re.findall(r'\bid="([A-Za-z][\w-]*)"', old))
    dup_new = {k for k, v in ids_new.items() if v > 1}
    dup_old = {k for k, v in ids_old.items() if v > 1}
    print("duplicate static ids: base %s, now %s, new duplicates %s" % (sorted(dup_old), sorted(dup_new), sorted(dup_new - dup_old)))
    ok &= not (dup_new - dup_old)

    print("protected (byte-identical to %s):" % BASE)
    for n in PROTECTED:
        a, b = extract(old, n), extract(new, n)
        same = a is not None and a == b
        print("  %-22s %s (%s bytes)" % (n, "identical" if same else "CHANGED/MISSING", len(b or "")))
        ok &= same

    print("versions:", re.findall(r"const (?:PT|APP)_VERSION='([^']+)'", new))

    ol, nl = old.splitlines(), new.splitlines()
    import difflib
    removed = [l for l in difflib.ndiff(ol, nl) if l.startswith("- ")]
    print("lines removed/changed vs %s: %d" % (BASE, len(removed)))
    for l in removed:
        print("   ", l[:170])
    print("ALL OK" if ok else "FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
