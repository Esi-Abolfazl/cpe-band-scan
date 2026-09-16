"""What lives in ~/.cpe-band-scan: saved runs (one JSON file each under runs/), lock profiles
(profiles.json) and settings.json. The password is written only when the person ticks Remember,
and then the settings file is readable by its owner alone."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from .config import home

RUN_ID = re.compile(r"\A[0-9]{8}-[0-9]{6}(-[0-9]+)?\Z")


def runs_dir() -> Path:
    folder = home() / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


SETTINGS_KEYS = ("router_url", "username", "password")   # password only via remember_password()


def settings_path() -> Path:
    home().mkdir(parents=True, exist_ok=True)
    return home() / "settings.json"


def settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_settings(kept: dict) -> dict:
    path = settings_path()
    path.write_text(json.dumps(kept, indent=2), encoding="utf-8")
    os.chmod(path, 0o600)
    return kept


def save_settings(**values) -> dict:
    kept = dict(settings())
    kept.update({key: value for key, value in values.items()
                 if key in SETTINGS_KEYS and key != "password" and value})
    return _write_settings(kept)


def remember_password(password: str | None) -> dict:
    """Store the password when given, drop it when None or empty. The only path that writes it."""
    kept = dict(settings())
    if password:
        kept["password"] = password
    else:
        kept.pop("password", None)
    return _write_settings(kept)


def remembered_password() -> str:
    return str(settings().get("password") or "")


# ---- lock profiles: a named lock to come back to when the place or the carrier changes ---------
def profiles_path() -> Path:
    home().mkdir(parents=True, exist_ok=True)
    return home() / "profiles.json"


def list_profiles() -> list[dict]:
    try:
        rows = json.loads(profiles_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return sorted((row for row in rows if isinstance(row, dict)),
                  key=lambda row: (row.get("saved", ""), row.get("id", "")), reverse=True)


def _write_profiles(rows: list[dict]) -> None:
    profiles_path().write_text(json.dumps(rows, indent=2), encoding="utf-8")


def save_profile(name: str, carrier: str, lock: dict) -> dict:
    when = datetime.now()
    rows = list_profiles()
    taken = {row["id"] for row in rows}
    base = f"{when:%Y%m%d-%H%M%S}"
    candidate, suffix = base, 1
    while candidate in taken:
        suffix += 1
        candidate = f"{base}-{suffix}"
    profile = {"id": candidate, "name": (name or default_name(carrier, when)).strip(),
               "carrier": carrier or "", "saved": when.isoformat(timespec="seconds"),
               "lock": {side: [list(lock[side][0]), list(lock[side][1])] for side in ("lte", "nr")}}
    _write_profiles(rows + [profile])
    return profile


def load_profile(profile_id: str) -> dict:
    for row in list_profiles():
        if row.get("id") == profile_id:
            return row
    raise KeyError(profile_id)


def rename_profile(profile_id: str, name: str) -> dict:
    rows = list_profiles()
    found = next((row for row in rows if row.get("id") == profile_id), None)
    if found is None:
        raise KeyError(profile_id)
    found["name"] = name.strip() or found["name"]
    _write_profiles(rows)
    return found


def delete_profile(profile_id: str) -> None:
    rows = list_profiles()
    kept = [row for row in rows if row.get("id") != profile_id]
    if len(kept) == len(rows):
        raise KeyError(profile_id)
    _write_profiles(kept)


def default_name(carrier: str, when: datetime | None = None) -> str:
    when = when or datetime.now()
    return f"{carrier or 'Unknown carrier'} — {when:%d %b %Y, %H:%M}"


def _unique_id(when: datetime) -> str:
    base = f"{when:%Y%m%d-%H%M%S}"
    candidate, suffix = base, 1
    while (runs_dir() / f"{candidate}.json").exists():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _path(run_id: str) -> Path:
    if not RUN_ID.match(run_id or ""):
        raise KeyError(run_id)
    path = runs_dir() / f"{run_id}.json"
    if not path.exists():
        raise KeyError(run_id)
    return path


def save(run: dict, name: str | None = None) -> dict:
    when = datetime.now()
    stored = dict(run)
    carrier = (stored.get("device") or {}).get("carrier", "")
    stored["name"] = (name or stored.get("name") or default_name(carrier, when)).strip()
    given = str(stored.get("id") or "")
    stored["id"] = given if RUN_ID.match(given) else _unique_id(when)
    stored["saved"] = when.isoformat(timespec="seconds")
    (runs_dir() / f"{stored['id']}.json").write_text(json.dumps(stored, indent=2), encoding="utf-8")
    return stored


def best_of(run: dict) -> str:
    sides = run.get("sides") or {}
    order = (sides.get("lte") or {}).get("order") or (sides.get("nr") or {}).get("order") or []
    return order[0] if order else ""


def list_runs() -> list[dict]:
    rows = []
    for path in runs_dir().glob("*.json"):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append({"id": run.get("id", path.stem), "name": run.get("name", ""),
                     "saved": run.get("saved", ""), "kind": run.get("kind", "scan"),
                     "carrier": (run.get("device") or {}).get("carrier", ""),
                     "sides": list((run.get("sides") or {}).keys()),
                     "best": best_of(run)})
    return sorted(rows, key=lambda row: (row["saved"], row["id"]), reverse=True)


def load(run_id: str) -> dict:
    return json.loads(_path(run_id).read_text(encoding="utf-8"))


def rename(run_id: str, name: str) -> dict:
    run = load(run_id)
    run["name"] = name.strip() or run["name"]
    _path(run_id).write_text(json.dumps(run, indent=2), encoding="utf-8")
    return run


def delete(run_id: str) -> None:
    _path(run_id).unlink()
