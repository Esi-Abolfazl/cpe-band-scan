"use strict";
const { token, copy, defaults } = window.CPE_BAND_SCAN;

const state = {
  device: null, status: null, profiles: [], run: null, results: null, suggestedName: "", profileName: null,
  remember: false,
  // run: the last finished job of either kind. results: the last finished scan, what the tables and
  // the test's band picker read; a test never takes it off the screen.
  scope: "all", testTarget: "current", testPick: { lte: "", nr: "" }, testMinutes: "2",
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

// ---- connect ---------------------------------------------------------------
function renderConnect() {
  const view = document.getElementById("view");
  const remember = el("input", { type: "checkbox", id: "remember", checked: state.remember ? "" : null,
                                 onchange: (event) => { state.remember = event.target.checked; } });
  view.className = "connect";
  view.replaceChildren(
    el("div", { class: "card narrow" },
      heading("h2", copy.APP.connect_heading),
      field("router_url", "text", defaults.url),
      defaults.remembered
        ? el("div", { class: "actions" },
            el("span", { class: "note" }, copy.NOTES.password_remembered),
            action("forget", onForget, { class: "quiet" }))
        : el("div", { class: "stack" },
            field("password", "password"),
            el("label", { class: "choice" }, remember, help("FIELDS", "remember"))),
      action("connect", onConnect, { class: "primary", id: "connect" })));
  const password = document.getElementById("password");
  if (password) password.addEventListener("keydown", (event) => { if (event.key === "Enter") onConnect(); });
}

async function onForget() {
  try {
    await api("POST", "/api/forget", {});
    defaults.remembered = false;
  } catch (failure) {
    showError(failure.message);
  }
  render();
}

async function onConnect() {
  showError(null);
  state.busy = true;
  const button = document.getElementById("connect");
  if (button) button.disabled = true;               // in place: a render here would wipe the password
  const password = document.getElementById("password");
  const body = { url: document.getElementById("router_url").value };
  if (password) { body.password = password.value; body.remember = state.remember; }
  try {
    const answer = await api("POST", "/api/connect", body);
    state.device = answer.device;
    state.suggestedName = answer.suggested_name;
    if (password && state.remember) defaults.remembered = true;
    await refreshStatus();
    await refreshProfiles();
  } catch (failure) {
    showError(failure.message);
  } finally {
    state.busy = false;
    if (button) button.disabled = false;
    render();
  }
}

async function refreshStatus() {
  try {
    state.status = await api("GET", "/api/status");
    state.running = state.status.running;
  } catch (failure) {
    showError(failure.message);
  }
}

// ---- status: what the router is doing, one row per network ------------------
function carrierChips(carriers) {
  return carriers.map((carrier, index) => el("span", { class: index ? "chip" : "chip anchor" },
    el("b", {}, carrier.band),
    carrier.width_mhz ? el("span", { class: "muted" }, fill(copy.NOTES.width_mhz, { width: carrier.width_mhz })) : null));
}

function measures(pairs) {
  return el("dl", { class: "measures" }, pairs.map(([label, value, entry]) =>
    el("div", {}, el("dt", {}, hint(label, entry)), el("dd", { class: "num" }, value))));
}

function networkRow(side, carriers, pairs, emptyText) {
  return el("div", { class: "network" },
    el("span", { class: "side" }, copy.SIDES[side]),
    el("div", { class: "network-body" },
      carriers.length ? el("div", { class: "chips" }, carrierChips(carriers)) : el("p", { class: "note" }, emptyText),
      carriers.length ? measures(pairs) : null));
}

function statusCard() {
  const signal = state.status.signal;
  const carriers = signal.carriers || [];
  const lte = carriers.filter((carrier) => carrier.tech === "lte");
  const nr = carriers.filter((carrier) => carrier.tech === "nr");
  return el("div", { class: "card" },
    heading("h2", copy.APP.status_heading),
    networkRow("lte", lte, [
      [copy.NOTES.quality, num(signal.sinr, "dB"), copy.COLUMNS.sinr],
      [copy.NOTES.channel, num(signal.rsrq, "dB"), copy.COLUMNS.rsrq],
      [copy.NOTES.strength, num(signal.rsrp, "dBm"), copy.COLUMNS.rsrp]], copy.NOTES.no_lte_carrier),
    networkRow("nr", nr, [
      [copy.NOTES.quality, num(signal.nrsinr, "dB"), copy.COLUMNS.nr_sinr],
      [copy.NOTES.strength, num(signal.nrrsrp, "dBm"), copy.COLUMNS.rsrp]],
      copy.NOTES.no_5g_carrier));
}

function lockWords(lock) {
  const parts = [];
  for (const side of ["lte", "nr"]) {
    const [anchors, secondaries] = lock[side];
    if (!anchors.length) continue;
    const prefix = side === "nr" ? "N" : "B";
    let words = fill(copy.NOTES.locked_to, { bands: anchors.map((band) => prefix + band).join(", ") });
    if (secondaries.length) {
      words += " " + fill(copy.NOTES.with_secondary, { bands: secondaries.map((band) => prefix + band).join(", ") });
    }
    parts.push(el("p", { class: "lock-line" }, el("span", { class: "side" }, copy.SIDES[side]), words));
  }
  return parts.length ? parts : [el("p", { class: "note" }, copy.NOTES.no_lock)];
}

function lockCard() {
  const idle = !state.running && !state.busy && !state.applying;
  return el("div", { class: "card" },
    heading("h2", copy.APP.lock_heading),
    el("div", { class: "stack" }, lockWords(state.status.lock)),
    el("div", { class: "actions" },
      action("refresh", async () => { await refreshStatus(); render(); }),
      action("clear", onClear, { disabled: !idle })),
    el("p", { class: "note" }, copy.NOTES.lock_survives));
}

async function onClear() {
  try {
    await api("POST", "/api/clear", {});
    await refreshStatus();
  } catch (failure) {
    showError(failure.message);
  }
  render();
}

function deviceLine() {
  const device = state.device;
  return el("p", { class: "device" },
    [device.model, `firmware ${device.firmware}`, device.carrier].filter(Boolean).join(" · "));
}

// ---- scan: the form, then the live progress ---------------------------------
function liveCard(kind) {
  return state.live && state.kind === kind ? state.live.card : null;
}

function scanCard() {
  const disabled = state.running || state.busy;
  return el("div", { class: "card span" },
    heading("h2", copy.APP.scan_heading),
    el("p", { class: "note" }, copy.NOTES.before_scan),
    el("div", { class: "form-row" },
      choices("scan_scope", state.scope, (value) => { state.scope = value; }, disabled),
      action("scan", () => onScan(SCOPES[state.scope]),
             { class: state.results ? "" : "primary", disabled })));
}

// A log line with one coloured word: the {slot} placeholder becomes `node`, or when there is no slot
// the text after the band name is coloured with `tailClass`.
function coloured(template, values, slot, node, tailClass) {
  const text = fill(template, values);
  if (slot) {
    const [before, after] = text.split(`{${slot}}`);
    return el("span", {}, before, node, after);
  }
  const cut = text.indexOf(": ") + 2;
  return el("span", {}, text.slice(0, cut), el("span", { class: tailClass }, text.slice(cut)));
}

function describe(event) {
  const words = copy.PROGRESS;
  switch (event.type) {
    case "set_start":                       // the bar already says "9 of 11 · about 3 min left"
      return fill(words.log_measuring, { name: event.name });
    case "set_result":
      return coloured(words.log_result, { name: event.name, floor: event.result.floor, grade: "{grade}" },
                      "grade", el("span", { class: `grade-${event.result.grade}` }, copy.GRADES[event.result.grade]));
    case "set_skipped":
      return coloured(event.reason === "refused" ? words.log_refused : words.log_skipped, { name: event.name },
                      null, null, "bad-text");
    case "side_start":
      return fill(words.side_start, { side: copy.SIDES[event.side], count: event.total,
                                      minutes: minutes(event.eta_s) });
    case "side_done":
      return fill(words.side_done, { side: copy.SIDES[event.side],
                                     count: Object.keys(event.results).length });
    case "applied":
      return fill(words.applied, { bands: event.plan.lte.map((band) => "B" + band)
                                     .concat(event.plan.nr.map((band) => "N" + band)).join(", ") });
    case "kept_auto": return words.kept_auto;
    case "unchanged": return words.unchanged;
    case "lock_back": return words.lock_back;
    case "lock_lost": return words.lock_lost;
    case "cancelled": return words.cancelled;
    case "trace_start": {
      const locked = state.live && state.live.kind === "test" && state.live.what !== copy.NOTES.test_target_current;
      return fill(locked ? words.trace_start_locked : words.trace_start,
                  { minutes: minutes(event.seconds), name: state.live ? state.live.what : "" });
    }
    case "trace_sample":
      return `${event.at_s}s  ${copy.NOTES.quality} ${num(event.sample.sinr, "dB")}  `
           + `${copy.NOTES.channel} ${num(event.sample.rsrq, "dB")}`;
    case "trace_done": return words.trace_done;
    case "done": return words.done;
    case "error": return event.message || copy.ERRORS[event.code] || "";
    default: return null;
  }
}

// A log panel is built once and appended to: rebuilding it on every poll is what made the
// old page unreadable. Follow is on until the reader scrolls up, or the side is finished.
function logPanel(side) {
  const body = el("div", { class: "log", "data-log": side, tabindex: "0" });
  const follow = el("input", { type: "checkbox", checked: "" });
  const followLabel = el("label", { class: "follow" }, follow, help("FIELDS", "follow"));
  const panel = {
    body, follow, lines: 0,
    node: el("div", { class: "log-panel" },
      el("div", { class: "log-head" },
        el("h3", {}, fill(copy.APP.log_heading, { side: copy.SIDES[side] })),
        followLabel),
      body),
    append(text) {
      body.append(el("div", {}, text));
      panel.lines += 1;
      if (follow.checked) body.scrollTop = body.scrollHeight;
    },
    stop() { follow.checked = false; followLabel.hidden = true; },
  };
  body.addEventListener("scroll", () => {
    const atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 4;
    if (!atBottom && follow.checked) follow.checked = false;
  });
  follow.addEventListener("change", () => { if (follow.checked) body.scrollTop = body.scrollHeight; });
  return panel;
}

function checkIcon() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 16 16"); svg.setAttribute("class", "check"); svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M3 8.5l3 3 7-7"); svg.append(path);
  return svg;
}

