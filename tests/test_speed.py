"""The speed probe, against servers on 127.0.0.1 only. Nothing here reaches the internet."""
import http.server
import socket
import struct
import threading
import time
from urllib.parse import parse_qs, urlparse

import pytest

from cpe_band_scan import speed


def test_source_ip_for_loopback_is_loopback():
    assert speed.source_ip("127.0.0.1") == "127.0.0.1"


def test_lan_route_finds_the_loopback_interface_for_a_loopback_router():
    route = speed.lan_route("127.0.0.1")
    assert route.router_ip == "127.0.0.1"
    assert route.lan_ip == "127.0.0.1"
    # scoping may be refused on some hosts (no capability); then ifindex is None and the
    # source bind alone carries the bypass - both outcomes are legal here
    assert route.ifindex is None or route.ifname


def test_open_socket_is_bound_to_the_lan_address_with_a_timeout():
    route = speed.lan_route("127.0.0.1")
    with speed.open_socket(route) as sock:
        assert sock.getsockname()[0] == "127.0.0.1"
        assert sock.gettimeout() == speed.TIMEOUT
    with speed.open_socket(route, socket.SOCK_DGRAM) as sock:
        assert sock.type == socket.SOCK_DGRAM


@pytest.mark.parametrize("default_ip,lan_ip,lan_public,default_public,expected", [
    ("192.168.1.56", "192.168.1.56", "5.1.1.1", None, "not_needed"),      # no tunnel at all
    ("198.18.0.1", "192.168.1.56", "5.1.1.1", "78.1.1.1", "confirmed"),  # tunnel up, addresses differ
    ("198.18.0.1", "192.168.1.56", "78.1.1.1", "78.1.1.1", "failed"),    # tunnel up, same address
    ("198.18.0.1", "192.168.1.56", None, "78.1.1.1", "blocked"),         # tunnel up, LAN path dead
    ("198.18.0.1", "192.168.1.56", "5.1.1.1", None, "confirmed"),        # default path dead, LAN alive
])
def test_verdict_reads_the_four_cases(default_ip, lan_ip, lan_public, default_public, expected):
    assert speed.verdict(default_ip, lan_ip, lan_public, default_public) == expected


def test_every_verdict_is_one_the_catalogue_can_say():
    from cpe_band_scan import copy
    for name in speed.VERDICTS:
        assert f"probe_{name}" in copy.NOTES


class _FakeSpeedHost(http.server.BaseHTTPRequestHandler):
    """Answers like speed.cloudflare.com: /__down?bytes=N streams N bytes, /cdn-cgi/trace
    reports ip=<what the server saw>."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/__down":
            size = int(parse_qs(url.query)["bytes"][0])
            body = b"x" * size
        elif url.path == "/cdn-cgi/trace":
            body = f"fl=1\nip={self.client_address[0]}\ncolo=TST\n".encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def speed_host(monkeypatch):
    """A local stand-in for the probe host, and the module pointed at it over plain HTTP."""
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _FakeSpeedHost)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    monkeypatch.setattr(speed, "HOST", "127.0.0.1")
    monkeypatch.setattr(speed, "PORT", httpd.server_address[1])
    monkeypatch.setattr(speed, "TLS", False)
    monkeypatch.setattr(speed, "BYTES", 300_000)
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def _dns_answer(query: bytes, ip: str) -> bytes:
    """One A record for whatever was asked, with the answer name as a pointer to the question."""
    question_end = 12
    while query[question_end]:
        question_end += query[question_end] + 1
    question_end += 5
    header = query[:2] + struct.pack("!HHHHH", 0x8180, 1, 1, 0, 0)
    answer = b"\xc0\x0c" + struct.pack("!HHIH", 1, 1, 60, 4) + socket.inet_aton(ip)
    return header + query[12:question_end] + answer


@pytest.fixture
def dns_server():
    """A UDP server on 127.0.0.1 that answers every A question with 10.9.8.7."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(0.2)
    stop = threading.Event()

    def serve():
        while not stop.is_set():
            try:
                query, who = sock.recvfrom(512)
            except socket.timeout:
                continue
            sock.sendto(_dns_answer(query, "10.9.8.7"), who)

    threading.Thread(target=serve, daemon=True).start()
    yield sock.getsockname()
    stop.set()
    sock.close()


ROUTE = speed.Route("127.0.0.1", "127.0.0.1")


def test_resolve_asks_over_the_lan_socket_and_reads_the_a_record(dns_server):
    assert speed.resolve("speed.cloudflare.com", ROUTE, servers=(dns_server,)) == "10.9.8.7"


def test_resolve_falls_through_a_dead_server_to_the_next(dns_server):
    dead = ("127.0.0.1", 9)           # discard port: nothing answers, the timeout moves us on
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(speed, "TIMEOUT", 0.3)
        assert speed.resolve("speed.cloudflare.com", ROUTE, servers=(dead, dns_server)) == "10.9.8.7"


def test_resolve_raises_when_nobody_answers():
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(speed, "TIMEOUT", 0.2)
        with pytest.raises(OSError):
            speed.resolve("speed.cloudflare.com", ROUTE, servers=(("127.0.0.1", 9),))


