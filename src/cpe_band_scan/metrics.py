"""What the radio is doing, and how good that is.

Stability lives in the SINR floor, not the average: a band that averages 8 dB but dips to
-4 dB stutters, while one holding 7-10 dB does not. RSRP above -90 dBm barely moves
throughput, so it never decides a ranking.
"""
from __future__ import annotations

import math
import re
import statistics
import time

from .router import Router, RouterError

SAMPLES, GAP = 5, 5
GRADES = (("excellent", 5.0, -10.0), ("good", 0.0, -13.0), ("fair", -5.0, -16.0))
NUMBER = re.compile(r"[-+]?\d*\.?\d+")
SIGNAL_FIELDS = ("sinr", "rsrq", "rsrp", "nrsinr", "nrrsrp")
CARRIER = re.compile(r"(?:(\d+)MHz@(\d+)\()?\b([BN])(\d+)")   # "20MHz@3300(B7)" or a bare "B7"
TECH = {"B": "lte", "N": "nr"}


def carriers(band: str) -> list[dict]:
    """The router's band string, one dict per carrier, in the router's order. Width and
    channel are None when the firmware prints only the band name."""
    return [{"tech": TECH[letter], "band": f"{letter}{number}",
             "width_mhz": int(width) if width else None,
             "earfcn": int(channel) if channel else None}
            for width, channel, letter, number in CARRIER.findall(band or "")]


def number(value) -> float:
    found = NUMBER.search(str(value or ""))
    return float(found.group()) if found else float("nan")


def sample(router: Router) -> dict:
    signal = router.get("device/signal") or {}
    band = str(signal.get("band") or "")
    taken = {"band": band, "has5g": "(N" in band, "carriers": carriers(band)}
    taken.update({field: number(signal.get(field)) for field in SIGNAL_FIELDS})
    return taken


def summarise(rows: list[dict]) -> dict:
    median = lambda field: statistics.median(row[field] for row in rows)
    out = {"band": rows[-1]["band"], "carriers": rows[-1].get("carriers", []),
           "has5g": all(row["has5g"] for row in rows),
           "floor": min(row["sinr"] for row in rows),
           "peak": max(row["sinr"] for row in rows),
           "samples": len(rows)}
    out.update({field: median(field) for field in SIGNAL_FIELDS})
    return out


def measure(router: Router, samples: int = SAMPLES, gap: int = GAP, sleep=time.sleep) -> dict:
    rows = []
    for index in range(samples):
        if index:
            sleep(gap)
        rows.append(sample(router))
    return summarise(rows)


def grade(measurement: dict, expect_5g: bool = True) -> str:
    if expect_5g and not measurement.get("has5g"):
        return "no5g"
    for name, floor, rsrq in GRADES:
        if measurement["floor"] >= floor and measurement["rsrq"] >= rsrq:
            return name
    return "poor"


RANK_KEYS = {"lte": ("floor", "sinr"), "nr": ("nrsinr", "nrrsrp")}


GRADE_ORDER = ("excellent", "good", "fair", "poor", "no5g")


def rank(results: dict, expect_5g: bool = True, side: str = "lte") -> list[str]:
    """Best first: by grade, then by the floor, then by the typical signal. 'auto' competes
    like any band, since leaving the router to choose is a choice too. The 4G side ranks by
    the LTE SINR floor; the 5G side by the NR carrier, because during a 5G scan the LTE
    anchor is on automatic and its numbers say nothing about the NR band under test."""
    first, second = RANK_KEYS.get(side, RANK_KEYS["lte"])
    live = {name: row for name, row in results.items()
            if (row.get("has5g") or not expect_5g)
            and not (math.isnan(row.get(first, float("nan"))) or math.isnan(row.get(second, float("nan"))))}
    return sorted(live, key=lambda name: (GRADE_ORDER.index(grade(live[name], expect_5g)),
                                          -live[name][first], -live[name][second]))


def supported_bands(router: Router, side: str) -> list[str]:
    config = (router.get("config/network/bandfreqlist.xml") or {}).get("config") or {}
    key = "nr_support_band_list" if side == "nr" else "lte_support_band_list"
    return [band.strip() for band in (config.get(key) or "").split(",") if band.strip()]


def visible_bands(router: Router) -> dict:
    """Cells the router can see right now. Only a hint: an active lock hides the rest."""
    text = ""
    for endpoint in ("device/nbrcellinfo", "device/seccellinfo"):
        try:
            payload = router.get(endpoint) or {}
        except Exception:   # boundary: a hint only; a router that hides its cells reads as one with none
            continue
        text += "".join(str(value) for value in payload.values() if value)
    return {"lte": sorted(set(re.findall(r"\bB(\d+)", text)), key=int),
            "nr": sorted(set(re.findall(r"\bN(\d+)", text)), key=int)}