function markDone(bar, status, text) {
  bar.hidden = true;
  status.classList.add("done");
  status.replaceChildren(checkIcon(), text);
}

function sideRow(side) {
  const bar = el("progress", { value: 0, max: 1 });
  const status = el("span", { class: "side-status num" }, copy.NOTES.side_waiting);
  return { bar, status,
           node: el("div", { class: "side-row" }, el("span", { class: "side" }, copy.SIDES[side]), bar, status) };
}

function buildScanLive(sides) {
  const rows = {}, logs = {};
  for (const side of sides) { rows[side] = sideRow(side); logs[side] = logPanel(side); }
  const stop = action("cancel", onCancel);
  const card = el("div", { class: "card span live" },
    heading("h2", copy.APP.progress_heading),
    el("div", { class: "side-rows" }, sides.map((side) => rows[side].node)),
    el("div", { class: "logs" }, sides.map((side) => logs[side].node)),
    el("div", { class: "actions" }, stop));
  return { kind: "scan", card, rows, logs, sides, current: sides[0], stop, plan: {} };
}

function buildTestLive(seconds, what) {
  const log = logPanel("trace");
  const bar = el("progress", { value: 0, max: seconds });
  const status = el("p", { class: "num" }, fill(copy.NOTES.test_running, { what, left: `${minutes(seconds)} min` }));
  const stop = action("stop_test", onCancel);
  const card = el("div", { class: "card span live" },
    heading("h2", copy.APP.test_heading), status, bar, log.node, el("div", { class: "actions" }, stop));
  return { kind: "test", card, log, bar, status, seconds, what, stop };
}

