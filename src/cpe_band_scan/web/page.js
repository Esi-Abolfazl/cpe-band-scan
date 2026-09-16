"use strict";
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
  const status = await api("GET", routes.status).catch(() => null);
  if (!status) return render();               // not connected yet: the connect screen is correct
  state.device = status.device;
  state.status = status;
  state.suggestedName = status.suggested_name || "";
  await refreshProfiles();
  const answer = await api("GET", `${routes.events}?since=0`).catch(() => null);
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
