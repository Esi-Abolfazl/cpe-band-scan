"""Which scan the page shows as the results: the last one that measured a band, whatever ran since."""
from cpe_band_scan import api, server
from cpe_band_scan.api import ROUTES
from tests.test_server import call, live  # noqa: F401  (live is a fixture)
from tests.test_server_jobs import connect, drain


def _finish(session, run):
    session.start("scan", lambda cancelled: iter([{"type": "done", "run": run}]))
    session.thread.join(5)


def test_a_scan_that_measured_nothing_keeps_the_last_results(live, monkeypatch):
    """Regression: a scan stopped before its first band replaced the finished tables with an
    empty one."""
    monkeypatch.setattr(api, "SLEEP", lambda seconds: None)
    session, port = live
    connect(port, session)
    call(port, "POST", ROUTES["scan"], {"sides": ["lte"], "bands": ["7"]}, token=session.token)
    drain(port, session)
    _finish(session, {"kind": "scan", "sides": {"lte": {"results": {}, "order": []}}})
    _, body = call(port, "GET", ROUTES["events"] + "?since=0", token=session.token)
    assert "B7" in body["results"]["sides"]["lte"]["results"]


def test_a_reload_after_a_test_still_gets_the_last_scan(live, monkeypatch):
    """Regression: a reload replayed only the last job, the test, so the finished scan's tables
    and the test picker were gone."""
    monkeypatch.setattr(api, "SLEEP", lambda seconds: None)
    session, port = live
    connect(port, session)
    call(port, "POST", ROUTES["scan"], {"sides": ["lte"], "bands": ["7"]}, token=session.token)
    scan = next(event for event in drain(port, session) if event["type"] == "done")["run"]
    call(port, "POST", ROUTES["test"], {"seconds": 20, "gap": 10}, token=session.token)
    drain(port, session)
    _, body = call(port, "GET", ROUTES["events"] + "?since=0", token=session.token)
    assert body["results"] == server.finite(scan)
