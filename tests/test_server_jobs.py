import time

import pytest

from cpe_band_scan import server
from cpe_band_scan.router import Router
from tests.fakes import FakeSession, factory
from tests.test_device import SUPPORTED
from tests.test_server import call, fake_router_factory, live  # noqa: F401  (live is a fixture)


def connect(port, session):
    return call(port, "POST", "/api/connect", {"url": "192.168.8.1", "password": "pw"},
                token=session.token)


def _locked_router_factory(lock_data):
    """A router factory whose fake session starts with `lock_data` as its net/lock-freq
    reading. The fixture's read is static, so this is how a test represents an existing lock
    rather than relying on a write to change what a later read returns."""
    fake = FakeSession(dict(SUPPORTED, **{"net/lock-freq": lock_data}))

    def make(url, password, username="admin"):
        return Router(url, password, username=username, connection_factory=factory(fake))
    return make, fake


_NR_LOCKED_FACTORY, _NR_LOCKED_FAKE = _locked_router_factory({
    "lte_info": {"lock_mode": "0"},
    "nr_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "78"}]}, "all_bands": "78"},
})

_LTE_LOCKED_FACTORY, _LTE_LOCKED_FAKE = _locked_router_factory({
    "lte_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "7"}]}, "all_bands": "7"},
    "nr_info": {"lock_mode": "0"},
})

_UNLOCKED_DATA = {"lte_info": {"lock_mode": "0"}, "nr_info": {"lock_mode": "0"}}
_APPLY_FACTORY, _APPLY_FAKE = _locked_router_factory(_UNLOCKED_DATA)
_CLEAR_FACTORY, _CLEAR_FAKE = _locked_router_factory(_UNLOCKED_DATA)


def drain(port, session, timeout=5):
    """Poll until the job reports it has finished."""
    since, events = 0, []
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, body = call(port, "GET", f"/api/events?since={since}", token=session.token)
        since, new = body["since"], body["events"]
        events += new
        if any(event["type"] == "finished" for event in new):
            return events
        time.sleep(0.05)
    raise AssertionError(f"job never finished; saw {[e['type'] for e in events]}")


def test_a_scan_cannot_start_before_connecting(live):
    session, port = live
    status, body = call(port, "POST", "/api/scan", {}, token=session.token)
    assert status == 409 and body["error"] == "not_connected"


def test_a_scan_streams_events_and_finishes(live, monkeypatch):
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)
    session, port = live
    connect(port, session)
    assert call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["7"]},
                token=session.token)[0] == 200
    events = drain(port, session)
    kinds = [event["type"] for event in events]
    assert "set_start" in kinds and "done" in kinds and kinds[-1] == "finished"


def test_events_are_only_delivered_once(live, monkeypatch):
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)
    session, port = live
    connect(port, session)
    call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["7"]}, token=session.token)
    drain(port, session)
    _, body = call(port, "GET", f"/api/events?since={len(session.events)}", token=session.token)
    assert body["events"] == []
    assert body["running"] is False


def test_a_second_scan_while_one_runs_is_refused(live, monkeypatch):
    session, port = live
    connect(port, session)
    session.thread = type("Alive", (), {"is_alive": lambda self: True})()
    status, body = call(port, "POST", "/api/scan", {"sides": ["lte"]}, token=session.token)
    assert status == 409 and body["error"] == "busy"


def test_cancelling_sets_the_flag_the_engine_reads(live):
    session, port = live
    connect(port, session)
    assert call(port, "POST", "/api/cancel", {}, token=session.token)[0] == 200
    assert session.cancelled is True


def test_a_crash_inside_the_job_becomes_an_error_event_not_a_dead_poll(live, monkeypatch):
    session, port = live
    connect(port, session)

    def explode(*args, **kwargs):
        raise ZeroDivisionError("boom")

    monkeypatch.setattr(server.scanner, "scan", explode)
    call(port, "POST", "/api/scan", {"sides": ["lte"]}, token=session.token)
    events = drain(port, session)
    assert events[0]["type"] == "error" and events[0]["code"] == "crash"


def test_a_crash_error_event_has_no_unfilled_braces(live, monkeypatch):
    session, port = live
    connect(port, session)

    def explode(*args, **kwargs):
        raise ZeroDivisionError("boom")

    monkeypatch.setattr(server.scanner, "scan", explode)
    call(port, "POST", "/api/scan", {"sides": ["lte"]}, token=session.token)
    events = drain(port, session)
    error = events[0]
    assert error["type"] == "error" and error["code"] == "crash"
    assert "{" not in error["message"] and "}" not in error["message"]


@pytest.mark.parametrize("live", [_APPLY_FACTORY], indirect=True)
def test_applying_a_band_locks_it(live):
    session, port = live
    connect(port, session)
    status, _ = call(port, "POST", "/api/apply", {"lte": ["7"], "scell": ["3"]}, token=session.token)
    assert status == 200
    _, payload = _APPLY_FAKE.posts[-1]
    assert payload["lte_info"]["freq_infos"] == {"freq_info": [{"band": "7"}]}
    assert payload["lte_info"]["all_bands"] == "3,7"


@pytest.mark.parametrize("live", [_NR_LOCKED_FACTORY], indirect=True)
def test_applying_a_4g_band_leaves_an_existing_5g_lock_intact(live):
    session, port = live
    connect(port, session)
    status, _ = call(port, "POST", "/api/apply", {"lte": ["7"]}, token=session.token)
    assert status == 200
    _, payload = _NR_LOCKED_FAKE.posts[-1]
    assert payload["lte_info"]["freq_infos"] == {"freq_info": [{"band": "7"}]}
    assert payload["nr_info"]["freq_infos"] == {"freq_info": [{"band": "78"}]}


