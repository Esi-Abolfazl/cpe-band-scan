"""One scan, many readers. The engine yields events; the CLI prints them, the server
buffers them, the tests assert on them. Nothing here knows about a terminal or HTTP."""
from __future__ import annotations

import time
from datetime import datetime

from . import lockfreq, metrics, speed
from .router import Router, RouterError

SETTLE = 35                       # seconds a re-attach needs after a band change
PER_SET = SETTLE + metrics.SAMPLES * metrics.GAP + 5
SIDES = ("lte", "nr")
OTHER = {"lte": "nr", "nr": "lte"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sets_for(router: Router, side: str, bands=None) -> dict:
    prefix = "N" if side == "nr" else "B"
    listed = bands or metrics.supported_bands(router, side)
    sets = {f"{prefix}{band}": [str(band)] for band in listed}
    sets["auto"] = []             # the reference row: what the router picks on its own
    return sets


def _scan_side(router, side, sets, expect_5g, cancelled, sleep, probe, per_set):
    other = OTHER[side]                        # the other side is on automatic during a measurement -
    keep = lockfreq.read_lock(router)           # scan() clears everything up front, so this read is it

    def set_side(bands):
        arguments = {side: bands, other: keep[other][0]}
        if other == "lte":
            arguments["lte_scell"] = keep["lte"][1]
        return lockfreq.lock(router, **arguments)

    results, skipped = {}, {}
    total = len(sets)
    yield {"type": "side_start", "side": side, "total": total, "eta_s": total * per_set}
    try:
        for index, (name, bands) in enumerate(sets.items(), 1):
            if cancelled():
                yield {"type": "cancelled", "side": side}
                break
            yield {"type": "set_start", "side": side, "name": name, "bands": bands,
                   "index": index, "total": total, "eta_s": (total - index + 1) * per_set}
            try:
                set_side(bands)
            except RouterError as error:
                skipped[name] = "refused"
                yield {"type": "set_skipped", "side": side, "name": name,
                       "reason": "refused", "detail": error.detail}
                continue
            sleep(SETTLE)
            first = metrics.sample(router)
            if not first["band"] or (side == "nr" and bands and not first["has5g"]):
                skipped[name] = "no_service"
                yield {"type": "set_skipped", "side": side, "name": name, "reason": "no_service"}
                continue
            measurement = metrics.measure(router, sleep=sleep)
            if probe is not None and not cancelled():
                measurement["speed"] = probe.measure()
            measurement["grade"] = metrics.grade(measurement, expect_5g or side == "nr")
            measurement["bands"] = bands
            results[name] = measurement
            yield {"type": "set_result", "side": side, "name": name, "result": measurement}
    finally:
        try:
            set_side([])
        except Exception:            # a failed restore must never replace the failure that caused the exit
            pass
    yield {"type": "side_done", "side": side, "sets": sets, "results": results,
           "skipped": skipped, "order": metrics.rank(results, expect_5g, side)}


def _restore(router, original) -> str | None:
    """Put back the lock the scan cleared up front, and say what happened: None when there
    was nothing to put back, "lock_back" when it is back, "lock_lost" when the router
    refused it. Best effort: a failed restore must never replace the failure that brought us
    here, but it must never pass for a successful one either."""
    if not (original["lte"][0] or original["nr"][0]):
        return None
    try:
        lockfreq.lock(router, lte=original["lte"][0], lte_scell=original["lte"][1],
                      nr=original["nr"][0], nr_scell=original["nr"][1])
    except Exception:
        return "lock_lost"
    return "lock_back"


def choose(run: dict, original: dict) -> tuple[dict, str]:
    """What to lock once the scan is done, and what to call it. A scan never takes a lock
    away without a reason it can state, so a side keeps what it arrived with - from
    `original` - unless the scan concluded something about that side.

    Two conclusions count. A band tops the LTE ranking: lock it, with every other ranked
    band as a secondary so carrier aggregation survives. Or the auto row (the router's own
    choice, measured the same way) tops it: leave the LTE side on automatic, the one case
    where an arriving lock is deliberately given up. An NR lock needs a band on top and two
    or more NR bands ranked - on NSA the NR carrier follows the LTE anchor, so locking the
    only one that answered concludes nothing.

    `outcome` names the result for the person: "applied" when the scan chose anything,
    "kept_auto" when the auto row won, "unchanged" when the scan concluded nothing and
    everything the person had is on its way back."""
    plan = {"lte": [], "lte_scell": [], "nr": [], "nr_scell": []}
    chose = auto_won = False
    lte = run["sides"].get("lte")
    if lte and lte["order"]:
        best = lte["order"][0]
        if best == "auto":
            auto_won = True
        else:
            plan["lte"] = list(lte["sets"][best])
            plan["lte_scell"] = [band for name in lte["order"][1:] for band in lte["sets"][name]]
            chose = True
    else:
        plan["lte"] = list(original["lte"][0])
        plan["lte_scell"] = list(original["lte"][1])
    nr = run["sides"].get("nr")
    nr_bands = [name for name in nr["order"] if name != "auto"] if nr else []
    if nr and len(nr_bands) >= 2 and nr["order"][0] != "auto":
        plan["nr"] = list(nr["sets"][nr["order"][0]])
        chose = True
    else:
        plan["nr"] = list(original["nr"][0])
        plan["nr_scell"] = list(original["nr"][1])
    return plan, "applied" if chose else "kept_auto" if auto_won else "unchanged"


def scan(router: Router, device, sides=("lte", "nr"), bands=None, cancelled=None, sleep=time.sleep, probe=None):
    cancelled = cancelled or (lambda: False)
    original = lockfreq.read_lock(router)
    report = probe.start() if probe is not None else None   # over the live link, before any lock change
    per_set = PER_SET + (speed.DURATION if probe is not None else 0)
    settled = stopped = False     # settled: the lock is where the person should be left
    try:                          # from the first write on, whatever ends the scan restores
        if original["lte"][0] or original["nr"][0]:
            lockfreq.lock(router)          # a lock in place hides which bands are really on air,
            sleep(SETTLE)                  # including whether 5G is available here at all
        baseline = metrics.sample(router)
        expect_5g = baseline["has5g"]
        run = {"kind": "scan", "started": _now(), "finished": "", "router_url": router.url,
               "device": device.as_dict(), "expect_5g": expect_5g, "baseline": baseline,
               "sides": {}, "applied": {"lte": [], "lte_scell": [], "nr": [], "nr_scell": []}}
        if report is not None:
            run["speed"] = report
        plan = {side: _sets_for(router, side, bands) for side in sides}
        start = {"type": "run_start", "sides": list(sides), "expect_5g": expect_5g, "baseline": baseline,
                 "plan": {side: {"total": len(sets), "eta_s": len(sets) * per_set}
                          for side, sets in plan.items()}}
        if report is not None:
            start["speed"] = report
        yield start

        for side in sides:
            sets = plan[side]
            for event in _scan_side(router, side, sets, expect_5g, cancelled, sleep, probe, per_set):
                stopped = stopped or event["type"] == "cancelled"
                yield event
                if event["type"] == "side_done":
                    run["sides"][side] = {key: event[key] for key in ("sets", "results", "skipped", "order")}
            if stopped:               # one side reporting it is the whole news; the sides left
                break                 # would only repeat the same sentence to the reader

        if stopped or cancelled():    # a cancel landing after the last side_done reports nothing
            state = _restore(router, original)
            settled = True            # restoring once is the whole job; a reader that stops
            if state:                 # reading at the next event must not trigger a second
                yield {"type": state}
        else:
            plan, outcome = choose(run, original)
            if plan["lte"] or plan["nr"]:
                lockfreq.lock(router, **plan)
            if outcome == "applied":
                run["applied"] = plan
                sleep(SETTLE)
                yield {"type": "applied", "plan": plan, "signal": metrics.sample(router)}
            else:
                yield {"type": outcome}
        run["finished"] = _now()
        settled = True
        yield {"type": "done", "run": run}
    finally:
        if not settled:
            _restore(router, original)


def trace(router: Router, seconds: int = 120, gap: int = 10, cancelled=None, sleep=time.sleep,
          lte=(), nr=(), lte_scell=()):
    """Watch a lock for a while. With no bands given it watches whatever is locked now and
    touches nothing; with `lte` or `nr` it locks that band for the test and puts the arriving
    lock back afterwards, whatever happens in between."""
    cancelled = cancelled or (lambda: False)
    original = lockfreq.read_lock(router)
    try:
        if lte or nr:
            lockfreq.lock(router, lte=lte or original["lte"][0], lte_scell=lte_scell if lte else original["lte"][1],
                          nr=nr or original["nr"][0], nr_scell=() if nr else original["nr"][1])
            sleep(SETTLE)
        started, rows = _now(), []
        yield {"type": "trace_start", "seconds": seconds, "gap": gap, "lock": lockfreq.read_lock(router)}
        for index in range(seconds // gap):
            if cancelled():
                yield {"type": "cancelled", "side": "trace"}
                break
            row = metrics.sample(router)
            rows.append(row)
            yield {"type": "trace_sample", "at_s": index * gap, "sample": row}
            sleep(gap)
        if not rows:
            return
        summary = metrics.summarise(rows)
        summary["grade"] = metrics.grade(summary, expect_5g=rows[0]["has5g"])
        run = {"kind": "test", "started": started, "finished": _now(), "router_url": router.url,
               "lock": lockfreq.read_lock(router), "samples": rows, "summary": summary}
        yield {"type": "trace_done", "run": run}
    finally:
        if lte or nr:
            lockfreq.lock(router, lte=original["lte"][0], lte_scell=original["lte"][1],
                          nr=original["nr"][0], nr_scell=original["nr"][1])