function applyEvent(event) {
  const live = state.live;
  if (!live) return;
  const line = describe(event);
  if (live.kind === "test") {
    if (event.type === "trace_sample") {
      live.bar.value = event.at_s;
      const left = live.seconds - event.at_s;
      live.status.textContent = fill(copy.NOTES.test_running,
        { what: live.what, left: left >= 60 ? `${minutes(left)} min` : `${left} s` });
    }
    if (line) live.log.append(line);
    if (event.type === "trace_done") markDone(live.bar, live.status, copy.PROGRESS.trace_done);
    if (event.type === "trace_done" || event.type === "cancelled" || event.type === "finished") live.log.stop();
    return;
  }
  if (event.type === "run_start") {
    live.plan = event.plan || {};
    for (const side of live.sides) {
      const plan = live.plan[side];
      if (plan) live.rows[side].bar.max = plan.total;
    }
  }
  const side = live.rows[event.side] ? event.side : live.current;
  const row = live.rows[side];
  if (event.type === "side_start") {
    live.current = side;
    row.bar.max = event.total;
  }
  if (event.type === "set_start") {
    row.bar.value = event.index - 1;
    row.status.textContent = fill(copy.NOTES.side_running,
      { index: event.index, total: event.total, minutes: minutes(event.eta_s) });
  }
  if (event.type === "side_done") {
    markDone(row.bar, row.status, copy.NOTES.side_done);
    live.logs[side].stop();
  }
  if (event.type === "cancelled") {
    row.status.textContent = copy.NOTES.side_stopped;
    for (const other of live.sides) if (live.rows[other].status.textContent === copy.NOTES.side_waiting) {
      live.rows[other].status.textContent = copy.NOTES.side_skipped;
    }
  }
  if (line) live.logs[side].append(line);
  if (event.type === "finished") for (const log of Object.values(live.logs)) log.stop();
}

