"""Lonely Planner dev helper · version 1.0.0 · F23
CHANGE 2026-11-13 F23-DEV-01: new file (no previous version). Regenerates supabase/functions/_shared/countries.ts
(code, Hebrew name, English name) from app/countries.json.   usage: python3 scripts/dev/gen_fn_countries.py [--check]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "supabase" / "functions" / "_shared" / "countries.ts"
HEAD = [
    "// Lonely Planner Edge Functions · shared country list · version 3.0.0-alpha.12 · F23",
    "// CHANGE 2026-11-13 F23-FN-02: new file (no previous version). GENERATED from app/countries.json (code, Hebrew name, English",
    "//   name only) by scripts/dev/gen_fn_countries.py — do not edit by hand; re-run the script when countries.json changes.",
    "//   Used by request-trip: an AI-suggested or picked country must be one of these (F23 C6), and the draft trip name (F21 D16).",
    "export const COUNTRIES: Record<string, { he: string; en: string }> = {",
]


def build():
    rows = sorted(json.loads((ROOT / "app" / "countries.json").read_text(encoding="utf-8")), key=lambda x: x["code"])
    body = ["  %s: { he: %s, en: %s }," % (x["code"], json.dumps(x["he"], ensure_ascii=False), json.dumps(x["en"], ensure_ascii=False)) for x in rows]
    return "\n".join(HEAD + body + ["};", ""])


if __name__ == "__main__":
    text = build()
    if "--check" in sys.argv:
        sys.exit(0 if OUT.read_text(encoding="utf-8") == text else 1)
    OUT.write_text(text, encoding="utf-8")
