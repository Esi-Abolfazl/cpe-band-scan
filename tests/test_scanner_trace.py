"""The test (trace) of one lock: samples, summary, and the lock it puts back."""
import pytest
from huawei_lte_api import exceptions as hx
from cpe_band_scan import scanner, speed
from cpe_band_scan.router import RouterError
from tests.fakes import Seq
from tests.fake_scan_router import signal, build, ARRIVES_LOCKED


def test_trace_yields_one_sample_per_step_and_a_summary():
    router, _ = build([signal(8)] * 50)
    events = list(scanner.trace(router, seconds=30, gap=10, sleep=lambda s: None))
    assert [event["type"] for event in events] == [
        "trace_start", "trace_sample", "trace_sample", "trace_sample", "trace_done"]
    assert events[-1]["run"]["kind"] == "test"
    assert events[-1]["run"]["summary"]["floor"] == 8.0

def test_a_test_stopped_before_its_first_sample_ends_without_a_summary():
    """summarise([]) used to raise IndexError here, which the page showed as 'an unexpected
    problem' for the most ordinary thing a person can do: press Stop straight away."""
    router, _ = build([signal(8)])
    events = list(scanner.trace(router, seconds=20, gap=10,
                                cancelled=lambda: True, sleep=lambda s: None))
    assert [event["type"] for event in events] == ["trace_start", "cancelled"]

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

def test_a_test_whose_lock_read_back_fails_still_puts_the_arriving_lock_back():
    """The test lock is the first write, so the restore must cover the read that follows it."""
    router, session = build([signal(8)] * 50, lock=ARRIVES_LOCKED)
    session.data["net/lock-freq"] = Seq([ARRIVES_LOCKED, hx.ResponseErrorException("x", 1)])
    with pytest.raises(RouterError):
        list(scanner.trace(router, seconds=20, gap=10, sleep=lambda s: None, lte=["3"]))
    writes = [p[1] for p in session.posts if p[0] == "net/lock-freq"]
    assert writes[-1]["lte_info"]["freq_infos"]["freq_info"] == [{"band": "7"}]

def test_a_reader_that_stops_at_trace_start_still_gets_the_arriving_lock_back():
    router, session = build([signal(8)] * 50, lock=ARRIVES_LOCKED)
    events = scanner.trace(router, seconds=20, gap=10, sleep=lambda s: None, lte=["3"])
    assert next(events)["type"] == "trace_start"
    events.close()
    writes = [p[1] for p in session.posts if p[0] == "net/lock-freq"]
    assert len(writes) == 2 and writes[-1]["lte_info"]["freq_infos"]["freq_info"] == [{"band": "7"}]

def test_a_5g_only_test_is_rated_on_the_5g_carrier():
    weak_anchor = {"band": "B7(N78)", "sinr": "-8", "rsrq": "-18", "rsrp": "-100", "nrsinr": "12", "nrrsrp": "-80"}
    router, _ = build([weak_anchor] * 50)
    events = list(scanner.trace(router, seconds=20, gap=10, sleep=lambda s: None, nr=["78"]))
    assert events[-1]["run"]["summary"]["grade"] == "excellent"
