"""Connect, scan, rank, apply, save, reopen — through real HTTP, against a fake router."""
import time

import pytest

from cpe_band_scan import server
from tests.test_server import call, fake_router_factory, live  # noqa: F401


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(server.scanner, "SETTLE", 0)
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)


def test_the_whole_journey(live):
    session, port = live

    status, connected = call(port, "POST", "/api/connect",
                             {"url": "192.168.8.1", "password": "pw"}, token=session.token)
    assert status == 200 and connected["device"]["driver"] == "lockfreq"

    assert call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["1", "7"]},
                token=session.token)[0] == 200

    since, run = 0, None
    deadline = time.time() + 10
    while time.time() < deadline and run is None:
        _, body = call(port, "GET", f"/api/events?since={since}", token=session.token)
        since = body["since"]
        for event in body["events"]:
            if event["type"] == "done":
                run = event["run"]
        time.sleep(0.05)
    assert run, "the scan never produced a run document"

    order = run["sides"]["lte"]["order"]
    assert order, "the scan produced no ranking"
    assert run["applied"]["lte"], "the winner was not applied"

    _, saved = call(port, "POST", "/api/runs", {"run": run, "name": "End to end"},
                    token=session.token)
    _, listed = call(port, "GET", "/api/runs", token=session.token)
    assert listed["runs"][0]["name"] == "End to end"

    _, reopened = call(port, "GET", f"/api/runs/{saved['run']['id']}", token=session.token)
    assert reopened["run"]["sides"]["lte"]["order"] == order

    assert call(port, "POST", "/api/apply", {"lte": ["7"], "scell": ["3"]},
                token=session.token)[0] == 200
    assert call(port, "POST", "/api/clear", {}, token=session.token)[0] == 200
