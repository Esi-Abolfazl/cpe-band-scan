import pytest
from huawei_lte_api import exceptions as hx

from cpe_band_scan import scanner
from cpe_band_scan.device import Device
from cpe_band_scan.router import Router
from tests.fakes import FakeSession, Seq, factory

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


def test_cancelling_stops_the_scan_and_restores_automatic():
    router, session = build([signal(8)] * 200)
    events = list(scanner.scan(router=router, device=DEVICE, sides=("lte",),
                               cancelled=lambda: True, sleep=lambda s: None))
    assert events[-1]["type"] == "done"
    assert any(event["type"] == "cancelled" for event in events)
    assert session.posts, "the finally block must still clear the lock"
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


def test_a_5g_only_scan_keeps_the_arriving_4g_anchor_in_what_it_writes():
    """Regression: a 5G-only scan must not drop the 4G anchor the router arrived locked to
    as a side effect - choose() has to fill the untouched side back in from `original`.
    Only one 5G band answers here, so the scan itself picks nothing: the anchor comes back
    in the final write, and there is no 'Locked to ...' claiming the scan chose it."""
    session = _LockAwareSession()
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    events = run_scan(router=router, device=DEVICE, sides=("nr",))
    run = events[-1]["run"]
    assert "lte" not in run["sides"], "the 4G side was never scanned"
    written = last_write(session)["lte_info"]
    assert [entry["band"] for entry in written["freq_infos"]["freq_info"]] == ["7"], \
        "the arriving 4G anchor must survive the 5G-only scan"
    assert not any(event["type"] == "applied" for event in events), \
        "nothing was chosen, so nothing may be announced as chosen"


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


def test_trace_yields_one_sample_per_step_and_a_summary():
    router, _ = build([signal(8)] * 50)
    events = list(scanner.trace(router, seconds=30, gap=10, sleep=lambda s: None))
    assert [event["type"] for event in events] == [
        "trace_start", "trace_sample", "trace_sample", "trace_sample", "trace_done"]
    assert events[-1]["run"]["kind"] == "test"
    assert events[-1]["run"]["summary"]["floor"] == 8.0


ARRIVES_LOCKED = {"lte_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "7"}]},
                               "all_bands": "3,7"},
                  "nr_info": {"lock_mode": "0"}}


def last_write(session) -> dict:
    endpoint, data = session.posts[-1]
    assert endpoint == "net/lock-freq", "band locks go through net/lock-freq only"
    return data


def test_a_cancelled_scan_puts_back_the_lock_the_router_arrived_with():
    """Fix 8: scan() clears the arriving lock up front so the 5G guard can see what is really
    on air. A scan stopped part way never put it back, so pressing Stop silently destroyed
    the band lock the person had - while telling them the router was as it was before."""
    router, session = build([signal(8)] * 200, lock=ARRIVES_LOCKED)
    events = list(scanner.scan(router=router, device=DEVICE, sides=("lte",),
                               cancelled=lambda: True, sleep=lambda s: None))
    assert events[-1]["type"] == "done"
    restored = last_write(session)["lte_info"]
    assert [entry["band"] for entry in restored["freq_infos"]["freq_info"]] == ["7"]
    assert restored["all_bands"] == "3,7", "the secondary must come back too"


def test_a_crash_mid_scan_puts_the_lock_back_and_still_raises():
    """The restore is best effort and must never swallow the failure that triggered it."""
    router, session = build([signal(8), signal(8), RuntimeError("radio went away")],
                            lock=ARRIVES_LOCKED)
    with pytest.raises(RuntimeError):
        run_scan(router=router, device=DEVICE, sides=("lte",))
    restored = last_write(session)["lte_info"]
    assert [entry["band"] for entry in restored["freq_infos"]["freq_info"]] == ["7"]
    assert restored["all_bands"] == "3,7"


def test_a_cancelled_scan_on_an_unlocked_router_puts_nothing_back():
    """A router that arrived on automatic must be left on automatic: the restore is for a
    lock that existed, not a lock invented from an empty `original`."""
    router, session = build([signal(8)] * 200)
    events = list(scanner.scan(router=router, device=DEVICE, sides=("lte",),
                               cancelled=lambda: True, sleep=lambda s: None))
    assert events[-1]["type"] == "done"
    assert all(data["lte_info"]["lock_mode"] == "0" and data["nr_info"]["lock_mode"] == "0"
               for _, data in session.posts), "nothing beyond the per-side clear may be written"


def test_an_auto_win_keeps_the_arriving_nr_lock_and_still_says_kept_auto():
    """choose() refills the untouched 5G side from `original`, so the plan is non-empty even
    though the scan picked nothing. Writing it is right; announcing 'Locked to ...' is not -
    the finding is that automatic won."""
    lock = {"lte_info": {"lock_mode": "0"},
            "nr_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "78"}]},
                        "all_bands": "78"}}
    router, session = build([signal(8)] * 13 + [signal(20)] * 6, bands="1,7", lock=lock)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    assert any(event["type"] == "kept_auto" for event in events)
    assert not any(event["type"] == "applied" for event in events)
    written = last_write(session)["nr_info"]
    assert [entry["band"] for entry in written["freq_infos"]["freq_info"]] == ["78"]


