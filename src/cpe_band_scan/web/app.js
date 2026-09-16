"use strict";
const { token, copy, defaults, routes } = window.CPE_BAND_SCAN;

const state = {
  device: null, status: null, profiles: [], run: null, results: null, suggestedName: "", profileName: null,
  remember: false,
  // run: the last finished job of either kind. results: the last finished scan, what the tables and
  // the test's band picker read; a test never takes it off the screen.
  scope: "all", speedTest: true, testTarget: "current", testPick: { lte: "", nr: "" }, testMinutes: "2",
  events: [], since: 0, running: false, kind: "", busy: false, pollFailures: 0,
  applying: null,          // {side, name} while an Apply request is in flight
  editing: null,           // {id, name} while a profile row is being renamed
  confirmDelete: null,     // profile id whose Delete was pressed once
  applyFailed: null,       // {side, name, message} when the router refused the last Apply
  live: null,              // the running job's DOM, built once per run and updated in place
};

const MAX_POLL_FAILURES = 3;   // consecutive failed polls before we treat the server as gone
const SCOPES = { all: ["lte", "nr"], lte: ["lte"], nr: ["nr"] };

// ---- plumbing --------------------------------------------------------------
function route(name, id) {
  return routes[name].replace("{id}", encodeURIComponent(id));
}

async function api(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: { "X-CPE-Band-Scan-Token": token, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const failure = new Error(payload.message || payload.error || "");
    failure.code = payload.error;
    throw failure;
  }
  return payload;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "class") node.className = value;
    else if (value !== null && value !== false) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function fill(template, fields) {
  return template.replace(/\{(\w+)\}/g, (_, key) => (fields[key] === undefined ? "" : fields[key]));
}

function labelFor(group, key) {
  const entry = copy[group][key];
  return typeof entry === "string" ? entry : entry.label;
}

function num(value, unit) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  return unit ? `${value} ${unit}` : `${value}`;
}

function minutes(seconds) {
  return Math.max(1, Math.round(seconds / 60));
}

function sameBands(a, b) {
  return a.length === b.length && a.every((band) => b.includes(band));
}

// ---- explanations: a hover on the word, nothing drawn ------------------------------------------
function hint(text, entry) {
  return el("span", entry && entry.help ? { class: "hint", title: entry.help } : {}, text);
}

function help(group, key) {
  return hint(labelFor(group, key), copy[group][key]);
}

function heading(level, text, ...extra) {
  return el(level, { class: "heading" }, el("span", {}, text), ...extra);
}

function field(key, type = "text", value = "") {
  const entry = copy.FIELDS[key];
  const input = el("input", { type, id: key, value, placeholder: entry.placeholder || "" });
  return el("div", { class: "field" },
    el("label", { for: key }, help("FIELDS", key)), input);
}

function choices(key, current, onPick, disabled) {
  const entry = copy.FIELDS[key];
  return el("fieldset", { class: "choices" },
    el("legend", {}, help("FIELDS", key)),
    el("div", { class: "choice-row" },
      Object.entries(entry.options).map(([value, option]) =>
        el("label", { class: "choice" },
          el("input", { type: "radio", name: key, value, disabled,
                        checked: current === value ? "" : null, onchange: () => onPick(value) }),
          hint(option.label, option)))));
}

function toggle(key, checked, onChange, disabled) {
  return el("label", { class: "choice" },
    el("input", { type: "checkbox", id: key, disabled, checked: checked ? "" : null,
                  onchange: (event) => onChange(event.target.checked) }),
    help("FIELDS", key));
}

function action(key, handler, extra = {}) {
  const button = el("button", Object.assign({ onclick: handler, type: "button", title: copy.ACTIONS[key].help }, extra),
                    copy.ACTIONS[key].label);
  return el("span", { class: "action" }, button);
}

function showError(message) {
  const banner = document.getElementById("banner");
  banner.textContent = message || "";
  banner.className = message ? "bad" : "";
  banner.hidden = !message;
}
