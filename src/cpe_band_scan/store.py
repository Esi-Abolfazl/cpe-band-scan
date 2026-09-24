"""What lives in ~/.cpe-band-scan: saved runs (one JSON file each under runs/), lock profiles
(profiles.json) and settings.json. The password is written only when the person ticks Remember,
and then the settings file is readable by its owner alone."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from .config import home
from .router import RouterError

# ponytail: one lock per process. Two `ui` processes on the same home can still interleave a
# profile edit; an O_EXCL lock file (no fcntl on Windows) is the upgrade if that ever happens.
_LOCK = threading.RLock()

RUN_ID = re.compile(r"\A[0-9]{8}-[0-9]{6}(-[0-9]+)?\Z")


def runs_dir() -> Path:
    folder = home() / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


SETTINGS_KEYS = ("router_url", "username", "password")   # password only via remember_password()


def settings_path() -> Path:
    home().mkdir(parents=True, exist_ok=True)
    return home() / "settings.json"


def _write(path: Path, payload) -> None:
    """Whole or not at all: the new text lands beside the old file and replaces it in one step.
    mkstemp makes the file owner-only, which the settings file needs for the password."""
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    except BaseException:
        os.unlink(temporary)
        raise


def settings() -> dict:
    """A settings file that no longer parses is moved to settings.json.bad, kept for the person,
    and the app starts over from defaults: only an address and a login are lost."""
    path = settings_path()
    with _LOCK:
        try:
            kept = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except ValueError:
            kept = None
        if not isinstance(kept, dict):
            os.replace(path, path.with_name(path.name + ".bad"))
            return {}
        return kept


def save_settings(**values) -> dict:
    with _LOCK:
        kept = settings()
        kept.update({key: value for key, value in values.items()
                     if key in SETTINGS_KEYS and key != "password" and value})
        _write(settings_path(), kept)
        return kept


def remember_password(password: str | None) -> dict:
    """Store the password when given, drop it when None or empty. The only path that writes it."""
    with _LOCK:
        kept = settings()
        if password:
            kept["password"] = password
        else:
            kept.pop("password", None)
        _write(settings_path(), kept)
        return kept


def remembered_password() -> str:
    return str(settings().get("password") or "")


# ---- lock profiles: a named lock to come back to when the place or the carrier changes ---------
def profiles_path() -> Path:
    home().mkdir(parents=True, exist_ok=True)
    return home() / "profiles.json"


def list_profiles() -> list[dict]:
    """Profiles are the person's own work: a file that no longer parses is an error they are
    shown, never a list that reads as empty and is then saved over."""
    path = profiles_path()
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except ValueError:
        rows = None
    if not isinstance(rows, list):
        raise RouterError("store_unreadable", str(path))
    return sorted((row for row in rows if isinstance(row, dict)),
                  key=lambda row: (row.get("saved", ""), row.get("id", "")), reverse=True)


def save_profile(name: str, carrier: str, lock: dict) -> dict:
    with _LOCK:
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
        _write(profiles_path(), rows + [profile])
        return profile


def load_profile(profile_id: str) -> dict:
    for row in list_profiles():
        if row.get("id") == profile_id:
            return row
    raise KeyError(profile_id)


def rename_profile(profile_id: str, name: str) -> dict:
    with _LOCK:
        rows = list_profiles()
        found = next((row for row in rows if row.get("id") == profile_id), None)
        if found is None:
            raise KeyError(profile_id)
        found["name"] = name.strip() or found["name"]
        _write(profiles_path(), rows)
        return found


def delete_profile(profile_id: str) -> None:
    with _LOCK:
        rows = list_profiles()
        kept = [row for row in rows if row.get("id") != profile_id]
        if len(kept) == len(rows):
            raise KeyError(profile_id)
        _write(profiles_path(), kept)


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
    with _LOCK:                 # the id is minted from what is on disk
        when = datetime.now()
        stored = dict(run)
        carrier = (stored.get("device") or {}).get("carrier", "")
        stored["name"] = (name or stored.get("name") or default_name(carrier, when)).strip()
        given = str(stored.get("id") or "")
        stored["id"] = given if RUN_ID.match(given) else _unique_id(when)
        stored["saved"] = when.isoformat(timespec="seconds")
        _write(runs_dir() / f"{stored['id']}.json", stored)
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
    path = _path(run_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise RouterError("store_unreadable", str(path)) from None


def rename(run_id: str, name: str) -> dict:
    with _LOCK:
        run = load(run_id)
        run["name"] = name.strip() or run["name"]
        _write(_path(run_id), run)
        return run


def delete(run_id: str) -> None:
    _path(run_id).unlink()
