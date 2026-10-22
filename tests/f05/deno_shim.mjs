// Plan_Travel F05 QA · Deno surface shim for scripts/dev/deno_test_node.mjs · version 1.0.0
// CHANGE 2026-10-19 F05-QA-04: first version (no previous version). Loaded with `node --import tests/f05/deno_shim.mjs`
//   BEFORE the dev runner. The runner assigns `globalThis.Deno = {test, env:{get}, serve}`; this shim intercepts that
//   assignment and adds what older Deno tests need: Deno.env.set / delete / toObject (tests/f04/function_test.ts) and a
//   loopback-only Deno.listen / Deno.connect (invite-manager's SMTP dialogue test, 127.0.0.1 only). No other change.
import net from "node:net";

function wrapSocket(sock) {
  const queue = [];
  let ended = false, waiter = null;
  sock.on("data", (b) => { queue.push(new Uint8Array(b)); if (waiter) { const w = waiter; waiter = null; w(); } });
  const done = () => { ended = true; if (waiter) { const w = waiter; waiter = null; w(); } };
  sock.on("end", done); sock.on("close", done); sock.on("error", done);
  return {
    async read(buf) {
      while (!queue.length && !ended) await new Promise((r) => (waiter = r));
      if (!queue.length) return null;
      const c = queue[0];
      const n = Math.min(buf.length, c.length);
      buf.set(c.subarray(0, n));
      if (n < c.length) queue[0] = c.subarray(n); else queue.shift();
      return n;
    },
    write(bytes) { return new Promise((res, rej) => sock.write(Buffer.from(bytes), (e) => (e ? rej(e) : res(bytes.length)))); },
    close() { sock.end(); sock.destroy(); },
  };
}

function extend(d) {
  if (!d || d.__qaShim) return d;
  const env = d.env || {};
  env.get = env.get || ((k) => process.env[k]);
  env.set = (k, v) => { process.env[k] = String(v); };
  env.delete = (k) => { delete process.env[k]; };
  env.toObject = () => ({ ...process.env });
  d.env = env;
  d.listen = ({ hostname = "127.0.0.1", port = 0 } = {}) => {
    if (hostname !== "127.0.0.1") throw new Error("qa shim: loopback only");
    const srv = net.createServer();
    const pending = [], waiters = [];
    srv.on("connection", (s) => { const c = wrapSocket(s); if (waiters.length) waiters.shift()(c); else pending.push(c); });
    // Deno.listen is synchronous and exposes addr at once: port 0 → a random high loopback port chosen here
    const addr = { port: port || 20000 + Math.floor(Math.random() * 40000) };
    const ready = new Promise((r) => srv.listen(addr.port, hostname, r));
    return {
      get addr() { return { transport: "tcp", hostname, port: addr.port }; },
      async accept() { await ready; return pending.length ? pending.shift() : new Promise((r) => waiters.push(r)); },
      close() { srv.close(); },
      __ready: ready,
    };
  };
  d.connect = async ({ hostname = "127.0.0.1", port }) => {
    if (hostname !== "127.0.0.1") throw new Error("qa shim: loopback only");
    for (let i = 0; ; i++) {
      try {
        return await new Promise((res, rej) => { const s = net.connect(port, hostname, () => res(wrapSocket(s))); s.on("error", rej); });
      } catch (e) { if (i > 20) throw e; await new Promise((r) => setTimeout(r, 25)); }
    }
  };
  d.__qaShim = true;
  return d;
}

let cur;
Object.defineProperty(globalThis, "Deno", {
  configurable: true,
  get() { return cur; },
  set(v) { cur = extend(v); },
});