def test_a_5g_scan_that_picks_nothing_gives_nothing_up():
    """A side the scan touched but concluded nothing about keeps what it arrived with: one
    NR band answering is not a finding, so both the 5G lock and the 4G anchor come back and
    the run says 'unchanged' rather than claiming it locked anything."""
    lock = {"lte_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "7"}]},
                         "all_bands": "7"},
            "nr_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "78"}]},
                        "all_bands": "78"}}
    router, session = build([signal(8)] * 200, lock=lock)
    events = run_scan(router=router, device=DEVICE, sides=("nr",))
    written = last_write(session)
    assert [entry["band"] for entry in written["lte_info"]["freq_infos"]["freq_info"]] == ["7"]
    assert [entry["band"] for entry in written["nr_info"]["freq_infos"]["freq_info"]] == ["78"]
    assert [event["type"] for event in events if event["type"] in
            ("applied", "kept_auto", "unchanged")] == ["unchanged"]


def test_a_scan_where_nothing_ranks_puts_the_arriving_lock_back():
    """Every set skipped for no service is not a verdict on the person's lock either. Both
    sides were scanned and neither concluded anything, so the lock arrives back intact."""
    lock = {"lte_info": ARRIVES_LOCKED["lte_info"],
            "nr_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "78"}]},
                        "all_bands": "78"}}
    router, session = build([signal(8, band="")] * 200, lock=lock)
    events = run_scan(router=router, device=DEVICE, sides=("lte", "nr"))
    assert not events[-1]["run"]["sides"]["lte"]["order"], "nothing may have ranked"
    restored = last_write(session)
    assert [entry["band"] for entry in restored["lte_info"]["freq_infos"]["freq_info"]] == ["7"]
    assert restored["lte_info"]["all_bands"] == "3,7"
    # the 5G side is what proves this is the restore and not a per-side clear: every clear
    # leaves the side it just measured on automatic, and 5G is the side measured last
    assert [entry["band"] for entry in restored["nr_info"]["freq_infos"]["freq_info"]] == ["78"]
    assert any(event["type"] == "unchanged" for event in events)


def test_an_auto_win_is_the_one_case_that_gives_a_lock_up():
    """The auto row beating every band is a conclusion about the LTE side: automatic is
    better than what the person arrived on, so the arriving LTE lock is deliberately not
    put back and the person is told why."""
    router, session = build([signal(8)] * 13 + [signal(20)] * 6, bands="1,7", lock=ARRIVES_LOCKED)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    assert any(event["type"] == "kept_auto" for event in events)
    assert not any(event["type"] == "unchanged" for event in events)
    assert last_write(session)["lte_info"]["lock_mode"] == "0", \
        "the arriving LTE lock must not come back when automatic won"


def cancel_scan(router, sides=("lte",)):
    return list(scanner.scan(router=router, device=DEVICE, sides=sides,
                             cancelled=lambda: True, sleep=lambda s: None))


def test_a_restore_the_router_refuses_is_reported_not_swallowed():
    """The person is told the run stopped; if the lock could not go back they are on
    automatic without knowing it, which is the false sentence this fix exists to stop."""
    router, session = build([signal(8)] * 200, lock=ARRIVES_LOCKED)
    accept = session.post_set

    def refuse_to_lock(endpoint, data):      # the clears still work; only putting a lock back fails
        if data["lte_info"]["lock_mode"] != "0" or data["nr_info"]["lock_mode"] != "0":
            raise hx.ResponseErrorException("100006", 100006)
        return accept(endpoint, data)

    session.post_set = refuse_to_lock
    kinds = [event["type"] for event in cancel_scan(router)]
    assert "lock_lost" in kinds
    assert "lock_back" not in kinds


def test_a_successful_restore_says_the_lock_is_back():
    router, _ = build([signal(8)] * 200, lock=ARRIVES_LOCKED)
    kinds = [event["type"] for event in cancel_scan(router)]
    assert "lock_back" in kinds
    assert "lock_lost" not in kinds


def test_a_router_that_arrived_unlocked_gets_neither_sentence():
    """Nothing was taken away, so there is nothing to report putting back."""
    router, _ = build([signal(8)] * 200)
    kinds = [event["type"] for event in cancel_scan(router)]
    assert "lock_back" not in kinds and "lock_lost" not in kinds


