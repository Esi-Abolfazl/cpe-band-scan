"use strict";
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
      toggle("speed_test", state.speedTest, (on) => { state.speedTest = on; }, disabled),
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
    case "run_start":
      return event.speed ? copy.NOTES["probe_" + event.speed.bypass] : null;
    case "set_start":                       // the bar already says "9 of 11 · about 3 min left"
      return fill(words.log_measuring, { name: event.name });
    case "set_result": {
      const speed = event.result.speed;
      const answered = speed && !speed.error;
      return coloured(answered ? words.log_result_probe : words.log_result,
                      { name: event.name, floor: event.floor, grade: "{grade}",
                        mbps: answered ? speed.mbps : "", ping: answered ? speed.latency_ms : "" },
                      "grade", el("span", { class: `grade-${event.result.grade}` }, copy.GRADES[event.result.grade]));
    }
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
    state.live = buildTestLive(start ? start.seconds : 120, testWhat(start && start.plan));
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
    await api("POST", routes.scan, { sides, speed: state.speedTest });
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
  try { await api("POST", routes.cancel, {}); } catch (failure) { showError(failure.message); }
}

async function poll() {
  const answer = await api("GET", `${routes.events}?since=${state.since}`).catch(() => null);
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
