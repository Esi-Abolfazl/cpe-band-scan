"""api/net/lock-freq, the only band-lock endpoint that firmware 4.x honours.

lock_mode: 0 none, 3 band, 1 frequency, 2 cell. Bands inside <freq_infos> may serve as the
primary carrier; bands that appear only in <all_bands> are allowed as secondary carriers,
which is how a lock keeps carrier aggregation alive.
"""
from __future__ import annotations

from collections import OrderedDict

from .router import Router

ENDPOINT = "net/lock-freq"


def bands_of(value) -> list[str]:
    """Band numbers as strings. A bare string is refused rather than iterated: "78" would
    otherwise become bands 7 and 8."""
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        raise ValueError(f"bands must be a list of numbers, got {value!r}")
    bands = [str(band).strip() for band in value]
    if not all(band.isdigit() for band in bands):
        raise ValueError(f"not band numbers: {value!r}")
    return bands


def band_info(bands, scell=()) -> OrderedDict:
    bands, scell = bands_of(bands), bands_of(scell)
    if not bands:
        return OrderedDict(lock_mode="0", freq_infos={}, all_bands="")
    every = sorted({*bands, *scell}, key=int)
    return OrderedDict(lock_mode="3",
                       freq_infos={"freq_info": [{"band": b} for b in bands]},
                       all_bands=",".join(every))


def lock(router: Router, lte=(), nr=(), lte_scell=(), nr_scell=()) -> str:
    return router.post(ENDPOINT, OrderedDict(lte_info=band_info(lte, lte_scell),
                                             nr_info=band_info(nr, nr_scell)))


def read_lock(router: Router) -> dict:
    current = router.get(ENDPOINT) or {}
    out = {}
    for side in ("lte", "nr"):
        info = current.get(f"{side}_info") or {}
        raw = (info.get("freq_infos") or {}).get("freq_info") or []
        entries = raw if isinstance(raw, list) else [raw]
        anchors = [str(entry["band"]) for entry in entries if entry.get("band")]
        every = [b for b in (info.get("all_bands") or "").split(",") if b]
        out[side] = (anchors, [b for b in every if b not in anchors])
    return out
