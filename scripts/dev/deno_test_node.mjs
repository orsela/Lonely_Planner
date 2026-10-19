// CHANGE 2026-10-19 F05-DEVFN-01: new file (no previous version). Dev/QA helper for sandboxes WITHOUT a Deno binary (the
//   package registries are blocked there): runs a Deno-style test file (Deno.test + an import of "./index.ts") on Node 22
//   with --experimental-strip-types. It maps `npm:@supabase/supabase-js@…` to the function's offline stub
//   (test_stubs/supabase_js.ts) and provides the tiny Deno surface the functions and tests use (Deno.test, Deno.env.get,
//   Deno.serve). Not a Deno replacement: when `deno` is available, prefer
//     deno test --allow-env --no-check --import-map=<fn>/test_import_map.json <fn>/test.ts
//
// usage: node --experimental-strip-types --no-warnings scripts/dev/deno_test_node.mjs supabase/functions/<fn>/test.ts [...]
import { register } from "node:module";
import { pathToFileURL } from "node:url";
import path from "node:path";

const hooks = `
export async function resolve(spec, ctx, next) {
  if (spec.startsWith("npm:@supabase/supabase-js")) {
    return next(new URL("./test_stubs/supabase_js.ts", ctx.parentURL).href, ctx);
  }
  return next(spec, ctx);
}`;
register("data:text/javascript," + encodeURIComponent(hooks), import.meta.url);

const tests = [];
globalThis.Deno = {
  test(name, fn) {
    if (typeof name === "object") tests.push({ name: name.name, fn: name.fn });
    else tests.push({ name, fn });
  },
  env: { get: (k) => process.env[k] },
  serve() { throw new Error("Deno.serve is not available in unit tests"); },
};

let pass = 0, failN = 0;
for (const f of process.argv.slice(2)) {
  tests.length = 0;
  const origLog = console.log;
  await import(pathToFileURL(path.resolve(f)).href);
  console.log(`# ${f}`);
  for (const t of tests) {
    const logs = [];
    console.log = (...a) => logs.push(a.join(" "));
    try {
      await t.fn();
      console.log = origLog;
      console.log(`  ok   ${t.name}`);
      pass++;
    } catch (e) {
      console.log = origLog;
      console.log(`  FAIL ${t.name}\n       ${String(e && e.stack || e).split("\n").slice(0, 3).join("\n       ")}`);
      failN++;
    }
  }
}
console.log(`${pass}/${pass + failN} pass`);
process.exit(failN ? 1 : 0);
