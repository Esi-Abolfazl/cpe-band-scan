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
    connect_error=hx.LoginErrorUsernamePasswordWrongException("108006: Username and Password wrong", 108006))],
    indirect=True)
def test_a_rejected_login_comes_back_as_a_sentence_carrying_the_routers_code(live):
    session, port = live
    status, body = call(port, "POST", ROUTES["connect"],
                        {"url": "192.168.8.1", "password": "nope"}, token=session.token)
    assert status == 409
    assert body["error"] == "bad_password"
    assert "admin username and password" in body["message"]
    assert "108006" in body["message"]


@pytest.mark.parametrize("live", [fake_router_factory(
    {"device/information": {"DeviceName": "B525", "SoftwareVersion": "3.11.1"},
     "net/lock-freq": hx.ResponseErrorException("not here", 100002)})], indirect=True)
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


def test_the_username_the_page_sends_is_the_one_the_next_visit_starts_with(live):
    """Nothing on the page used to carry a username, so a router whose admin account isn't
    admin failed with the wrong-password sentence and no way to correct it."""
    from cpe_band_scan import store
    session, port = live
    status, _ = call(port, "POST", ROUTES["connect"],
                     {"url": "192.168.8.1", "password": "pw", "username": "operator"},
                     token=session.token)
    assert status == 200
    assert store.settings()["username"] == "operator"
    _, page = call(port, "GET", "/")
    assert '"username": "operator"' in page


def test_a_blank_password_is_refused_with_its_own_sentence(live):
    session, port = live
    status, body = call(port, "POST", ROUTES["connect"],
                        {"url": "192.168.8.1", "password": ""}, token=session.token)
    assert status == 409
    assert body["error"] == "no_password"


def test_the_page_shows_the_router_address_the_way_a_person_types_it(live):
    from cpe_band_scan import store
    store.save_settings(router_url="http://192.168.1.1/", username="admin")
    session, port = live
    _, page = call(port, "GET", "/")
    assert '"url": "192.168.1.1"' in page


@pytest.fixture
def connected():
    """A server whose session is already connected to one FakeSession the test can inspect."""
    fake = FakeSession(dict(SUPPORTED))
    session = server.Session(router_factory=lambda url, password, username: Router(
        url, password, username=username, connection_factory=factory(fake)))
    session.connect("192.168.8.1", "pw", "admin")
    httpd = server.build(port=0, session=session)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    yield session, httpd.server_address[1], fake
    httpd.shutdown()
    httpd.server_close()


def raw(port, method, path, body: bytes, token, length=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.putrequest(method, path)
    connection.putheader("X-CPE-Band-Scan-Token", token)
    connection.putheader("Content-Length", str(len(body)) if length is None else length)
    connection.endheaders(body)
    response = connection.getresponse()
    return response.status, json.loads(response.read())


@pytest.mark.parametrize("route", ["apply", "clear", "scan", "test", "connect", "profiles"])
@pytest.mark.parametrize("body", [b"{broken", b"[]", b"null", b'"x"', b"\xff"])
def test_a_body_that_is_not_a_json_object_is_refused_before_anything_is_written(connected, route, body):
    """Regression: bad JSON was read as {}, so `clear` with a broken body cleared the lock,
    and `[]` or `null` crashed the handler with no answer at all."""
    session, port, fake = connected
    status, answer = raw(port, "POST", ROUTES[route], body, session.token)
    assert (status, answer["error"]) == (400, "bad_request")
    assert fake.posts == [] and session.thread is None


@pytest.mark.parametrize("length", ["x", "-1", str(server.MAX_BODY + 1)])
def test_a_body_length_that_cannot_be_trusted_is_refused(connected, length):
    session, port, fake = connected
    status, answer = raw(port, "POST", ROUTES["clear"], b"{}", session.token, length=length)
    assert (status, answer["error"]) == (400, "bad_request")
    assert fake.posts == []


def test_a_handler_that_crashes_still_answers_in_json(connected, monkeypatch):
    session, port, _ = connected
    monkeypatch.setitem(api.HANDLERS, ("POST", "clear"), lambda *args: 1 / 0)
    status, answer = raw(port, "POST", ROUTES["clear"], b"{}", session.token)
    assert (status, answer["error"]) == (500, "crash")
