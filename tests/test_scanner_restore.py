"""Whatever ends a scan, the lock the router arrived with goes back, and the run says so."""
import pytest
from huawei_lte_api import exceptions as hx
from cpe_band_scan import scanner, speed
from cpe_band_scan.router import Router, RouterError
from tests.fakes import FakeSession, FakeProbe, Seq, factory
from tests.fake_scan_router import DEVICE, signal, build, run_scan, _LockAwareSession, ARRIVES_LOCKED, last_write, cancel_scan


def test_cancelling_stops_the_scan_and_restores_automatic():
    router, session = build([signal(8)] * 200)
    events = list(scanner.scan(router=router, device=DEVICE, sides=("lte",),
                               cancelled=lambda: True, sleep=lambda s: None))
    assert events[-1]["type"] == "done"
    assert any(event["type"] == "cancelled" for event in events)
    assert session.posts, "the finally block must still clear the lock"
    assert session.posts[-1][1]["lte_info"]["lock_mode"] == "0"

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

def _puts_back(session):
    return [data for _, data in session.posts if data["lte_info"]["lock_mode"] != "0"]

def test_a_scan_that_fails_before_its_first_band_still_puts_the_arriving_lock_back():
    """The up-front clear is the scan's first write, so the restore has to cover it: a signal
    read failing straight after it used to leave the person on automatic, their lock gone."""
    router, session = build([hx.ResponseErrorException("x", 1)], lock=ARRIVES_LOCKED)
    with pytest.raises(RouterError):
        run_scan(router=router, device=DEVICE, sides=("lte",))
    assert len(_puts_back(session)) == 1
    assert last_write(session)["lte_info"]["all_bands"] == "3,7"

def test_a_reader_that_stops_at_run_start_still_gets_the_arriving_lock_back():
    router, session = build([signal(8)] * 200, lock=ARRIVES_LOCKED)
    events = scanner.scan(router=router, device=DEVICE, sides=("lte",), sleep=lambda s: None)
    assert next(events)["type"] == "run_start"
    events.close()
    assert len(_puts_back(session)) == 1
    assert last_write(session)["lte_info"]["all_bands"] == "3,7"
