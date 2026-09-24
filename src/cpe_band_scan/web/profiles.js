"use strict";
// ---- lock profiles: a named lock to come back to ----------------------------------------------
function profileLockWords(lock) {
  const [lte, scell] = lock.lte;
  return lockSentence({ lte, scell, nr: lock.nr[0] }) || copy.NOTES.profile_auto;
}

function profileInUse(profile) {
  const lock = state.status.lock;
  return ["lte", "nr"].every((side) => [0, 1].every((part) => sameBands(profile.lock[side][part], lock[side][part])));
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
  try { state.profiles = (await api("GET", routes.profiles)).profiles; } catch (failure) { showError(failure.message); }
}

async function onSaveProfile() {
  showError(null);
  try {
    await api("POST", routes.profiles, { name: document.getElementById("profile_name").value });
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
    await api("POST", route("profile_apply", profile.id), {});
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
    await api("POST", route("profile_rename", profile.id), { name });
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
    await api("DELETE", route("profile", profile.id));
    await refreshProfiles();
  } catch (failure) {
    showError(failure.message);
  }
  state.confirmDelete = null;
  render();
}
