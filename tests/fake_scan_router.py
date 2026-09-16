"""A fake router for scanner tests: scripted signal readings, a lock the router remembers, and
the scan/cancel drivers every scanner test file starts from."""
import pytest
from huawei_lte_api import exceptions as hx
from cpe_band_scan import scanner, speed
from cpe_band_scan.device import Device
from cpe_band_scan.router import Router
from tests.fakes import FakeSession, FakeProbe, Seq, factory


DEVICE = Device(model="H155-381", firmware="4.0.0.5", driver="lockfreq", carrier="MCI", plmn="43211")

def signal(sinr, band="B7(N78)"):
    return {"band": band, "sinr": f"{sinr}", "rsrq": "-10", "rsrp": "-85", "nrsinr": "12", "nrrsrp": "-80"}

def build(signals, bands="1,7", lock=None):
    """A router whose signal readings follow `signals`, one per read."""
    session = FakeSession({
        "device/signal": Seq(signals),
        "net/lock-freq": lock or {"lte_info": {}, "nr_info": {}},
        "config/network/bandfreqlist.xml": {"config": {"lte_support_band_list": bands,
                                                       "nr_support_band_list": "78"}},
        "device/nbrcellinfo": {}, "device/seccellinfo": {},
    })
    return Router("192.168.8.1", "pw", connection_factory=factory(session)), session

def run_scan(**kwargs):
    kwargs.setdefault("sleep", lambda seconds: None)
    return list(scanner.scan(**kwargs))

class _LockAwareSession:
    """Stands in for a router that only shows the N carrier once it isn't pinned to band 7 -
    a 4G-only anchor on this network. `current_lte` tracks whichever band the scan last
    locked, starting at the band the router arrived already locked to."""

    def __init__(self):
        self.current_lte = "7"
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, endpoint, prefix=None):
        key = f"config/{endpoint}" if prefix == "config" else endpoint
        if key == "net/lock-freq":
            if self.current_lte:
                return {"lte_info": {"lock_mode": "3",
                                     "freq_infos": {"freq_info": [{"band": self.current_lte}]},
                                     "all_bands": self.current_lte},
                        "nr_info": {"lock_mode": "0"}}
            return {"lte_info": {"lock_mode": "0"}, "nr_info": {"lock_mode": "0"}}
        if key == "device/signal":
            if self.current_lte == "7":
                return signal(8, band="B7")
            return signal(8, band=f"B{self.current_lte or 1}(N78)")
        if key == "config/network/bandfreqlist.xml":
            return {"config": {"lte_support_band_list": "1,7", "nr_support_band_list": "78"}}
        if key in ("device/nbrcellinfo", "device/seccellinfo"):
            return {}
        raise KeyError(key)

    def post_set(self, endpoint, data):
        self.posts.append((endpoint, data))
        info = ((data.get("lte_info") or {}).get("freq_infos") or {}).get("freq_info") or []
        self.current_lte = info[0]["band"] if info else None
        return "OK"

ARRIVES_LOCKED = {"lte_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "7"}]},
                               "all_bands": "3,7"},
                  "nr_info": {"lock_mode": "0"}}

def last_write(session) -> dict:
    endpoint, data = session.posts[-1]
    assert endpoint == "net/lock-freq", "band locks go through net/lock-freq only"
    return data

def cancel_scan(router, sides=("lte",)):
    return list(scanner.scan(router=router, device=DEVICE, sides=sides,
                             cancelled=lambda: True, sleep=lambda s: None))

def nr_signal(nrsinr, band="B7(N78)"):
    return {"band": band, "sinr": "8", "rsrq": "-10", "rsrp": "-85",
            "nrsinr": f"{nrsinr}", "nrrsrp": "-80"}
