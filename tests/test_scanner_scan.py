"""The scan: which bands are measured, how sets are graded and ranked, what gets applied."""
import pytest
from huawei_lte_api import exceptions as hx
from cpe_band_scan import scanner, speed
from cpe_band_scan.router import Router
from tests.fakes import FakeSession, FakeProbe, Seq, factory
from tests.fake_scan_router import DEVICE, signal, build, run_scan, _LockAwareSession, ARRIVES_LOCKED, last_write, nr_signal


def test_a_scan_measures_every_supported_band_plus_the_automatic_baseline():
    router, _ = build([signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    started = [event["name"] for event in events if event["type"] == "set_start"]
    assert started == ["B1", "B7", "auto"]

def test_each_set_reports_a_graded_result():
    router, _ = build([signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    result = next(event for event in events if event["type"] == "set_result")
    assert result["result"]["grade"] == "excellent"
    assert result["name"] == "B1"

def test_a_band_with_no_service_is_skipped_not_measured():
    # the first reading is the pre-scan baseline; the second is what B1 reports once locked
    router, _ = build([signal(8)] + [signal(8, band="")] + [signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    skipped = [event for event in events if event["type"] == "set_skipped"]
    assert skipped[0]["name"] == "B1"
    assert skipped[0]["reason"] == "no_service"

def test_a_band_the_router_refuses_is_skipped_and_the_scan_continues():
    router, session = build([signal(8)] * 200)
    session.data["POST net/lock-freq"] = hx.ResponseErrorException("100006", 100006)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    reasons = [event["reason"] for event in events if event["type"] == "set_skipped"]
    assert reasons == ["refused", "refused", "refused"]
    assert events[-1]["type"] == "done"

def test_a_crash_mid_scan_still_leaves_the_router_on_automatic():
    """The finally block is the only thing standing between a crash and a router
    left locked to one band."""
    router, session = build([signal(8), signal(8), RuntimeError("radio went away")])
    with pytest.raises(RuntimeError):
        run_scan(router=router, device=DEVICE, sides=("lte",))
    assert session.posts, "the scan must have written at least once"
    assert session.posts[-1][1]["lte_info"]["lock_mode"] == "0"

def test_the_winner_is_applied_with_the_runners_up_as_secondaries():
    router, _ = build([signal(8)] * 200, bands="1,7")
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    record = events[-1]["run"]["sides"]["lte"]
    applied = next(event for event in events if event["type"] == "applied")
    assert applied["plan"]["lte"] == record["sets"][record["order"][0]]
    assert applied["plan"]["lte_scell"] == [band for name in record["order"][1:]
                                            for band in record["sets"][name]]

def test_auto_beating_every_band_keeps_it_and_applies_nothing():
    """Fix 3: choose() must consult the auto row it measures. If the router's own choice
    holds a steadier floor than every band the scan tried, locking the best of them would
    make things worse, so nothing should be applied and the run should say so."""
    # baseline + B1 + B7 (6 reads each) come back at floor 8; auto (6 reads) comes back
    # higher, at floor 20 - auto genuinely wins.
    router, _ = build([signal(8)] * 13 + [signal(20)] * 6, bands="1,7")
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    run = events[-1]["run"]
    assert run["applied"]["lte"] == []
    assert not any(event["type"] == "applied" for event in events)
    assert any(event["type"] == "kept_auto" for event in events)

def test_the_run_document_carries_everything_needed_to_save_it():
    router, _ = build([signal(8)] * 200)
    run = run_scan(router=router, device=DEVICE, sides=("lte",))[-1]["run"]
    assert run["kind"] == "scan"
    assert run["device"]["carrier"] == "MCI"
    assert run["sides"]["lte"]["order"][0] in run["sides"]["lte"]["results"]
    assert run["started"] and run["finished"]

def test_a_connection_without_5g_still_produces_a_ranking():
    router, _ = build([signal(8, band="B1")] * 200)
    run = run_scan(router=router, device=DEVICE, sides=("lte",))[-1]["run"]
    assert run["expect_5g"] is False
    assert run["sides"]["lte"]["order"], "4G-only connections must still rank"

def test_a_router_already_locked_to_a_4g_only_band_still_expects_5g():
    """Fix 1: a router that arrives already locked to band 7 - a band that never carries a
    5G carrier here - hides that 5G is available at all: reading the baseline while still
    locked reports no N carrier, so expect_5g must come from a baseline taken after the
    existing lock is cleared, not from the very first reading."""
    session = _LockAwareSession()
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    run = run_scan(router=router, device=DEVICE, sides=("lte",))[-1]["run"]
    assert run["expect_5g"] is True
    assert "B7" not in run["sides"]["lte"]["order"]
    assert "B1" in run["sides"]["lte"]["order"]

def test_a_full_scan_on_a_4g_only_anchor_still_ranks_5g_bands():
    """Regression: _scan_side used to be handed the router's *original* lock to hold on the
    side it wasn't scanning, so scanning 5G while anchored to band 7 (a 4G-only band here)
    re-imposed that anchor under every 5G set. No 5G ever attached and every 5G band came
    back 'no_service'. _scan_side must read the current (cleared) lock itself instead."""
    session = _LockAwareSession()
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    run = run_scan(router=router, device=DEVICE, sides=("lte", "nr"))[-1]["run"]
    assert run["sides"]["nr"]["order"], "the 5G ranking must not be empty"
    assert not run["sides"]["nr"]["skipped"], "no 5G band should be skipped for no service"

def test_an_unlocked_router_scanning_one_side_leaves_the_other_untouched():
    """The choose() fallback that restores an unscanned side from `original` must be a no-op
    when the router arrived unlocked, so a one-sided scan behaves exactly as it did before."""
    router, _ = build([signal(8)] * 200, bands="1,7")
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    run = events[-1]["run"]
    applied = next(event for event in events if event["type"] == "applied")
    assert applied["plan"]["nr"] == []
    assert "nr" not in run["sides"]

def test_nr_is_only_locked_when_two_nr_bands_answer():
    router, _ = build([signal(8)] * 200, bands="7")
    run = run_scan(router=router, device=DEVICE, sides=("nr",))[-1]["run"]
    assert run["applied"]["nr"] == []

def test_a_crash_mid_scan_puts_the_lock_back_and_still_raises():
    """The restore is best effort and must never swallow the failure that triggered it."""
    router, session = build([signal(8), signal(8), RuntimeError("radio went away")],
                            lock=ARRIVES_LOCKED)
    with pytest.raises(RuntimeError):
        run_scan(router=router, device=DEVICE, sides=("lte",))
    restored = last_write(session)["lte_info"]
    assert [entry["band"] for entry in restored["freq_infos"]["freq_info"]] == ["7"]
    assert restored["all_bands"] == "3,7"

def test_a_5g_scan_orders_the_bands_by_their_own_carrier():
    """One baseline read, then six reads per set (one attach check, five samples): N78 at 2 dB,
    N79 at 20 dB, then the auto row at 5 dB. The LTE floor is 8 dB in every read, so if N79 is
    not first the ranking is reading the anchor instead of the NR carrier."""
    session = FakeSession({
        "device/signal": Seq([nr_signal(2)] * 7 + [nr_signal(20)] * 6 + [nr_signal(5)] * 6),
        "net/lock-freq": {"lte_info": {}, "nr_info": {}},
        "config/network/bandfreqlist.xml": {"config": {"lte_support_band_list": "7",
                                                       "nr_support_band_list": "78,79"}},
        "device/nbrcellinfo": {}, "device/seccellinfo": {},
    })
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    events = run_scan(router=router, device=DEVICE, sides=("nr",))
    done = next(event for event in events if event["type"] == "side_done")
    assert done["order"] == ["N79", "auto", "N78"]

def test_sides_and_other_agree():
    assert set(scanner.SIDES) == set(scanner.OTHER) == set(scanner.OTHER.values())

def test_run_start_carries_the_plan_for_every_side_so_the_page_can_show_both_etas():
    router, _ = build([signal(8)] * 400)
    start = run_scan(router=router, device=DEVICE, sides=("lte", "nr"))[0]
    assert start["plan"]["lte"]["total"] == 3 and start["plan"]["nr"]["total"] == 2
    assert start["plan"]["nr"]["eta_s"] == 2 * scanner.PER_SET

def test_a_5g_side_row_without_a_5g_carrier_is_graded_no_5g_even_when_none_was_expected():
    """No 5G anywhere: every N band is skipped and only the auto row is measured. Grading it on
    the 4G numbers showed 'Excellent' on a 5G table that had no 5G in it."""
    session = FakeSession({
        "device/signal": Seq([{"band": "B7", "sinr": "8", "rsrq": "-10", "rsrp": "-85"}] * 40),
        "net/lock-freq": {"lte_info": {}, "nr_info": {}},
        "config/network/bandfreqlist.xml": {"config": {"lte_support_band_list": "7",
                                                       "nr_support_band_list": "78"}},
        "device/nbrcellinfo": {}, "device/seccellinfo": {},
    })
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    events = run_scan(router=router, device=DEVICE, sides=("nr",))
    done = next(event for event in events if event["type"] == "side_done")
    assert done["results"]["auto"]["grade"] == "no5g" and done["order"] == []

def test_a_5g_scan_applies_the_strong_nr_band_even_when_the_weak_one_rode_a_better_anchor():
    """Regression: the rating read the LTE anchor on the 5G side, so N41 at -5 dB on an
    excellent anchor was ranked, reported and applied above N78 at +25 dB on a good one."""
    def reading(lte, rsrq, nr):
        return {"band": "B7(N78)", "sinr": f"{lte}", "rsrq": f"{rsrq}", "rsrp": "-85",
                "nrsinr": f"{nr}", "nrrsrp": "-80"}
    session = FakeSession({
        "device/signal": Seq([reading(8, -10, 10)] + [reading(15, -8, -5)] * 6
                             + [reading(1, -12, 25)] * 6 + [reading(8, -10, 10)] * 7),
        "net/lock-freq": {"lte_info": {}, "nr_info": {}},
        "config/network/bandfreqlist.xml": {"config": {"lte_support_band_list": "7",
                                                       "nr_support_band_list": "41,78"}},
        "device/nbrcellinfo": {}, "device/seccellinfo": {},
    })
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    events = run_scan(router=router, device=DEVICE, sides=("nr",))
    done = next(event for event in events if event["type"] == "side_done")
    assert done["order"][0] == "N78"
    reported = {event["name"]: event for event in events if event["type"] == "set_result"}
    assert reported["N78"]["result"]["grade"] == "excellent" and reported["N78"]["floor"] == 25
    assert reported["N41"]["floor"] == -5, "the progress line shows the floor the rating rests on"
    applied = next(event for event in events if event["type"] == "applied")
    assert applied["plan"]["nr"] == ["78"]