function startLive() {
  if (state.kind === "test") {
    const start = state.events.find((event) => event.type === "trace_start");
    state.live = buildTestLive(start ? start.seconds : 120, start && start.lock ? lockedWhat(start.lock) : testWhat());
  } else {
    const start = state.events.find((event) => event.type === "run_start");
    state.live = buildScanLive(start ? start.sides : SCOPES[state.scope]);
  }
  for (const event of state.events) applyEvent(event);
}

function finishLive() {
  if (!state.live) return;
  state.live.stop.hidden = true;
}

async function onScan(sides) {
  showError(null);
  state.events = []; state.since = 0; state.run = null; state.pollFailures = 0;
  state.applyFailed = null;
  try {
    await api("POST", "/api/scan", { sides });
    state.running = true;
    state.kind = "scan";
    state.live = buildScanLive(sides);
    render();
    poll();
  } catch (failure) {
    showError(failure.message);
    render();
  }
}

async function onCancel() {
  try { await api("POST", "/api/cancel", {}); } catch (failure) { showError(failure.message); }
}

async function poll() {
  const answer = await api("GET", `/api/events?since=${state.since}`).catch(() => null);
  if (answer) {
    state.pollFailures = 0;
    state.since = answer.since;
    state.events = state.events.concat(answer.events);
    state.running = answer.running;
    state.kind = answer.kind;
    for (const event of answer.events) {
      if (event.type === "done") state.results = event.run;
      if (event.type === "done" || event.type === "trace_done") state.run = event.run;
      if (event.type === "error") showError(describe(event));
      applyEvent(event);
    }
  } else {
    state.pollFailures += 1;
    if (state.pollFailures >= MAX_POLL_FAILURES) {
      state.running = false;
      showError(copy.ERRORS.crash);
      finishLive();
      return render();
    }
  }
  if (state.running) setTimeout(poll, 2000);
  else { finishLive(); await refreshStatus(); render(); }
}

// ---- results ---------------------------------------------------------------
const COLUMN_KEYS = ["rank", "band", "grade", "five_g", "floor", "sinr", "rsrq", "rsrp",
                     "nr_sinr", "carriers"];

