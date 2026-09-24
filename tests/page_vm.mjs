// Runs page scripts in a vm context with a stub DOM and a recording fetch. Reads one JSON spec on
// stdin (tests/page.py writes it) and prints {result, requests, banner} as JSON.
import vm from "node:vm";
import { readFileSync } from "node:fs";

const spec = JSON.parse(readFileSync(0, "utf8"));
const requests = [];

class Element {
  constructor(tag) {
    Object.assign(this, { tagName: tag, nodeType: 1, children: [], attributes: {}, listeners: {},
                          textContent: "", className: "", hidden: false, disabled: false });
  }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  addEventListener(type, handler) { (this.listeners[type] ||= []).push(handler); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
}

const byId = {};
const document = {
  createElement: (tag) => new Element(tag),
  createTextNode: (text) => ({ nodeType: 3, textContent: text }),
  getElementById: (id) => (byId[id] ||= new Element("div")),
};

async function fetch(path, init) {
  requests.push({ method: init.method, path, body: init.body === undefined ? null : JSON.parse(init.body) });
  const answer = spec.responses[`${init.method} ${path}`] || { status: 200, body: {} };
  return { ok: answer.status < 400, json: async () => answer.body };
}

const context = vm.createContext({ window: { CPE_BAND_SCAN: spec.bootstrap }, document, fetch, console });
for (const file of spec.files) vm.runInContext(readFileSync(file, "utf8"), context, { filename: file });
const result = await vm.runInContext(`(async () => { ${spec.script} })()`, context);
process.stdout.write(JSON.stringify({ result: result ?? null, requests, banner: byId.banner ? byId.banner.textContent : "" }));
