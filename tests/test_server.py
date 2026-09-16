import http.client
import http.server
import json
import threading

import pytest
from huawei_lte_api import exceptions as hx

from cpe_band_scan import api, server
from cpe_band_scan.api import ROUTES
from cpe_band_scan.router import Router
from tests.fakes import FakeProbe, FakeSession, Seq, factory
from tests.test_device import SUPPORTED


def fake_router_factory(data=None, connect_error=None):
    def make(url, password, username="admin"):
        return Router(url, password, username=username,
                      connection_factory=factory(FakeSession(dict(SUPPORTED, **(data or {}))),
                                                 connect_error=connect_error))
    return make


@pytest.fixture
def live(request, monkeypatch):
    """A server on a free port, torn down after the test. Defaults to a fake speed probe so a
    scan test that doesn't care about speed never touches the real network; a test that does
    care overrides `api.PROBE` itself."""
    monkeypatch.setattr(api, "PROBE", lambda url: FakeProbe(url))
    session = server.Session(router_factory=getattr(request, "param", fake_router_factory()))
    httpd = server.build(port=0, session=session)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield session, httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def call(port, method, path, body=None, token=None, host=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-CPE-Band-Scan-Token"] = token
    if host:
        headers["Host"] = host
    connection.request(method, path, json.dumps(body) if body is not None else None, headers)
    response = connection.getresponse()
    payload = response.read()
    try:
        return response.status, json.loads(payload)
    except ValueError:
        return response.status, payload.decode()


def test_the_page_carries_the_token_and_the_copy(live):
    session, port = live
    status, body = call(port, "GET", "/")
    assert status == 200
    assert session.token in body
    assert "Router address" in body, "the copy bundle must reach the page"


def test_an_api_call_without_the_token_is_refused(live):
    _, port = live
    assert call(port, "GET", ROUTES["status"])[0] == 403


def test_an_api_call_from_another_host_name_is_refused(live):
    session, port = live
    status, _ = call(port, "GET", ROUTES["status"], token=session.token, host="router.attacker.test")
    assert status == 403


def test_the_page_from_another_host_name_is_refused(live):
    _, port = live
    status, _ = call(port, "GET", "/", host="router.attacker.test")
    assert status == 403


def test_a_static_asset_from_another_host_name_is_refused(live):
    _, port = live
    status, _ = call(port, "GET", "/app.js", host="router.attacker.test")
    assert status == 403


def test_connecting_reports_the_device_and_suggests_a_name(live):
    session, port = live
    status, body = call(port, "POST", ROUTES["connect"],
                        {"url": "192.168.8.1", "password": "pw"}, token=session.token)
    assert status == 200
    assert body["device"]["model"] == "H155-381"
    assert body["suggested_name"].startswith("MCI — ")


@pytest.mark.parametrize("live", [fake_router_factory(
    connect_error=hx.LoginErrorUsernamePasswordWrongException("no", 108001))], indirect=True)
def test_a_wrong_password_comes_back_as_a_sentence_not_a_code(live):
    session, port = live
    status, body = call(port, "POST", ROUTES["connect"],
                        {"url": "192.168.8.1", "password": "nope"}, token=session.token)
    assert status == 409
    assert body["error"] == "bad_password"
    assert "admin password" in body["message"]


@pytest.mark.parametrize("live", [fake_router_factory(
    {"device/information": {"DeviceName": "B525", "SoftwareVersion": "3.11.1"}})], indirect=True)
def test_an_unsupported_router_explains_why(live):
    session, port = live
    status, body = call(port, "POST", ROUTES["connect"],
                        {"url": "192.168.8.1", "password": "pw"}, token=session.token)
    assert status == 409
    assert body["error"] == "firmware_not_supported"
    assert "3.11.1" in body["message"]


def test_status_before_connecting_says_so(live):
    session, port = live
    status, body = call(port, "GET", ROUTES["status"], token=session.token)
    assert status == 409
    assert body["error"] == "not_connected"


def test_status_after_connecting_returns_the_signal_and_the_lock(live):
    session, port = live
    call(port, "POST", ROUTES["connect"], {"url": "192.168.8.1", "password": "pw"}, token=session.token)
    status, body = call(port, "GET", ROUTES["status"], token=session.token)
    assert status == 200
    assert "signal" in body and "lock" in body and body["device"]["carrier"] == "MCI"
    assert body["suggested_name"].startswith("MCI — ")


def test_serve_stops_a_running_job_and_waits_for_it_before_returning(monkeypatch):
    """Fix 2: pressing Ctrl-C ends serve_forever, but the job runs on a daemon thread. If
    serve() returns without cancelling and joining it, the process exits mid-scan and the
    finally block that restores automatic mode never runs, leaving the router locked."""
    calls = []
    session = server.Session()
    session.cancel = lambda: calls.append("cancel")

    class FakeThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            calls.append(("join", timeout))

    session.thread = FakeThread()
    monkeypatch.setattr(server.ThreadingHTTPServer, "serve_forever",
                        lambda self: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert server.serve(port=0, open_browser=False, session=session) == 0
    assert calls == ["cancel", ("join", server.SETTLE_GRACE)]


def test_serve_does_not_touch_a_session_with_no_job_running(monkeypatch):
    calls = []
    session = server.Session()
    session.cancel = lambda: calls.append("cancel")
    monkeypatch.setattr(server.ThreadingHTTPServer, "serve_forever",
                        lambda self: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert server.serve(port=0, open_browser=False, session=session) == 0
    assert calls == []


def test_binding_never_resolves_the_bind_address(monkeypatch):
    """HTTPServer resolves its bind address by default. On a VPN-routed resolver that call
    blocks for tens of seconds and the page never loads. Timing this would pass on any
    machine with a fast resolver, bug present or not, so assert the call is never made."""
    called = []
    monkeypatch.setattr(http.server.socket, "getfqdn",
                        lambda *args: called.append(args) or "localhost")
    httpd = server.build(port=0, session=server.Session())
    httpd.server_close()
    assert not called, "the reverse DNS lookup is back"


def test_a_non_numeric_since_is_a_bad_request_not_a_crash(live):
    session, port = live
    status, answer = call(port, "GET", ROUTES["events"] + "?since=abc", token=session.token)
    assert (status, answer["error"]) == (400, "bad_request")


@pytest.mark.parametrize("live", [fake_router_factory(
    {"device/signal": {"band": "20MHz@2850(B7) + 20MHz@100(B1)", "sinr": "12dB", "rsrq": "-11dB", "rsrp": "-85dBm"}})],
    indirect=True)
def test_a_router_without_5g_yields_json_a_browser_accepts(live):
    """metrics reports a missing reading as nan; nan is not JSON, and fetch().json() throws on it."""
    session, port = live
    call(port, "POST", ROUTES["connect"], {"url": "192.168.1.1", "password": "pw"}, token=session.token)
    status, body = call(port, "GET", ROUTES["status"], token=session.token)
    assert status == 200
    assert body["signal"]["nrsinr"] is None and body["signal"]["nrrsrp"] is None


def test_the_page_shows_the_router_address_the_way_a_person_types_it(live):
    from cpe_band_scan import store
    store.save_settings(router_url="http://192.168.1.1/", username="admin")
    session, port = live
    _, page = call(port, "GET", "/")
    assert '"url": "192.168.1.1"' in page
