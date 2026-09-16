import pytest

from tests.test_server import call, fake_router_factory, live  # noqa: F401

RUN = {"kind": "scan", "device": {"carrier": "MCI"},
       "sides": {"lte": {"order": ["B7"], "results": {"B7": {"floor": 7}}, "sets": {"B7": ["7"]},
                         "skipped": {}}}}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CPE_BAND_SCAN_HOME", str(tmp_path))


def test_an_empty_list_is_an_empty_list_not_an_error(live):
    session, port = live
    status, body = call(port, "GET", "/api/runs", token=session.token)
    assert status == 200 and body["runs"] == []


def test_saving_returns_the_stored_run_with_its_name_and_id(live):
    session, port = live
    status, body = call(port, "POST", "/api/runs", {"run": RUN, "name": "Living room"},
                        token=session.token)
    assert status == 200
    assert body["run"]["name"] == "Living room"
    assert body["run"]["id"]


def test_a_saved_run_can_be_opened_again(live):
    session, port = live
    _, saved = call(port, "POST", "/api/runs", {"run": RUN}, token=session.token)
    status, body = call(port, "GET", f"/api/runs/{saved['run']['id']}", token=session.token)
    assert status == 200 and body["run"]["sides"]["lte"]["order"] == ["B7"]


def test_renaming_keeps_the_results(live):
    session, port = live
    _, saved = call(port, "POST", "/api/runs", {"run": RUN}, token=session.token)
    status, body = call(port, "POST", f"/api/runs/{saved['run']['id']}/rename", {"name": "Bedroom"},
                        token=session.token)
    assert status == 200 and body["run"]["name"] == "Bedroom"
    assert body["run"]["sides"]["lte"]["order"] == ["B7"]


def test_deleting_removes_it(live):
    session, port = live
    _, saved = call(port, "POST", "/api/runs", {"run": RUN}, token=session.token)
    assert call(port, "DELETE", f"/api/runs/{saved['run']['id']}", token=session.token)[0] == 200
    assert call(port, "GET", "/api/runs", token=session.token)[1]["runs"] == []


def test_an_unknown_run_is_a_404_not_a_crash(live):
    session, port = live
    assert call(port, "GET", "/api/runs/20260101-000000", token=session.token)[0] == 404


def test_a_run_id_that_walks_the_filesystem_is_refused(live):
    session, port = live
    assert call(port, "GET", "/api/runs/..%2f..%2fetc%2fpasswd", token=session.token)[0] == 404