@pytest.mark.parametrize("live", [_LTE_LOCKED_FACTORY], indirect=True)
def test_applying_an_explicit_empty_list_clears_that_side(live):
    session, port = live
    connect(port, session)
    status, _ = call(port, "POST", "/api/apply", {"lte": [], "nr": ["78"]}, token=session.token)
    assert status == 200
    _, payload = _LTE_LOCKED_FAKE.posts[-1]
    assert payload["lte_info"]["lock_mode"] == "0"
    assert payload["nr_info"]["freq_infos"] == {"freq_info": [{"band": "78"}]}


@pytest.mark.parametrize("live", [_CLEAR_FACTORY], indirect=True)
def test_clearing_returns_the_router_to_automatic(live):
    session, port = live
    connect(port, session)
    assert call(port, "POST", "/api/clear", {}, token=session.token)[0] == 200
    _, payload = _CLEAR_FAKE.posts[-1]
    assert payload["lte_info"]["lock_mode"] == "0"
    assert payload["nr_info"]["lock_mode"] == "0"


def test_a_two_minute_test_runs_as_a_job(live, monkeypatch):
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)
    session, port = live
    connect(port, session)
    call(port, "POST", "/api/test", {"seconds": 20, "gap": 10}, token=session.token)
    events = drain(port, session)
    assert [event["type"] for event in events][:2] == ["trace_start", "trace_sample"]


@pytest.mark.parametrize("path,body", [
    ("/api/apply", {"lte": ["7"]}),
    ("/api/clear", {}),
    ("/api/connect", {"url": "192.168.8.1", "password": "pw"}),
])
def test_nothing_touches_the_router_while_a_job_runs(live, path, body):
    """The page greys these buttons out, but the page is a mirror. A write that lands mid-scan
    pollutes the measurement in progress and is then overwritten by the scan's own lock."""
    session, port = live
    connect(port, session)
    session.thread = type("Alive", (), {"is_alive": lambda self: True})()
    status, answer = call(port, "POST", path, body, token=session.token)
    assert (status, answer["error"]) == (409, "busy")


@pytest.mark.parametrize("live", [_APPLY_FACTORY], indirect=True)
def test_a_string_band_is_refused_before_it_reaches_the_router(live):
    session, port = live
    connect(port, session)
    before = len(_APPLY_FAKE.posts)
    status, answer = call(port, "POST", "/api/apply", {"lte": "78"}, token=session.token)
    assert (status, answer["error"]) == (400, "bad_request")
    assert len(_APPLY_FAKE.posts) == before, "the router must not have been written to"


def test_an_unknown_side_is_refused_before_a_scan_starts(live):
    session, port = live
    connect(port, session)
    status, answer = call(port, "POST", "/api/scan", {"sides": ["wifi"]}, token=session.token)
    assert (status, answer["error"]) == (400, "bad_request")
    assert not session.running()


@pytest.mark.parametrize("body", [{"seconds": 0}, {"gap": 0}, {"seconds": 10, "gap": 20},
                                  {"seconds": "soon"}])
def test_a_test_with_impossible_timing_is_refused(live, body):
    session, port = live
    connect(port, session)
    status, answer = call(port, "POST", "/api/test", body, token=session.token)
    assert (status, answer["error"]) == (400, "bad_request")


@pytest.mark.parametrize("live", [fake_router_factory({"device/signal": OSError("timed out")})],
                         indirect=True)
def test_a_router_lost_mid_scan_reads_as_unreachable_with_its_address(live, monkeypatch):
    """Signing in worked; the first signal read times out. The person should read the same
    sentence as for a wrong address, and it must name the router rather than end in 'at .'."""
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)
    session, port = live
    connect(port, session)
    call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["7"]}, token=session.token)
    events = drain(port, session)
    error = next(event for event in events if event["type"] == "error")
    assert error["code"] == "unreachable"
    assert "192.168.8.1" in error["message"]


def test_the_write_endpoints_hold_the_session_lock(live):
    """require_idle() then lock() must be one step, or a scan can start in between."""
    import inspect
    from cpe_band_scan import server as srv
    source = inspect.getsource(srv.Handler.do_POST)
    for path in ("/api/connect", "/api/apply", "/api/clear"):
        branch = source[source.index(f'path == "{path}"'):]
        branch = branch[:branch.index("return self._json")]
        assert "with self.session.lock:" in branch, f"{path} writes outside the session lock"


def test_a_test_of_a_chosen_band_locks_it_and_puts_the_lock_back(live, monkeypatch):
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)
    session, port = live
    session._router_factory = _LTE_LOCKED_FACTORY
    connect(port, session)
    call(port, "POST", "/api/test", {"seconds": 20, "gap": 10, "lte": ["3"]}, token=session.token)
    events = drain(port, session)
    assert events[0]["lock"]["lte"][0] == ["7"]     # the fake's read is static; the writes tell
    writes = [payload for endpoint, payload in _LTE_LOCKED_FAKE.posts if endpoint == "net/lock-freq"]
    assert writes[-2]["lte_info"]["freq_infos"]["freq_info"] == [{"band": "3"}]
    assert writes[-1]["lte_info"]["freq_infos"]["freq_info"] == [{"band": "7"}]
    assert events[-2]["type"] == "trace_done"