def test_ping_reports_a_median_and_a_spread_in_whole_milliseconds(speed_host):
    reading = speed.ping(ROUTE, "127.0.0.1")
    assert set(reading) == {"latency_ms", "jitter_ms"}
    assert isinstance(reading["latency_ms"], int) and reading["latency_ms"] >= 0
    assert reading["jitter_ms"] >= 0


def test_download_counts_the_bytes_and_turns_them_into_megabits_per_second(speed_host):
    reading = speed.download(ROUTE, "127.0.0.1")
    assert reading["bytes"] == 300_000
    assert reading["mbps"] > 0 and reading["seconds"] >= 0
    assert set(reading) == {"mbps", "bytes", "seconds"}


def test_download_stops_at_the_window_even_when_more_is_on_offer(speed_host, monkeypatch):
    """A fast link finishes the 50 MB early; a slow one must not sit through all of it."""
    monkeypatch.setattr(speed, "SECONDS", 0.0)      # the window closes on the first chunk
    monkeypatch.setattr(speed, "BYTES", 5_000_000)
    reading = speed.download(ROUTE, "127.0.0.1")
    assert 0 < reading["bytes"] < 5_000_000


def test_public_ip_reads_the_trace_line(speed_host):
    assert speed.public_ip(ROUTE) == "127.0.0.1"
    assert speed.public_ip(None) == "127.0.0.1"


def test_the_probe_starts_with_a_verdict_and_then_measures_each_band(speed_host, dns_server, monkeypatch):
    monkeypatch.setattr(speed, "PUBLIC_DNS", "127.0.0.1")
    monkeypatch.setattr(speed, "resolve", lambda host, route, servers=None, deadline=None: "127.0.0.1")
    probe = speed.SpeedProbe("http://127.0.0.1/")
    report = probe.start()
    assert report["bypass"] == "not_needed"          # loopback is its own default route
    assert report["lan_ip"] == "127.0.0.1" and report["public_ip"] == "127.0.0.1"
    reading = probe.measure()
    assert {"latency_ms", "jitter_ms", "mbps", "bytes", "seconds"} <= set(reading)


def test_a_band_whose_probe_fails_reports_no_answer_not_a_crash(speed_host, monkeypatch):
    monkeypatch.setattr(speed, "PUBLIC_DNS", "127.0.0.1")
    monkeypatch.setattr(speed, "resolve", lambda host, route, servers=None, deadline=None: "127.0.0.1")
    probe = speed.SpeedProbe("http://127.0.0.1/")
    probe.start()
    speed_host.shutdown()                            # the internet went away mid-scan
    speed_host.server_close()
    monkeypatch.setattr(speed, "TIMEOUT", 0.3)
    assert probe.measure() == {"error": "no_answer"}


def test_a_blocked_probe_never_opens_a_socket_per_band(monkeypatch):
    monkeypatch.setattr(speed, "lan_route", lambda router_ip: (_ for _ in ()).throw(OSError("no route")))
    probe = speed.SpeedProbe("http://192.0.2.1/")
    assert probe.start()["bypass"] == "blocked"
    calls = []
    monkeypatch.setattr(speed, "open_socket", lambda *args, **kwargs: calls.append(args))
    assert probe.measure() == {"error": "blocked"}
    assert calls == []


def test_resolve_treats_a_truncated_answer_like_no_answer():
    """One malformed reply from the router's resolver must move on, never abort the scan."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0)); sock.settimeout(0.2)
    stop = threading.Event()
    def serve():
        while not stop.is_set():
            try: query, who = sock.recvfrom(512)
            except socket.timeout: continue
            sock.sendto(_dns_answer(query, "10.9.8.7")[:-3], who)   # cut inside the A record
    threading.Thread(target=serve, daemon=True).start()
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(speed, "TIMEOUT", 0.3)
            with pytest.raises(OSError):
                speed.resolve("speed.cloudflare.com", ROUTE, servers=(sock.getsockname(),))
    finally:
        stop.set(); sock.close()


def test_a_probe_never_outlives_its_duration(monkeypatch):
    """A dead path must cost the scan DURATION at most, or the cancel grace in server.py lies."""
    sink = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sink.bind(("127.0.0.1", 0)); sink.listen(8)          # accepts, never answers
    monkeypatch.setattr(speed, "HOST", "127.0.0.1")
    monkeypatch.setattr(speed, "PORT", sink.getsockname()[1])
    monkeypatch.setattr(speed, "TLS", False)
    monkeypatch.setattr(speed, "DURATION", 0.6)
    monkeypatch.setattr(speed, "resolve", lambda host, route, servers=None, deadline=None: "127.0.0.1")
    probe = speed.SpeedProbe("http://127.0.0.1/")
    probe.route, probe.bypass = ROUTE, "not_needed"
    started = time.monotonic()
    try:
        assert probe.measure() == {"error": "no_answer"}
    finally:
        sink.close()
    assert time.monotonic() - started < speed.DURATION + 0.5


def test_a_deadline_shortens_the_window_but_keeps_a_whole_body(speed_host):
    body, count, _ = speed._get(speed.connect(ROUTE, "127.0.0.1"), "/cdn-cgi/trace",
                                deadline=time.monotonic() + 5)
    assert count and body, "a bounded fetch with no window still returns its body"