function inUse(side, record, name) {
  const lock = state.status && state.status.lock[side];
  return Boolean(lock && lock[0].length && sameBands(record.sets[name], lock[0]));
}

function applyCell(side, record, name) {
  if (name === "auto") return el("td", {});
  if (inUse(side, record, name)) return el("td", {}, el("span", { class: "badge in-use" }, copy.NOTES.in_use));
  const mine = state.applying && state.applying.side === side && state.applying.name === name;
  const failed = state.applyFailed && state.applyFailed.side === side && state.applyFailed.name === name;
  return el("td", {},
    el("button", { type: "button", class: "apply", disabled: state.running || Boolean(state.applying),
                   onclick: () => onApply(side, record, name) },
       mine ? copy.NOTES.applying : copy.ACTIONS.apply.label),
    failed ? el("div", { class: "note bad-text" }, state.applyFailed.message) : null);
}

function resultsTable(run) {
  if (!run || !run.sides) return el("p", { class: "note" }, copy.NOTES.empty_results);
  const blocks = [];
  for (const [side, record] of Object.entries(run.sides)) {
    const ranked = record.order.concat(
      Object.keys(record.results).filter((name) => !record.order.includes(name)));
    const head = el("tr", {},
      COLUMN_KEYS.map((key) => el("th", { scope: "col" }, help("COLUMNS", key))),
      el("th", { scope: "col" }));
    const rows = ranked.map((name, index) => {
      const row = record.results[name];
      const isBest = index === 0 && record.order.includes(name);
      const used = inUse(side, record, name);
      return el("tr", { class: [isBest ? "best" : "", used ? "used" : ""].join(" ").trim() },
        el("td", { class: "num" }, record.order.includes(name) ? index + 1 : "—"),
        el("td", { class: "band" }, el("b", {}, name), isBest ? el("span", { class: "badge best" }, copy.NOTES.best) : null),
        el("td", { class: `grade-${row.grade}` }, copy.GRADES[row.grade]),
        el("td", {}, row.has5g ? "yes" : "no"),
        el("td", { class: "num" }, num(row.floor)),
        el("td", { class: "num" }, num(row.sinr)),
        el("td", { class: "num" }, num(row.rsrq)),
        el("td", { class: "num" }, num(row.rsrp)),
        el("td", { class: "num" }, num(row.nrsinr)),
        el("td", { class: "carriers" }, (row.carriers || []).map((carrier) => carrier.band).join(" + ") || row.band),
        applyCell(side, record, name));
    });
    const skipped = Object.keys(record.skipped);
    blocks.push(el("div", { class: "card span" },
      heading("h2", fill(copy.APP.results_side_heading, { side: copy.SIDES[side] })),
      el("div", { class: "table-scroll" }, el("table", {}, el("thead", {}, head), el("tbody", {}, rows))),
      skipped.length
        ? el("p", { class: "note" }, `${skipped.join(", ")}: ` + copy.PROGRESS.no_service.replace("{name}", "").trim())
        : null,
      el("p", { class: "note" }, copy.NOTES.auto_row)));
  }
  return blocks;
}

async function onApply(side, record, name) {
  showError(null);
  state.applying = { side, name };
  state.applyFailed = null;
  render();
  const chosen = record.sets[name];
  const others = record.order.filter((other) => other !== name).flatMap((other) => record.sets[other]);
  const payload = side === "nr" ? { nr: chosen } : { lte: chosen, scell: others };
  try {
    await api("POST", "/api/apply", payload);
    await refreshStatus();
  } catch (failure) {
    state.applyFailed = { side, name, message: failure.message };
  }
  state.applying = null;
  render();
}

// ---- test ------------------------------------------------------------------
function pickable() {
  const run = state.results;
  if (!run || !run.sides) return [];
  return Object.entries(run.sides).flatMap(([side, record]) =>
    record.order.map((name) => ({ side, name, bands: record.sets[name] })));
}

function picked() {
  const options = pickable();
  return ["lte", "nr"].map((side) => options.find((option) => option.side === side && option.name === state.testPick[side]))
    .filter(Boolean);
}

