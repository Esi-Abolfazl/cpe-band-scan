"use strict";
// ---- results ---------------------------------------------------------------
const COLUMN_KEYS = ["rank", "band", "grade", "five_g", "floor", "sinr", "rsrq", "rsrp",
                     "nr_sinr", "carriers"];
const SPEED_KEYS = ["speed", "ping"];
const SPEED_AT = 4;            // after the 5G column; cli.py holds the same two values

// a blocked probe measured no band: its sentence is still said, but no columns are added
function showsSpeed(run) {
  return Boolean(run.speed) && run.speed.bypass !== "blocked";
}

function columnKeys(run) {
  const keys = COLUMN_KEYS.slice();
  if (showsSpeed(run)) keys.splice(SPEED_AT, 0, ...SPEED_KEYS);
  return keys;
}

function speedCells(row) {
  const probe = row.speed;
  const answered = probe && !probe.error;
  return SPEED_KEYS.map((key) => el("td", { class: "num" },
    answered ? num(key === "speed" ? probe.mbps : probe.latency_ms) : copy.NOTES.probe_no_answer));
}

function inUse(side, record, name) {
  const lock = state.status && state.status.lock[side];
  return Boolean(lock && sameBands(record.sets[name], lock[0]));   // auto is the empty lock
}

function applyCell(side, record, name) {
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
  const [firstSide] = Object.keys(run.sides);
  for (const [side, record] of Object.entries(run.sides)) {
    const ranked = record.order.concat(
      Object.keys(record.results).filter((name) => !record.order.includes(name)));
    const head = el("tr", {},
      columnKeys(run).map((key) => el("th", { scope: "col" }, help("COLUMNS", key))),
      el("th", { scope: "col" }));
    const rows = ranked.map((name, index) => {
      const row = record.results[name];
      const isBest = index === 0 && record.order.includes(name);
      const used = inUse(side, record, name);
      const cells = [
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
      ];
      if (showsSpeed(run)) cells.splice(SPEED_AT, 0, ...speedCells(row));
      return el("tr", { class: [isBest ? "best" : "", used ? "used" : ""].join(" ").trim() },
        cells, applyCell(side, record, name));
    });
    const skipped = Object.keys(record.skipped);
    blocks.push(el("div", { class: "card span" },
      heading("h2", fill(copy.APP.results_side_heading, { side: copy.SIDES[side] })),
      el("div", { class: "table-scroll" }, el("table", {}, el("thead", {}, head), el("tbody", {}, rows))),
      skipped.length
        ? el("p", { class: "note" }, `${skipped.join(", ")}: ` + copy.PROGRESS.no_service.replace("{name}", "").trim())
        : null,
      el("p", { class: "note" }, copy.NOTES.auto_row),
      run.speed && side === firstSide ? el("p", { class: "note" }, copy.NOTES["probe_" + run.speed.bypass]) : null));
  }
  return blocks;
}

async function onApply(side, record, name) {
  showError(null);
  state.applying = { side, name };
  state.applyFailed = null;
  render();
  const chosen = record.sets[name];
  const others = name === "auto" ? []
    : record.order.filter((other) => other !== name).flatMap((other) => record.sets[other]);
  const payload = side === "nr" ? { nr: chosen } : { lte: chosen, scell: others };
  try {
    await api("POST", routes.apply, payload);
    await refreshStatus();
  } catch (failure) {
    state.applyFailed = { side, name, message: failure.message };
  }
  state.applying = null;
  render();
}
