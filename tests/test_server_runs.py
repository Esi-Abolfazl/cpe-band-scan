import pytest

from cpe_band_scan.api import ROUTES
from tests.test_server import call, fake_router_factory, live  # noqa: F401

RUN = {"kind": "scan", "device": {"carrier": "MCI"},
       "sides": {"lte": {"order": ["B7"], "results": {"B7": {"floor": 7}}, "sets": {"B7": ["7"]},
                         "skipped": {}}}}


def test_an_empty_list_is_an_empty_list_not_an_error(live):
    session, port = live
    status, body = call(port, "GET", ROUTES["runs"], token=session.token)
    assert status == 200 and body["runs"] == []


def test_saving_returns_the_stored_run_with_its_name_and_id(live):
    session, port = live
    status, body = call(port, "POST", ROUTES["runs"], {"run": RUN, "name": "Living room"},
                        token=session.token)
    assert status == 200
    assert body["run"]["name"] == "Living room"
    assert body["run"]["id"]


def test_a_saved_run_can_be_opened_again(live):
    session, port = live
    _, saved = call(port, "POST", ROUTES["runs"], {"run": RUN}, token=session.token)
    status, body = call(port, "GET", ROUTES["run"].format(id=saved['run']['id']), token=session.token)
    assert status == 200 and body["run"]["sides"]["lte"]["order"] == ["B7"]


def test_renaming_keeps_the_results(live):
    session, port = live
    _, saved = call(port, "POST", ROUTES["runs"], {"run": RUN}, token=session.token)
    status, body = call(port, "POST", ROUTES["run_rename"].format(id=saved['run']['id']), {"name": "Bedroom"},
                        token=session.token)
    assert status == 200 and body["run"]["name"] == "Bedroom"
    assert body["run"]["sides"]["lte"]["order"] == ["B7"]


def test_deleting_removes_it(live):
    session, port = live
    _, saved = call(port, "POST", ROUTES["runs"], {"run": RUN}, token=session.token)
    assert call(port, "DELETE", ROUTES["run"].format(id=saved['run']['id']), token=session.token)[0] == 200
    assert call(port, "GET", ROUTES["runs"], token=session.token)[1]["runs"] == []


def test_an_unknown_run_is_a_404_not_a_crash(live):
    session, port = live
    assert call(port, "GET", ROUTES["run"].format(id="20260101-000000"), token=session.token)[0] == 404


def test_a_run_id_that_walks_the_filesystem_is_refused(live):
    session, port = live
    assert call(port, "GET", ROUTES["run"].format(id="..%2f..%2fetc%2fpasswd"), token=session.token)[0] == 404


# ---- lock profiles ---------------------------------------------------------------------------
from tests.test_server_jobs import _LTE_LOCKED_FACTORY, _LTE_LOCKED_FAKE, connect  # noqa: E402


def test_saving_a_profile_reads_the_lock_from_the_router(live):
    session, port = live
    session._router_factory = _LTE_LOCKED_FACTORY
    connect(port, session)
    status, body = call(port, "POST", ROUTES["profiles"], {"name": "Home"}, token=session.token)
    assert status == 200
    assert body["profile"]["name"] == "Home" and body["profile"]["carrier"] == "MCI"
    assert body["profile"]["lock"]["lte"] == [["7"], []]
    _, listed = call(port, "GET", ROUTES["profiles"], token=session.token)
    assert [row["id"] for row in listed["profiles"]] == [body["profile"]["id"]]


def test_applying_a_profile_writes_its_whole_lock(live):
    session, port = live
    session._router_factory = _LTE_LOCKED_FACTORY
    connect(port, session)
    _, body = call(port, "POST", ROUTES["profiles"], {"name": "Home"}, token=session.token)
    status, _ = call(port, "POST", ROUTES["profile_apply"].format(id=body['profile']['id']), {}, token=session.token)
    assert status == 200
    _, payload = _LTE_LOCKED_FAKE.posts[-1]
    assert payload["lte_info"]["freq_infos"]["freq_info"] == [{"band": "7"}]
    assert payload["nr_info"]["lock_mode"] == "0"


def test_a_profile_can_be_renamed_and_deleted_over_the_api(live):
    session, port = live
    session._router_factory = _LTE_LOCKED_FACTORY
    connect(port, session)
    _, body = call(port, "POST", ROUTES["profiles"], {"name": "Home"}, token=session.token)
    pid = body["profile"]["id"]
    _, renamed = call(port, "POST", ROUTES["profile_rename"].format(id=pid), {"name": "Office"}, token=session.token)
    assert renamed["profile"]["name"] == "Office"
    assert call(port, "DELETE", ROUTES["profile"].format(id=pid), token=session.token)[0] == 200
    assert call(port, "GET", ROUTES["profiles"], token=session.token)[1]["profiles"] == []
    assert call(port, "POST", ROUTES["profile_apply"].format(id=pid), {}, token=session.token)[0] == 404


def test_a_remembered_password_signs_in_without_being_typed_again(live):
    session, port = live
    status, _ = call(port, "POST", ROUTES["connect"],
                     {"url": "192.168.8.1", "password": "pw", "remember": True}, token=session.token)
    assert status == 200
    from cpe_band_scan import store
    assert store.remembered_password() == "pw"
    status, _ = call(port, "POST", ROUTES["connect"], {"url": "192.168.8.1"}, token=session.token)
    assert status == 200
    call(port, "POST", ROUTES["forget"], {}, token=session.token)
    assert store.remembered_password() == ""