function testLock() {
  const results = state.results;
  const chosen = picked();
  const lte = chosen.find((option) => option.side === "lte");
  const nr = chosen.find((option) => option.side === "nr");
  const scell = lte ? results.sides.lte.order.filter((other) => other !== lte.name).flatMap((other) => results.sides.lte.sets[other]) : [];
  return { lte: lte ? lte.bands : [], scell, nr: nr ? nr.bands : [] };
}

function lockSentence(plan) {
  const parts = [];
  if (plan.lte.length) parts.push("B" + plan.lte.join(", B") + (plan.scell.length ? ` +B${plan.scell.join(" B")}` : ""));
  if (plan.nr.length) parts.push("N" + plan.nr.join(", N"));
  return parts.join(" · ");
}

function lockedWhat(lock) {
  const [lte, scell] = lock.lte;
  const sentence = lockSentence({ lte, scell, nr: lock.nr[0] });
  return sentence || copy.NOTES.test_target_current;
}

function testWhat() {
  if (state.testTarget === "pick" && picked().length) return lockSentence(testLock());
  return copy.NOTES.test_target_current;
}

function currentLockWords() {
  const lock = state.status.lock;
  const words = [];
  for (const side of ["lte", "nr"]) {
    const [anchors, secondaries] = lock[side];
    if (!anchors.length) continue;
    const prefix = side === "nr" ? "N" : "B";
    words.push(anchors.map((band) => prefix + band).join(", ")
      + (secondaries.length ? ` +${secondaries.map((band) => prefix + band).join(" ")}` : ""));
  }
  return words.length ? words.join(" · ") : copy.NOTES.no_lock;
}

function sidePicker(side, options, disabled, onPick) {
  return el("select", { id: `test_pick_${side}`, disabled,
                        onchange: (event) => { state.testPick[side] = event.target.value; onPick(); } },
    el("option", { value: "" }, fill(copy.NOTES.keep_side, { side: copy.SIDES[side] })),
    options.filter((option) => option.side === side).map((option) =>
      el("option", { value: option.name, selected: option.name === state.testPick[side] ? "" : null }, option.name)));
}

function testCard() {
  const options = pickable();
  const disabled = state.running || state.busy;
  const target = copy.FIELDS.test_target;
  const plan = el("p", { class: "note" });
  const showPlan = () => {
    const chosen = state.testTarget === "pick" && picked().length;
    plan.textContent = chosen ? fill(copy.NOTES.test_plan, { bands: lockSentence(testLock()) }) : "";
  };
  const pickers = ["lte", "nr"].map((side) => sidePicker(side, options, disabled || !options.length || state.testTarget !== "pick", showPlan));
  const setPick = (on) => { pickers.forEach((select) => { select.disabled = !on || !options.length; }); showPlan(); };
  showPlan();
  const targetChoices = el("fieldset", { class: "choices" },
    el("legend", {}, help("FIELDS", "test_target")),
    el("label", { class: "choice" },
      el("input", { type: "radio", name: "test_target", value: "current", disabled,
                    checked: state.testTarget === "current" ? "" : null,
                    onchange: () => { state.testTarget = "current"; setPick(false); } }),
      hint(target.options.current.label, target.options.current), el("span", { class: "muted" }, ` — ${currentLockWords()}`)),
    el("label", { class: "choice" },
      el("input", { type: "radio", name: "test_target", value: "pick", disabled: disabled || !options.length,
                    checked: state.testTarget === "pick" ? "" : null,
                    onchange: () => { state.testTarget = "pick"; setPick(true); } }),
      hint(target.options.pick.label, target.options.pick), ...pickers),
    options.length ? plan : el("p", { class: "note" }, copy.NOTES.no_results_to_pick));
  return el("div", { class: "card span" },
    heading("h2", copy.APP.test_heading),
    el("div", { class: "form-row" },
      targetChoices,
      choices("test_minutes", state.testMinutes, (value) => { state.testMinutes = value; }, disabled),
      action("test", onTest, { disabled })),
    state.run && state.run.kind === "test" ? traceSummary(state.run) : null);
}

