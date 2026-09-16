"""Run the page against a fake router: python tools/demo_server.py

Its own fixture (not the test suite's): a short band list on each side, and a device/signal
reading tied to whichever band is actually locked right now, each with its own fixed quality.
That's what makes the ranked table show a real ordering instead of a tie -- and it stays
correct no matter how many times /api/status gets read around a scan (on connect, on every
page load/resume, on the Refresh button): those reads only look at current lock state, they
don't consume anything, so they can't drift a scan's readings out of sync the way a fixed,
hand-ordered script of responses would.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpe_band_scan import api, server                          # noqa: E402
from cpe_band_scan.router import Router                    # noqa: E402
from tests.fakes import FakeProbe, FakeSession, factory     # noqa: E402

# band -> (sinr, rsrq, rsrp, nrsinr, nrrsrp). "" is the auto/no-lock state. B3 and N78 are
# built to win their side outright, so the demo scan always shows a real ranking, not a tie.
_BAND_QUALITY = {
    "": (3, -11, -88, 10, -82),         # auto: good
    "1": (1, -14, -95, 9, -85),         # B1: fair
    "3": (7, -8, -80, 12, -78),         # B3: excellent, the LTE winner
    "78": (8, -7, -80, 15, -75),        # N78: excellent, the NR winner
    "41": (-1, -15, -96, 4, -90),       # N41: fair
}

DEMO_DATA = {
    "device/information": {"DeviceName": "H155-381", "SoftwareVersion": "4.0.0.5",
                           "SerialNumber": "DEMO001"},
    "net/net-feature-switch": {"lock_freq_switch": "3"},
    "net/lock-freq": {"lte_info": {"lock_mode": "0"}, "nr_info": {"lock_mode": "0"}},
    "net/current-plmn": {"FullName": "MCI", "ShortName": "MCI", "Numeric": "43211", "State": "0"},
    "device/nbrcellinfo": {},
    "device/seccellinfo": {},
    "config/network/bandfreqlist.xml": {"config": {
        "lte_support_band_list": "1,3", "nr_support_band_list": "78,41"}},
}


class _DemoSession(FakeSession):
    """Tracks whatever net/lock-freq last locked, and answers device/signal from that."""

    def __init__(self, data):
        super().__init__(data)
        self.lte_band = ""
        self.nr_band = ""

    def post_set(self, endpoint, data):
        result = super().post_set(endpoint, data)
        if endpoint == "net/lock-freq":
            lte = ((data.get("lte_info") or {}).get("freq_infos") or {}).get("freq_info") or []
            nr = ((data.get("nr_info") or {}).get("freq_infos") or {}).get("freq_info") or []
            self.lte_band = lte[0]["band"] if lte else ""
            self.nr_band = nr[0]["band"] if nr else ""
            self.data["net/lock-freq"] = data        # the page reads back what it wrote
        return result

    def get(self, endpoint, prefix=None):
        if endpoint == "device/signal":
            key = self.nr_band or self.lte_band          # 5G, when locked, decides quality
            sinr, rsrq, rsrp, nrsinr, nrrsrp = _BAND_QUALITY.get(key, _BAND_QUALITY[""])
            anchor = self.lte_band or "7"
            others = [b for b in ("7", "3", "1") if b != anchor][:2]
            band = (f"20MHz@3300(B{anchor}) + 20MHz@1500(B{others[0]}) + 15MHz@300(B{others[1]})"
                    f" + 100MHz@650000(N{self.nr_band or 78})")
            return {"band": band, "sinr": sinr, "rsrq": rsrq, "rsrp": rsrp,
                    "nrsinr": nrsinr, "nrrsrp": nrrsrp}
        return super().get(endpoint, prefix=prefix)


def _demo_router(url, password, username="admin"):
    return Router(url, password, username=username,
                  connection_factory=factory(_DemoSession(DEMO_DATA)))


# The real settle/gap delays (35s + 5*5s per band) would make even this short demo take
# minutes; cap every sleep the scan/test does so it finishes in a few seconds while still
# pacing the progress log enough to watch it move.
api.SLEEP = lambda seconds: time.sleep(min(seconds, 0.15))
# No internet in the demo: a fixed set of readings, cycled per band, and a proven bypass.
_READINGS = [{"latency_ms": 62, "jitter_ms": 9, "mbps": 48.3, "bytes": 30_000_000, "seconds": 5.0},
             {"latency_ms": 140, "jitter_ms": 40, "mbps": 9.8, "bytes": 6_100_000, "seconds": 5.0},
             {"error": "no_answer"},
             {"latency_ms": 71, "jitter_ms": 5, "mbps": 33.1, "bytes": 20_700_000, "seconds": 5.0}]
api.PROBE = lambda url: FakeProbe(url, bypass="confirmed", readings=_READINGS * 3)

session = server.Session(router_factory=_demo_router)
session.connect("192.168.8.1", "demo")
server.serve(port=8766, session=session)
