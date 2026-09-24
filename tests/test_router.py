import pytest
from collections import OrderedDict
from huawei_lte_api import exceptions as hx

from cpe_band_scan.router import Router, RouterError, normalise_url
from tests.fakes import FakeSession, factory


@pytest.mark.parametrize("given,expected", [
    ("192.168.8.1", "http://192.168.8.1/"),
    ("  192.168.8.1  ", "http://192.168.8.1/"),
    ("http://192.168.1.1", "http://192.168.1.1/"),
    ("http://192.168.1.1/", "http://192.168.1.1/"),
    ("https://router.local/", "https://router.local/"),
])
def test_normalise_url(given, expected):
    assert normalise_url(given) == expected


def test_get_returns_payload():
    session = FakeSession({"device/signal": {"band": "7"}})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    assert router.get("device/signal") == {"band": "7"}


def test_config_endpoints_use_the_config_prefix():
    session = FakeSession({"config/network/bandfreqlist.xml": {"config": {"lte_support_band_list": "1,3"}}})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    assert router.get("config/network/bandfreqlist.xml")["config"]["lte_support_band_list"] == "1,3"


def test_wrong_password_is_reported_as_bad_password():
    router = Router("192.168.8.1", "pw",
                    connection_factory=factory(connect_error=hx.LoginErrorUsernamePasswordWrongException("no", 108001)))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "bad_password"


def test_the_rejected_login_carries_the_routers_own_code():
    """108001 (username), 108002 (password) and 108006 (both) all read as one sentence, so the
    code the router sent is the only way back to which of the three it was."""
    router = Router("192.168.8.1", "pw",
                    connection_factory=factory(connect_error=hx.LoginErrorUsernameWrongException(
                        "108001: Username wrong", 108001)))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert "108001" in caught.value.detail


def test_a_blank_password_is_refused_before_the_router_is_called():
    def explode(*args, **kwargs):
        raise AssertionError("a blank password reached the router")

    router = Router("192.168.8.1", "", connection_factory=explode)
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "no_password"


def test_too_many_attempts_is_reported_as_locked_out():
    router = Router("192.168.8.1", "pw",
                    connection_factory=factory(connect_error=hx.LoginErrorUsernamePasswordOverrunException("no", 108002)))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "locked_out"


def test_no_route_to_host_is_reported_as_unreachable():
    router = Router("192.168.8.1", "pw",
                    connection_factory=factory(connect_error=OSError("No route to host")))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "unreachable"


def test_a_non_huawei_answer_is_reported_as_not_huawei_api():
    """Seen in the field: the box answers 200 with an HTML redirect, the library dies on KeyError('token')."""
    router = Router("192.168.8.1", "pw", connection_factory=factory(connect_error=KeyError("token")))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "not_huawei_api"


def test_a_refused_api_call_keeps_the_endpoint_in_the_detail():
    session = FakeSession({"net/lock-freq": hx.ResponseErrorException("100006", 100006)})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    with pytest.raises(RouterError) as caught:
        router.get("net/lock-freq")
    assert caught.value.code == "api_refused"
    assert "net/lock-freq" in caught.value.detail


def test_post_reaches_the_session():
    session = FakeSession()
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    router.post("net/lock-freq", OrderedDict(lte_info={}))
    assert session.posts == [("net/lock-freq", OrderedDict(lte_info={}))]


def test_a_timeout_mid_session_is_reported_as_unreachable():
    """Login worked minutes ago; now the router is off. requests raises an OSError subclass
    from inside get(), and the person should read the same sentence as for a wrong address."""
    session = FakeSession({"device/signal": OSError("timed out")})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "unreachable"


def test_a_write_to_a_router_that_went_away_is_reported_as_unreachable():
    session = FakeSession({"POST net/lock-freq": OSError("connection reset")})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    with pytest.raises(RouterError) as caught:
        router.post("net/lock-freq", OrderedDict())
    assert caught.value.code == "unreachable"


def test_a_router_that_accepts_but_never_answers_is_unreachable_not_a_hang(monkeypatch):
    """Without a timeout the library waits forever, and a scan stuck inside a read never
    reaches the finally that puts the person's lock back."""
    import socket
    import time
    from cpe_band_scan import router as router_module

    monkeypatch.setattr(router_module, "TIMEOUT", (0.2, 0.2))
    listener = socket.create_server(("127.0.0.1", 0))
    try:
        router = Router(f"127.0.0.1:{listener.getsockname()[1]}", "pw")
        began = time.monotonic()
        with pytest.raises(RouterError) as caught:
            router.get("device/signal")
        assert caught.value.code == "unreachable"
        assert time.monotonic() - began < 5
    finally:
        listener.close()
