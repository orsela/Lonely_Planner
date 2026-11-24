// Lonely Planner OFFMAP · browser smoke test of the viewer (390px): fake MVT tiles in IndexedDB, Leaflet + protomaps-leaflet from app/vendor, headless Chrome through the DevTools protocol. Run: node tests/offmap/view_smoke_run.mjs. Needs google-chrome; prints OUT and writes /tmp/offmap_view_shot.png. CHANGE 2026-11-24 OFFMAP-T-04: new file (viewer, alpha.20.3).
import http from "node:http"; import fs from "node:fs"; import path from "node:path"; import { spawn } from "node:child_process";
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../.."), URL_ = process.argv[2] || "/tests/offmap/view_smoke.html", WAIT = +(process.argv[3] || 9000);
const srv = http.createServer((q, r) => { const f = path.join(root, decodeURIComponent(q.url.split("?")[0])); fs.readFile(f, (e, b) => { if (e) { r.writeHead(404); r.end(); } else { r.writeHead(200, { "content-type": f.endsWith(".js") ? "text/javascript" : f.endsWith(".css") ? "text/css" : "text/html" }); r.end(b); } }); });
await new Promise(r => srv.listen(8791, "127.0.0.1", r));
const ch = spawn("google-chrome", ["--headless=new", "--no-sandbox", "--disable-gpu", "--remote-debugging-port=9333", "--window-size=390,560", "about:blank"], { stdio: "ignore" });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let tabs; for (let i = 0; i < 30; i++) { try { tabs = await (await fetch("http://127.0.0.1:9333/json")).json(); if (tabs.length) break; } catch (e) {} await sleep(300); }
const ws = new WebSocket(tabs.find(t => t.type === "page").webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const pend = new Map(), logs = [];
ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d.result); pend.delete(d.id); } else if (d.method === "Runtime.consoleAPICalled") logs.push(d.params.args.map(a => a.value ?? a.description).join(" ")); else if (d.method === "Runtime.exceptionThrown") logs.push("EXC " + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text)); };
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send("Runtime.enable"); await send("Page.enable");
await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 560, deviceScaleFactor: 2, mobile: true });
await send("Page.navigate", { url: "http://127.0.0.1:8791" + URL_ }); await sleep(WAIT);
const t = await send("Runtime.evaluate", { expression: "document.getElementById('out')&&document.getElementById('out').textContent", returnByValue: true });
console.log("OUT:", t.result.value); console.log("LOGS:", logs.slice(0, 10).join("\n"));
const s = await send("Page.captureScreenshot", { format: "png" }); fs.writeFileSync("/tmp/offmap_view_shot.png", Buffer.from(s.data, "base64"));
ch.kill(); srv.close(); process.exit(0);