function traceSummary(run) {
  const keys = ["floor", "sinr", "rsrq", "rsrp", "five_g", "carriers"];
  const summary = run.summary;
  const value = {
    floor: num(summary.floor, "dB"), sinr: num(summary.sinr, "dB"), rsrq: num(summary.rsrq, "dB"),
    rsrp: num(summary.rsrp, "dBm"), five_g: summary.has5g ? "yes" : "no",
    carriers: (summary.carriers || []).map((carrier) => carrier.band).join(" + ") || summary.band,
  };
  return el("table", { class: "summary" },
    el("tbody", {}, keys.map((key) => el("tr", {},
      el("th", { scope: "row" }, help("COLUMNS", key)),
      el("td", { class: "num" }, value[key])))));
}

async function onTest() {
  showError(null);
  const seconds = Number(state.testMinutes) * 60;
  const body = { seconds, gap: 10 };
  if (state.testTarget === "pick") {
    const plan = testLock();                             // the same secondaries Apply would keep
    if (plan.lte.length) { body.lte = plan.lte; body.scell = plan.scell; }
    if (plan.nr.length) body.nr = plan.nr;
  }
  state.events = []; state.since = 0; state.run = null; state.pollFailures = 0;
  try {
    await api("POST", "/api/test", body);
    state.running = true;
    state.kind = "test";
    state.live = buildTestLive(seconds, testWhat());
    render();
    poll();
  } catch (failure) {
    showError(failure.message);
    render();
  }
}

// ---- lock profiles: a named lock to come back to ----------------------------------------------
function profileLockWords(lock) {
  const [lte, scell] = lock.lte;
  return lockSentence({ lte, scell, nr: lock.nr[0] }) || copy.NOTES.profile_auto;
}

function profileInUse(profile) {
  const lock = state.status.lock;
  return ["lte", "nr"].every((side) => sameBands(profile.lock[side][0], lock[side][0]));
}

function profilesCard() {
  const busy = state.running || state.busy || Boolean(state.applying);
  const input = el("input", { type: "text", id: "profile_name",
                              value: state.profileName ?? state.suggestedName ?? "",
                              placeholder: copy.FIELDS.profile_name.placeholder });
  input.addEventListener("input", () => { state.profileName = input.value; });
  const form = el("div", { class: "form-row" },
    el("div", { class: "field" }, el("label", { for: "profile_name" }, help("FIELDS", "profile_name")), input),
    action("save_profile", onSaveProfile, { disabled: busy }));
  const rows = state.profiles.map((profile) => {
    const used = profileInUse(profile);
    const editing = state.editing && state.editing.id === profile.id;
    const nameInput = editing && el("input", { type: "text", value: state.editing.name, "aria-label": copy.FIELDS.profile_name.label,
                                               oninput: (event) => { state.editing.name = event.target.value; },
                                               onkeydown: (event) => { if (event.key === "Enter") onRenameProfile(profile); if (event.key === "Escape") stopEditing(); } });
    return el("tr", { class: used ? "used" : "" },
      el("td", {}, editing ? nameInput : el("b", {}, profile.name)),
      el("td", { class: "muted" }, profile.carrier),
      el("td", {}, profileLockWords(profile.lock)),
      el("td", { class: "muted num" }, profile.saved.slice(0, 16).replace("T", " ")),
      el("td", {}, used
        ? el("span", { class: "badge in-use" }, copy.NOTES.in_use)
        : el("button", { type: "button", class: "apply", disabled: busy,
                         onclick: () => onApplyProfile(profile) },
             state.applying && state.applying.profile === profile.id ? copy.NOTES.applying : copy.ACTIONS.apply_profile.label)),
      el("td", { class: "row-actions" }, ...(editing
        ? [el("button", { type: "button", class: "quiet", title: copy.ACTIONS.save_name.help, onclick: () => onRenameProfile(profile) }, copy.ACTIONS.save_name.label),
           el("button", { type: "button", class: "quiet", title: copy.ACTIONS.cancel_rename.help, onclick: stopEditing }, copy.ACTIONS.cancel_rename.label)]
        : [el("button", { type: "button", class: "quiet", title: copy.ACTIONS.rename_profile.help,
                          onclick: () => { state.editing = { id: profile.id, name: profile.name }; state.confirmDelete = null; render(); } },
              copy.ACTIONS.rename_profile.label),
           el("button", { type: "button", class: "quiet danger", onclick: () => onDeleteProfile(profile),
                          title: state.confirmDelete === profile.id ? copy.ACTIONS.confirm_delete.help : copy.ACTIONS.delete_profile.help },
              state.confirmDelete === profile.id ? copy.ACTIONS.confirm_delete.label : copy.ACTIONS.delete_profile.label)])));
  });
  const list = state.profiles.length
    ? el("div", { class: "table-scroll" }, el("table", {}, el("tbody", {}, rows)))
    : el("p", { class: "note" }, copy.NOTES.empty_profiles);
  return el("div", { class: "card span" }, heading("h2", copy.APP.profiles_heading), form, list,
    el("p", { class: "note" }, copy.NOTES.rescan_hint));
}