def test_the_restore_puts_back_every_nr_band_not_just_the_anchor():
    """A router arriving with two NR bands must not come back one band narrower - the
    difference is a carrier the person had and would never be told they lost."""
    lock = {"lte_info": {"lock_mode": "0"},
            "nr_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "78"}]},
                        "all_bands": "78,79"}}
    router, session = build([signal(8)] * 200, lock=lock)
    cancel_scan(router)
    restored = last_write(session)["nr_info"]
    assert [entry["band"] for entry in restored["freq_infos"]["freq_info"]] == ["78"]
    assert restored["all_bands"] == "78,79"


def test_a_cancelled_full_scan_says_it_stopped_once():
    """Each side reports its own cancellation; the reader needs to be told once."""
    router, _ = build([signal(8)] * 200, lock=ARRIVES_LOCKED)
    events = cancel_scan(router, sides=("lte", "nr"))
    assert [event["type"] for event in events].count("cancelled") == 1


def test_closing_the_generator_after_the_restore_does_not_restore_twice():
    """The restore event is yielded before the scan marks the lock settled, so a reader that
    stops there leaves the generator to unwind through its finally and write the same lock a
    second time - another real band change, another half minute off the air."""
    router, session = build([signal(8)] * 200, lock=ARRIVES_LOCKED)
    events = scanner.scan(router=router, device=DEVICE, sides=("lte",),
                          cancelled=lambda: True, sleep=lambda s: None)
    for event in events:
        if event["type"] in ("lock_back", "lock_lost"):
            break
    events.close()
    puts_back = [data for _, data in session.posts if data["lte_info"]["lock_mode"] != "0"]
    assert len(puts_back) == 1, "the lock the router arrived with is put back once, not twice"


def nr_signal(nrsinr, band="B7(N78)"):
    return {"band": band, "sinr": "8", "rsrq": "-10", "rsrp": "-85",
            "nrsinr": f"{nrsinr}", "nrrsrp": "-80"}


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


def test_a_test_stopped_before_its_first_sample_ends_without_a_summary():
    """summarise([]) used to raise IndexError here, which the page showed as 'an unexpected
    problem' for the most ordinary thing a person can do: press Stop straight away."""
    router, _ = build([signal(8)])
    events = list(scanner.trace(router, seconds=20, gap=10,
                                cancelled=lambda: True, sleep=lambda s: None))
    assert [event["type"] for event in events] == ["trace_start", "cancelled"]


def test_sides_and_other_agree():
    assert set(scanner.SIDES) == set(scanner.OTHER) == set(scanner.OTHER.values())


def test_run_start_carries_the_plan_for_every_side_so_the_page_can_show_both_etas():
    router, _ = build([signal(8)] * 400)
    start = run_scan(router=router, device=DEVICE, sides=("lte", "nr"))[0]
    assert start["plan"]["lte"]["total"] == 3 and start["plan"]["nr"]["total"] == 2
    assert start["plan"]["nr"]["eta_s"] == 2 * scanner.PER_SET


def test_a_plain_trace_never_writes_to_the_router():
    router, session = build([signal(8)] * 50)
    list(scanner.trace(router, seconds=20, gap=10, sleep=lambda s: None))
    assert not [p for p in session.posts if p[0] == "net/lock-freq"]


def test_a_trace_of_a_chosen_band_locks_it_first_and_puts_the_arriving_lock_back():
    router, session = build([signal(8)] * 50, lock=ARRIVES_LOCKED)
    events = list(scanner.trace(router, seconds=20, gap=10, sleep=lambda s: None, lte=["3"]))
    writes = [p[1] for p in session.posts if p[0] == "net/lock-freq"]
    assert writes[0]["lte_info"]["freq_infos"]["freq_info"] == [{"band": "3"}]
    assert writes[-1]["lte_info"]["freq_infos"]["freq_info"] == [{"band": "7"}]
    assert writes[-1]["lte_info"]["all_bands"] == "3,7"
    assert events[-1]["type"] == "trace_done"


def test_a_trace_of_a_chosen_band_restores_the_lock_even_when_the_router_dies_mid_test():
    router, session = build([signal(8)] * 2 + [hx.ResponseErrorException("x", 1)], lock=ARRIVES_LOCKED)
    with pytest.raises(Exception):
        list(scanner.trace(router, seconds=40, gap=10, sleep=lambda s: None, lte=["3"]))
    writes = [p[1] for p in session.posts if p[0] == "net/lock-freq"]
    assert writes[-1]["lte_info"]["freq_infos"]["freq_info"] == [{"band": "7"}]


def test_a_trace_can_lock_a_4g_and_a_5g_band_together_with_secondaries():
    router, session = build([signal(8)] * 50, lock=ARRIVES_LOCKED)
    list(scanner.trace(router, seconds=20, gap=10, sleep=lambda s: None, lte=["3"], nr=["78"], lte_scell=["1"]))
    first = [p[1] for p in session.posts if p[0] == "net/lock-freq"][0]
    assert first["lte_info"]["all_bands"] == "1,3"
    assert first["nr_info"]["freq_infos"]["freq_info"] == [{"band": "78"}]


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
