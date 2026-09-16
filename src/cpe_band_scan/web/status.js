"use strict";
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
    await api("POST", routes.clear, {});
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