async function refreshProfiles() {
  try { state.profiles = (await api("GET", "/api/profiles")).profiles; } catch { state.profiles = []; }
}

async function onSaveProfile() {
  showError(null);
  try {
    await api("POST", "/api/profiles", { name: document.getElementById("profile_name").value });
    state.profileName = null;
    await refreshProfiles();
  } catch (failure) {
    showError(failure.message);
  }
  render();
}

async function onApplyProfile(profile) {
  showError(null);
  state.applying = { profile: profile.id };
  render();
  try {
    await api("POST", `/api/profiles/${profile.id}/apply`, {});
    await refreshStatus();
  } catch (failure) {
    showError(failure.message);
  }
  state.applying = null;
  render();
}

function stopEditing() {
  state.editing = null;
  render();
}

async function onRenameProfile(profile) {
  const name = state.editing ? state.editing.name : profile.name;
  try {
    await api("POST", `/api/profiles/${profile.id}/rename`, { name });
    await refreshProfiles();
  } catch (failure) {
    showError(failure.message);
  }
  state.editing = null;
  render();
}

async function onDeleteProfile(profile) {
  if (state.confirmDelete !== profile.id) {       // first press only arms it; the second one deletes
    state.confirmDelete = profile.id;
    render();
    return;
  }
  try {
    await api("DELETE", `/api/profiles/${profile.id}`);
    await refreshProfiles();
  } catch (failure) {
    showError(failure.message);
  }
  state.confirmDelete = null;
  render();
}

// ---- the page --------------------------------------------------------------
function renderMain() {
  document.getElementById("view").className = "";
  const view = document.getElementById("view");
  const children = [
    deviceLine(),
    el("div", { class: "grid" },
      statusCard(),
      lockCard(),
      profilesCard(),
      scanCard(),
      liveCard("scan"),
      resultsTable(state.results),
      testCard(),
      liveCard("test")),
  ];
  view.replaceChildren(...children.flat().filter(Boolean));
}

function render() {
  const top = document.getElementById("top");
  top.replaceChildren(el("h1", {}, copy.APP.name), el("p", { class: "lede" }, copy.APP.tagline));
  if (!state.device) renderConnect(); else renderMain();
}

async function resume() {
  const status = await api("GET", "/api/status").catch(() => null);
  if (!status) return render();               // not connected yet: the connect screen is correct
  state.device = status.device;
  state.status = status;
  state.suggestedName = status.suggested_name || "";
  await refreshProfiles();
  const answer = await api("GET", "/api/events?since=0").catch(() => null);
  if (answer) {
    state.since = answer.since;
    state.events = answer.events;
    state.running = answer.running;
    state.kind = answer.kind;
    for (const event of answer.events) {
      if (event.type === "done") state.results = event.run;
      if (event.type === "done" || event.type === "trace_done") state.run = event.run;
    }
    if (state.events.length) { startLive(); if (!state.running) finishLive(); }
  }
  render();
  if (state.running) poll();
}

resume();
