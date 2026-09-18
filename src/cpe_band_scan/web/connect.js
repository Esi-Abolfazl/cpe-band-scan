"use strict";
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
      el("div", { class: "stack" },
        field("username", "text", defaults.username),
        el("span", { class: "note" }, copy.NOTES.username_note)),
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
    await api("POST", routes.forget, {});
    defaults.remembered = false;
  } catch (failure) {
    showError(failure.message);
  }
  render();
}

async function onConnect() {
  showError(null);
  const password = document.getElementById("password");
  if (password && !password.value.trim()) return showError(copy.ERRORS.no_password);
  state.busy = true;
  const button = document.getElementById("connect");
  if (button) button.disabled = true;               // in place: a render here would wipe the password
  const body = { url: document.getElementById("router_url").value,
                 username: document.getElementById("username").value };
  if (password) { body.password = password.value; body.remember = state.remember; }
  try {
    const answer = await api("POST", routes.connect, body);
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
    state.status = await api("GET", routes.status);
    state.running = state.status.running;
  } catch (failure) {
    showError(failure.message);
  }
}
