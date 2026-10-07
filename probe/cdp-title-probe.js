// cdp-title-probe.js — drive a Chrome DevTools Protocol target and read the
// fingerprint result from document.title.
//
// Usage:
//   node cdp-title-probe.js <cdpPort> <pageUrl>
//
// Finds an about:blank page target (or creates one), navigates it to pageUrl,
// polls document.title until the probe sets "FPR|{json}", then prints the JSON.
const [, , port, pageUrl] = process.argv;

async function main() {
  const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  let target = list.find(t => t.type === "page" && t.url === "about:blank");
  if (!target) {
    target = await (await fetch(`http://127.0.0.1:${port}/json/new`, { method: "PUT" })).json();
  }
  if (!target || !target.webSocketDebuggerUrl) {
    console.error("NO_TARGET " + JSON.stringify(list.map(t => t.url)));
    process.exit(1);
  }
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const send = (method, params = {}) => new Promise((res, rej) => {
    const mid = ++id;
    pending.set(mid, { res, rej });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { res, rej } = pending.get(m.id);
      pending.delete(m.id);
      m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
    }
  };
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  await send("Page.enable");
  await send("Page.navigate", { url: pageUrl });
  let title = "";
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 500));
    try {
      const r = await send("Runtime.evaluate", { expression: "document.title", returnByValue: true });
      title = r.result.value || "";
      if (title.startsWith("FPR|")) break;
    } catch (e) { /* context destroyed during navigation */ }
  }
  console.log(title.startsWith("FPR|") ? title.slice(4) : "TITLE_NOT_SET:" + title);
  ws.close();
  process.exit(0);
}
main().catch(e => { console.error("ERR " + e.message); process.exit(1); });
