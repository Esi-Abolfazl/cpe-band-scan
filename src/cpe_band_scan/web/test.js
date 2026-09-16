"use strict";
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
    await api("POST", routes.test, body);
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
