"""Saved runs: one JSON file each, under ~/.cpe-band-scan/runs. Nothing here ever holds a password."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

RUN_ID = re.compile(r"\A[0-9]{8}-[0-9]{6}(-[0-9]+)?\Z")


def home() -> Path:
    return Path(os.environ.get("CPE_BAND_SCAN_HOME") or Path.home() / ".cpe-band-scan")


def runs_dir() -> Path:
    folder = home() / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


SETTINGS_KEYS = ("router_url", "username")          # a password is never one of these


def settings_path() -> Path:
    home().mkdir(parents=True, exist_ok=True)
    return home() / "settings.json"


def settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(**values) -> dict:
    kept = dict(settings())
    kept.update({key: value for key, value in values.items() if key in SETTINGS_KEYS and value})
    settings_path().write_text(json.dumps(kept, indent=2), encoding="utf-8")
    return kept


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
