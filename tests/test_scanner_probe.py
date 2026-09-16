"""The speed probe rides along a scan: readings per set, the verdict on the run, the ETA."""
from cpe_band_scan import scanner, speed
from tests.fakes import FakeSession, FakeProbe, Seq, factory
from tests.fake_scan_router import DEVICE, signal, build, run_scan


def test_with_a_probe_every_measured_set_carries_speed_and_the_run_carries_the_verdict():
    router, _ = build([signal(8)] * 200)
    probe = FakeProbe(bypass="confirmed")
    events = run_scan(router=router, device=DEVICE, sides=("lte",), probe=probe)
    results = [event for event in events if event["type"] == "set_result"]
    assert results and all(event["result"]["speed"] == FakeProbe.READING for event in results)
    run = events[-1]["run"]
    assert run["speed"]["bypass"] == "confirmed"
    assert run["sides"]["lte"]["results"]["auto"]["speed"] == FakeProbe.READING
    assert probe.started == 1 and probe.measured == len(results)

def test_the_probe_starts_before_the_first_lock_is_touched():
    """start() proves the bypass over the live connection; after the first lock change the
    link is down for half a minute and nothing could be proven."""
    router, session = build([signal(8)] * 200, lock={
        "lte_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "7"}]}, "all_bands": "7"},
        "nr_info": {"lock_mode": "0"}})
    order = []
    probe = FakeProbe()
    probe.start = lambda: order.append("start") or {"bypass": "not_needed", "lan_ip": "", "public_ip": ""}
    original_post = session.post_set
    session.post_set = lambda endpoint, data: order.append("lock") or original_post(endpoint, data)
    run_scan(router=router, device=DEVICE, sides=("lte",), probe=probe)
    assert order[0] == "start"

def test_run_start_carries_the_verdict_so_the_page_can_say_it_first():
    router, _ = build([signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",), probe=FakeProbe(bypass="failed"))
    start = next(event for event in events if event["type"] == "run_start")
    assert start["speed"]["bypass"] == "failed"

def test_the_eta_grows_by_the_probe_duration_per_set_only_when_a_probe_is_on():
    router, _ = build([signal(8)] * 200, bands="1,7")
    with_probe = run_scan(router=router, device=DEVICE, sides=("lte",), probe=FakeProbe())
    router, _ = build([signal(8)] * 200, bands="1,7")
    without = run_scan(router=router, device=DEVICE, sides=("lte",))
    plan_with = next(e for e in with_probe if e["type"] == "run_start")["plan"]["lte"]
    plan_without = next(e for e in without if e["type"] == "run_start")["plan"]["lte"]
    assert plan_with["eta_s"] == plan_without["eta_s"] + plan_with["total"] * speed.DURATION
    side_with = next(e for e in with_probe if e["type"] == "side_start")["eta_s"]
    side_without = next(e for e in without if e["type"] == "side_start")["eta_s"]
    assert side_with == side_without + plan_with["total"] * speed.DURATION

def test_without_a_probe_nothing_about_speed_appears_anywhere():
    router, _ = build([signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    run = events[-1]["run"]
    assert "speed" not in run
    assert "speed" not in next(e for e in events if e["type"] == "run_start")
    assert all("speed" not in row for row in run["sides"]["lte"]["results"].values())

def test_a_probe_reading_never_touches_the_ranking():
    """Spec R15. Two bands with identical radio numbers and wildly different speeds must
    rank exactly as they would without a probe."""
    fast_then_slow = [{"latency_ms": 30, "jitter_ms": 2, "mbps": 200.0, "bytes": 1, "seconds": 1.0},
                      {"latency_ms": 900, "jitter_ms": 50, "mbps": 0.2, "bytes": 1, "seconds": 1.0},
                      dict(FakeProbe.READING)]
    router, _ = build([signal(8)] * 200, bands="1,7")
    with_probe = run_scan(router=router, device=DEVICE, sides=("lte",), probe=FakeProbe(readings=fast_then_slow))
    router, _ = build([signal(8)] * 200, bands="1,7")
    without = run_scan(router=router, device=DEVICE, sides=("lte",))
    assert with_probe[-1]["run"]["sides"]["lte"]["order"] == without[-1]["run"]["sides"]["lte"]["order"]

def test_a_cancelled_scan_does_not_probe_the_band_it_was_measuring():
    router, _ = build([signal(8)] * 200)
    probe = FakeProbe()
    calls = {"n": 0}
    def cancelled():
        calls["n"] += 1
        return calls["n"] > 1          # first check passes, every later check says stop
    events = list(scanner.scan(router=router, device=DEVICE, sides=("lte",), probe=probe,
                               cancelled=cancelled, sleep=lambda s: None))
    assert any(event["type"] == "cancelled" for event in events)
    assert probe.measured == 0
