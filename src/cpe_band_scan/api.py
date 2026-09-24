"""Every /api route, spelled once. The server matches paths against ROUTES, the page receives
ROUTES in its bootstrap and the tests import it; nothing else spells a path. HANDLERS is the one
explicit list of what answers each (method, route)."""
from __future__ import annotations

import time
from urllib.parse import unquote

from . import config, lockfreq, metrics, scanner, speed, store
from .config import DEFAULT_URL

ROUTES = {
    "status": "/api/status",
    "events": "/api/events",
    "connect": "/api/connect",
    "forget": "/api/forget",
    "scan": "/api/scan",
    "test": "/api/test",
    "cancel": "/api/cancel",
    "apply": "/api/apply",
    "clear": "/api/clear",
    "runs": "/api/runs",
    "run": "/api/runs/{id}",
    "run_rename": "/api/runs/{id}/rename",
    "profiles": "/api/profiles",
    "profile": "/api/profiles/{id}",
    "profile_rename": "/api/profiles/{id}/rename",
    "profile_apply": "/api/profiles/{id}/apply",
}

SLEEP = time.sleep    # real between-band and between-sample waits; read at call time so
                      # tests can swap in a no-op instead of waiting out real settle/gap delays
PROBE = speed.SpeedProbe   # built per scan for the connected router; the demo swaps in a fake


def match(path: str) -> tuple[str, str] | None:
    """The route name and the decoded `{id}` segment ("" when the route has none)."""
    parts = path.split("/")
    for name, template in ROUTES.items():
        pattern = template.split("/")
        if len(pattern) == len(parts) and all(p == "{id}" or p == q for p, q in zip(pattern, parts)):
            return name, next((unquote(q) for p, q in zip(pattern, parts) if p == "{id}"), "")
    return None


# Each handler: (session, body, id, query) -> JSON payload. KeyError -> 404, ValueError -> 400,
# RouterError -> 409, anything else -> 500 "crash", mapped by the server; a body that is not a
# JSON object never reaches a handler.

def status(session, body, id, query):
    router = session.require_router()
    return {"device": session.device.as_dict(), "lock": lockfreq.read_lock(router),
            "signal": metrics.sample(router), "visible": metrics.visible_bands(router),
            "running": session.running(),
            "suggested_name": store.default_name(session.device.carrier)}


def events(session, body, id, query):
    since = max(0, int(query.get("since", ["0"])[0]))
    events = session.events[since:]
    return {"since": since + len(events), "events": events,
            "running": session.running(), "kind": session.kind, "results": session.results}


def connect(session, body, id, query):
    with session.lock:
        session.require_idle()
        password = body.get("password") or store.remembered_password()
        username = body.get("username") or config.username()
        device = session.connect(body.get("url") or DEFAULT_URL, password, username)
        store.save_settings(router_url=session.router.url, username=username)
        if "remember" in body:                  # the page decides; absent means keep as is
            store.remember_password(password if body["remember"] else None)
    return {"device": device.as_dict(), "suggested_name": store.default_name(device.carrier)}


def forget(session, body, id, query):
    store.remember_password(None)
    return {"remembered": False}


def scan(session, body, id, query):
    router, device = session.require_router(), session.device
    sides = tuple(body.get("sides") or ("lte", "nr"))
    if any(side not in scanner.SIDES for side in sides):
        raise ValueError(f"sides {sides!r}")
    bands = lockfreq.bands_of(body.get("bands") or []) or None
    probe = PROBE(router.url) if body.get("speed", True) is not False else None
    session.start("scan", lambda cancelled: scanner.scan(
        router, device, sides=sides, bands=bands, cancelled=cancelled, sleep=SLEEP, probe=probe))
    return {"started": True}


def test(session, body, id, query):
    router = session.require_router()
    seconds = int(body["seconds"]) if "seconds" in body else 120
    gap = int(body["gap"]) if "gap" in body else 10
    if not 0 < gap <= seconds:
        raise ValueError(f"seconds={seconds} gap={gap}")
    lte = lockfreq.bands_of(body["lte"]) if "lte" in body else None   # [] = automatic for the test;
    nr = lockfreq.bands_of(body["nr"]) if "nr" in body else None      # absent = keep the lock
    scell = lockfreq.bands_of(body.get("scell") or [])
    session.start("test", lambda cancelled: scanner.trace(
        router, seconds=seconds, gap=gap, cancelled=cancelled, sleep=SLEEP, lte=lte, nr=nr, lte_scell=scell))
    return {"started": True}


def cancel(session, body, id, query):
    session.cancel()
    return {"cancelling": True}


def apply(session, body, id, query):
    with session.lock:
        session.require_idle()
        router = session.require_router()
        current = lockfreq.read_lock(router)     # an absent side keeps the whole lock it has
        lte = body["lte"] if "lte" in body else current["lte"][0]
        scell = body["scell"] if "scell" in body else current["lte"][1]
        nr, nr_scell = (body["nr"], []) if "nr" in body else current["nr"]
        lockfreq.lock(router, lte=lte, lte_scell=scell, nr=nr, nr_scell=nr_scell)
    return {"applied": True}


def clear(session, body, id, query):
    with session.lock:
        session.require_idle()
        lockfreq.lock(session.require_router())
    return {"applied": True}


def list_runs(session, body, id, query):
    return {"runs": store.list_runs()}


def save_run(session, body, id, query):
    return {"run": store.save(body.get("run") or {}, body.get("name"))}


def load_run(session, body, id, query):
    return {"run": store.load(id)}


def rename_run(session, body, id, query):
    return {"run": store.rename(id, body.get("name") or "")}


def delete_run(session, body, id, query):
    store.delete(id)
    return {"deleted": True}


def list_profiles(session, body, id, query):
    return {"profiles": store.list_profiles()}


def save_profile(session, body, id, query):
    with session.lock:
        session.require_idle()              # mid-scan the lock is whatever band is under test
        router = session.require_router()
        profile = store.save_profile(body.get("name") or "", session.device.carrier,
                                     lockfreq.read_lock(router))
    return {"profile": profile}


def rename_profile(session, body, id, query):
    return {"profile": store.rename_profile(id, body.get("name") or "")}


def apply_profile(session, body, id, query):
    lock = store.load_profile(id)["lock"]
    with session.lock:
        session.require_idle()
        lockfreq.lock(session.require_router(), lte=lock["lte"][0], lte_scell=lock["lte"][1],
                      nr=lock["nr"][0], nr_scell=lock["nr"][1])
    return {"applied": True}


def delete_profile(session, body, id, query):
    store.delete_profile(id)
    return {"deleted": True}


HANDLERS = {
    ("GET", "status"): status,
    ("GET", "events"): events,
    ("POST", "connect"): connect,
    ("POST", "forget"): forget,
    ("POST", "scan"): scan,
    ("POST", "test"): test,
    ("POST", "cancel"): cancel,
    ("POST", "apply"): apply,
    ("POST", "clear"): clear,
    ("GET", "runs"): list_runs,
    ("POST", "runs"): save_run,
    ("GET", "run"): load_run,
    ("POST", "run_rename"): rename_run,
    ("DELETE", "run"): delete_run,
    ("GET", "profiles"): list_profiles,
    ("POST", "profiles"): save_profile,
    ("POST", "profile_rename"): rename_profile,
    ("POST", "profile_apply"): apply_profile,
    ("DELETE", "profile"): delete_profile,
}
