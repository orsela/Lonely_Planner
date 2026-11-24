// Lonely Planner F13 · coverage report: Hebrew string literals with no entry in app/i18n/en.json · version 3.0.0-alpha.17.2
// CHANGE 2026-11-24 F13-QA-01: new file (no previous version). Scans the files of the spec §1 table (comments stripped), pulls every string literal / attribute /
//   markup text node that holds Hebrew, normalises interpolations to {} and checks it against the catalog (exact entry, or a pattern). Report only: exit 0 unless --strict.
//   Super-admin screens and the legal pages stay Hebrew by decision D2: they are listed under "excluded" and never counted as gaps.
// Run: node tests/f13/coverage.mjs [--json] [--strict] [--files a,b]      (no network)
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const HEB = /[\u0590-\u05FF]/;
const args = process.argv.slice(2);
const JSON_OUT = args.includes("--json"), STRICT = args.includes("--strict");
const filesArg = (args.find(a => a.startsWith("--files=")) || "").slice(8);

const SURFACES = [
  ["app/index.html", "app"], ["join/flow.js", "join"], ["join/index.html", "join"], ["invite/index.html", "invite"],
  ...(existsSync(path.join(REPO, "app/js")) ? readdirSync(path.join(REPO, "app/js")).filter(f => f.endsWith(".js") && f !== "f13.js").map(f => ["app/js/" + f, "app/js"]) : []),
];
const EXCLUDED = [["teaser/index.html", "legal/teaser"], ["privacy/index.html", "legal"], ["terms/index.html", "legal"], ["request/index.html", "already bilingual"]];

export function stripComments(t, kind) {
  t = t.replace(/<!--[\s\S]*?-->/g, "");
  if (kind !== "json") {
    t = t.replace(/\/\*[\s\S]*?\*\//g, "");
    t = t.replace(/(^|[^:"'\\])\/\/[^\n]*/g, "$1");
  }
  return t;
}
/* a literal's text with the JS interpolations replaced by {} and entities/escapes left as they are */
export function normalise(s) {
  return s.replace(/\$\{[^}]*\}/g, "{}").replace(/\s+/g, " ").trim();
}
export function extract(text, kind) {
  const t = stripComments(text, kind), out = new Set();
  const lit = /(["'`])((?:\\[\s\S]|(?!\1)[^\\\n])*?)\1/g;   /* single-line literals (template literals included, newlines excluded) */
  let m;
  while ((m = lit.exec(t))) { if (HEB.test(m[2])) out.add(normalise(m[2])); }
  if (kind === "html") {
    const nodes = />([^<>]*[\u0590-\u05FF][^<>]*)</g;
    while ((m = nodes.exec(t))) out.add(normalise(m[1]));
  }
  return [...out].filter(s => HEB.test(s));
}
export function covered(str, catalog) {
  const ex = catalog.exact || {};
  if (Object.prototype.hasOwnProperty.call(ex, str)) return true;
  const sample = str.replace(/\{\}/g, "X");
  for (const p of catalog.patterns || []) {
    const re = new RegExp("^" + String(p.he).split(/(\{[a-zA-Z0-9_]+\})/).map(x => /^\{.*\}$/.test(x) ? "[\\s\\S]+?" : x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("") + "$");
    if (re.test(sample) || re.test(str)) return true;
  }
  return false;
}

const catalog = JSON.parse(readFileSync(path.join(REPO, "app/i18n/en.json"), "utf8"));
const only = filesArg ? new Set(filesArg.split(",")) : null;
const rows = [];
let total = 0, gaps = 0;
for (const [f, surface] of SURFACES) {
  if (only && !only.has(f)) continue;
  const p = path.join(REPO, f); if (!existsSync(p)) continue;
  const kind = f.endsWith(".html") ? "html" : "js";
  const lits = extract(readFileSync(p, "utf8"), kind);
  const miss = lits.filter(s => !covered(s, catalog));
  rows.push({ file: f, surface, literals: lits.length, missing: miss.length });
  total += lits.length; gaps += miss.length;
}
if (JSON_OUT) console.log(JSON.stringify({ total, gaps, rows, excluded: EXCLUDED.map(e => e[0]) }, null, 1));
else {
  console.log("F13 coverage · catalog exact=%d patterns=%d keys=%d", Object.keys(catalog.exact || {}).length, (catalog.patterns || []).length, Object.keys(catalog.keys || {}).length);
  for (const r of rows.sort((a, b) => b.missing - a.missing)) console.log("%s %s %s", r.file.padEnd(28), String(r.literals).padStart(5) + " literals", String(r.missing).padStart(5) + " without English");
  console.log("TOTAL %d literals · %d without English · excluded by decision D2: %s", total, gaps, EXCLUDED.map(e => e[0]).join(", "));
}
process.exit(STRICT && gaps ? 1 : 0);
