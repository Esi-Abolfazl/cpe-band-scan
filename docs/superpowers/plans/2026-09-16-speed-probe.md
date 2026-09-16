# Per-band speed and ping probe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After each band's radio samples, measure ping and download speed from this computer through the router, past any VPN, and show both next to the rating without letting them touch the ranking.

**Architecture:** One new module, `speed.py`, owns every socket: it finds the interface that reaches the router, scopes and binds each probe socket to it (DNS query included), proves whether the bypass held, and returns plain dicts. `scanner.scan()` takes an optional probe object and attaches its readings to each band's result and its verdict to the run. The server, the CLI and the page only carry a boolean and render what the run says.

**Tech Stack:** Python 3.10+ stdlib only (`socket`, `ssl`, `http.client`, `struct`), pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-09-16-cpe-band-scan-spec.md`, section "Addendum 2026-09-16: per-band speed and ping".

## Global Constraints

- Python `>=3.10`; dependencies stay exactly `["huawei-lte-api>=1.7"]`; no new runtime dependency.
- Every word the person reads lives in `src/cpe_band_scan/copy.py`; app.js and cli.py never hardcode a label (`tests/test_parity.py`, `tests/test_copy.py` enforce this).
- No string may ask the person to turn off, disconnect or disable a VPN (`test_no_string_asks_the_user_to_turn_off_a_vpn`).
- The page and the terminal show the same columns in the same order (`test_results_table_matches_the_pages_column_order`), so both add the two new columns at the same position, only when the run carries speed data.
- Speed and ping never enter `metrics.rank()` (spec R15).
- Probe host `speed.cloudflare.com`; download window 5 s capped at 50 MB; 5 connects for ping; the checkbox help states the data cost (spec R16).
- `PER_SET` stays what it is; the ETA adds `speed.DURATION` per band only when the probe is on.
- Tests never reach the internet: they use local HTTP and DNS servers on 127.0.0.1 and `tests/fakes.FakeProbe`.
- Run `.venv/bin/python -m pytest -q` from the repo root (the `.venv` the `Run on Mac` launcher builds; `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'` if it is missing); all green before every commit. The suite is 292 tests and takes about 30 s. Commit messages follow the repo's `type: sentence` style (`feat:`, `fix:`, `docs:`, `test:`).
- One `git commit` per Bash call, never chained.

---

## File structure

| File | Responsibility |
|---|---|
| Create `src/cpe_band_scan/speed.py` | routing past the VPN, DNS over the LAN, ping, download, verdict, `SpeedProbe` |
| Create `tests/test_speed.py` | local DNS/HTTP servers; every function above; the four verdicts |
| Modify `src/cpe_band_scan/copy.py` | the checkbox, the two columns, four verdict sentences, the no-answer cell, two log lines |
| Modify `tests/test_copy.py` | new placeholders allowed; every verdict has a sentence |
| Modify `src/cpe_band_scan/scanner.py` | `scan(..., probe=None)`; start the probe while the link is up; attach readings |
| Modify `tests/fakes.py`, `tests/test_scanner.py` | `FakeProbe`; readings land on results; ETA grows; off means absent |
| Modify `src/cpe_band_scan/server.py`, `tests/test_server_jobs.py` | `/api/scan` body `speed` (default true); `server.PROBE` swap point |
| Modify `src/cpe_band_scan/cli.py`, `tests/test_cli.py` | `--no-speed`; columns; verdict line; log lines |
| Modify `tools/demo_server.py` | a `FakeProbe` so the demo needs no internet |
| Modify `src/cpe_band_scan/web/app.js`, `tests/test_parity.py`, `tests/test_page_quality.py` | checkbox; columns; note under the table; log lines |
| Modify `README.md`, `skills/bandscan/SKILL.md`, `skills/bandscan/reference.md`, `docs/design/2026-09-16-page-redesign.md` | the feature, the VPN story, the data cost |

---

### Task 1: The words

**Files:**
- Modify: `src/cpe_band_scan/copy.py` (FIELDS, COLUMNS, NOTES, PROGRESS)
- Test: `tests/test_copy.py`

**Interfaces:**
- Produces: `copy.FIELDS["speed_test"]`, `copy.COLUMNS["speed"]`, `copy.COLUMNS["ping"]`, `copy.NOTES["probe_not_needed" | "probe_confirmed" | "probe_failed" | "probe_blocked" | "probe_no_answer"]`, `copy.PROGRESS["log_result_probe"]`, `copy.PROGRESS["set_result_probe"]`. Placeholders `{mbps}` and `{ping}` join the allowed set.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_copy.py`:

```python
VERDICTS = ("not_needed", "confirmed", "failed", "blocked")


@pytest.mark.parametrize("verdict", VERDICTS)
def test_every_bypass_verdict_has_a_sentence(verdict):
    assert copy.NOTES[f"probe_{verdict}"].strip()


def test_the_speed_checkbox_states_the_data_cost():
    entry = copy.FIELDS["speed_test"]
    assert "MB" in entry["help"], "spec R16: the data cost sits next to the checkbox"
    assert "VPN" in entry["help"]


def test_speed_and_ping_columns_exist_and_say_they_are_one_moment():
    assert copy.COLUMNS["speed"]["label"] and copy.COLUMNS["ping"]["label"]
    assert "moment" in copy.COLUMNS["speed"]["help"].lower()


def test_the_probe_log_lines_carry_speed_and_ping():
    for key in ("log_result_probe", "set_result_probe"):
        assert "{mbps}" in copy.PROGRESS[key] and "{ping}" in copy.PROGRESS[key]
```

Also change the allowed placeholder set in `test_error_placeholders_are_only_the_ones_callers_pass`: add `"mbps", "ping"` to the `allowed` set literal.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_copy.py -q`
Expected: FAIL with `KeyError: 'probe_not_needed'` and `KeyError: 'speed_test'`.

- [ ] **Step 3: Add the strings**

In `copy.py`, inside `FIELDS`, after the `"follow"` entry:

```python
    "speed_test": {
        "label": "Measure speed and ping on each band",
        "placeholder": "",
        "help": "Adds about 10 seconds and downloads up to 50 MB of mobile data per band. Goes around "
                "your VPN, so the numbers are the band's, not the VPN's.",
    },
```

Inside `COLUMNS`, after `"carriers"`:

```python
    "speed": {"label": "Speed", "help": "Download in Mbit/s over 5 seconds, straight through the router. "
                                         "One moment's reading: cell load changes it hour to hour."},
    "ping": {"label": "Ping", "help": "Time to reach the internet in ms, the middle of 5 tries. Under 50 "
                                       "feels instant, over 150 you notice."},
```

Inside `NOTES`, after `"vpn"`:

```python
    "probe_not_needed": "No VPN was active, so speed and ping are your plain connection.",
    "probe_confirmed": "Speed and ping were measured straight through the router, past your VPN, so "
                       "they are the band's own numbers.",
    "probe_failed": "Your VPN couldn't be bypassed, so speed and ping include it. Compare rows with "
                    "each other, not with other scans.",
    "probe_blocked": "Your VPN blocks everything outside its tunnel, so speed and ping weren't measured. "
                     "Allow local network access in the VPN's settings, or scan with the speed test "
                     "unticked.",
    "probe_no_answer": "no answer",
```

Inside `PROGRESS`, after `"log_result"` and after `"set_result"` respectively:

```python
    "log_result_probe": "{name}: {grade}, lowest {floor} dB, {mbps} Mbit/s, {ping} ms",
    "set_result_probe": "{name} scored {grade}, lowest quality {floor} dB, {mbps} Mbit/s, {ping} ms ping.",
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_copy.py tests/test_parity.py -q`
Expected: `test_copy.py` PASS. `test_parity.py::test_every_entry_is_actually_rendered_by_the_page[FIELDS]` and `[COLUMNS]` FAIL, because the page does not render `speed_test`, `speed`, `ping` yet. That is expected until Task 6; note it and move on. Every other test PASS.

- [ ] **Step 5: Commit**

```bash
git add src/cpe_band_scan/copy.py tests/test_copy.py
```
```bash
git commit -m "feat: the words for the per-band speed and ping probe and its VPN verdicts"
```

---

### Task 2: Routing past the VPN, and the verdict

**Files:**
- Create: `src/cpe_band_scan/speed.py`
- Create: `tests/test_speed.py`

**Interfaces:**
- Produces: `speed.Route(router_ip, lan_ip, ifindex=None, ifname=None)`, `speed.source_ip(target) -> str`, `speed.scope(sock, ifindex, ifname)`, `speed.lan_route(router_ip) -> Route`, `speed.open_socket(route, kind=SOCK_STREAM) -> socket`, `speed.verdict(default_ip, lan_ip, lan_public, default_public) -> str`, `speed.VERDICTS`, `speed.DURATION`. Task 3 builds on all of these.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_speed.py`:

```python
"""The speed probe, against servers on 127.0.0.1 only. Nothing here reaches the internet."""
import socket

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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_speed.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'cpe_band_scan.speed'`.

- [ ] **Step 3: Write the module's first half**

Create `src/cpe_band_scan/speed.py`:

```python
"""Speed and ping through the router itself, past any VPN on this computer.

A VPN moves two things: the default route, and DNS. The 2026-09-16 check on a Mac with a
fake-IP VPN (the tunnel answers every name with a 198.18.x.x address only it can route)
showed that scoping the socket to the LAN interface is not enough - the name has to be
resolved through the LAN too, or the connect goes to an address nobody on the LAN knows.
So every step here goes through one door, open_socket(): scoped to the interface that
reaches the router, bound to this computer's LAN address, the DNS query included.

Whether the bypass held is proven, not assumed: the public address seen through the LAN
socket is compared with the one seen through the default route (see verdict()).
"""
from __future__ import annotations

import http.client
import random
import socket
import ssl
import statistics
import struct
import sys
import time
from dataclasses import dataclass
from urllib.parse import urlparse

HOST = "speed.cloudflare.com"
PORT = 443
TLS = True                    # tests point HOST/PORT at a plain local server and switch this off
DOWNLOAD = "/__down?bytes={bytes}"
TRACE = "/cdn-cgi/trace"
BYTES = 50_000_000            # the most one band may download; a fast link ends the window early
SECONDS = 5                   # the download window; a slow link ends it with fewer bytes
PINGS = 5
TIMEOUT = 8
DURATION = 12                 # what one band's probe adds to the ETA: pings, TLS, the window
PUBLIC_DNS = "1.1.1.1"
VERDICTS = ("not_needed", "confirmed", "failed", "blocked")
FAILURES = (OSError, http.client.HTTPException, ValueError)


@dataclass
class Route:
    router_ip: str
    lan_ip: str
    ifindex: int | None = None
    ifname: str | None = None


def source_ip(target: str) -> str:
    """The address this computer would send from to reach `target`: a routing lookup with
    no packet sent, which is what a connected UDP socket is."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((target, 53))
        return sock.getsockname()[0]


def scope(sock: socket.socket, ifindex: int, ifname: str) -> None:
    """Pin a socket's routing to one interface. Each OS spells it differently, and each
    raises OSError when it will not (Linux before 5.7 wants CAP_NET_RAW for this)."""
    if sys.platform == "darwin":
        sock.setsockopt(socket.IPPROTO_IP, 25, ifindex)                        # IP_BOUND_IF
    elif sys.platform.startswith("linux"):
        sock.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_BINDTODEVICE", 25), ifname.encode())
    elif sys.platform == "win32":
        sock.setsockopt(socket.IPPROTO_IP, 31, struct.pack("!I", ifindex))     # IP_UNICAST_IF
    else:
        raise OSError(f"no interface scoping on {sys.platform}")


def lan_route(router_ip: str) -> Route:
    """The interface that reaches the router, found by scoping a probe socket to each one
    in turn: the one that answers with the LAN address is it. Without one (no interface can
    be scoped here) the source bind alone has to carry the bypass, and verdict() will say
    whether it did."""
    lan_ip = source_ip(router_ip)
    for index, name in socket.if_nameindex():
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            try:
                scope(sock, index, name)
                sock.connect((router_ip, 53))
            except OSError:
                continue
            if sock.getsockname()[0] == lan_ip:
                return Route(router_ip, lan_ip, index, name)
    return Route(router_ip, lan_ip)


def open_socket(route: Route, kind=socket.SOCK_STREAM) -> socket.socket:
    sock = socket.socket(socket.AF_INET, kind)
    sock.settimeout(TIMEOUT)
    if route.ifindex is not None:
        try:
            scope(sock, route.ifindex, route.ifname)
        except OSError:
            pass                    # verdict(), not this call, decides whether the bypass held
    sock.bind((route.lan_ip, 0))
    return sock


def verdict(default_ip: str, lan_ip: str, lan_public: str | None, default_public: str | None) -> str:
    """What the numbers mean. No tunnel: the default route already leaves by the LAN. A tunnel
    and nothing answering through the LAN: it blocks anything outside itself. A tunnel and two
    different public addresses: the bypass held. The same address both ways: it did not."""
    if default_ip == lan_ip:
        return "not_needed"
    if not lan_public:
        return "blocked"
    return "confirmed" if lan_public != default_public else "failed"
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_speed.py -q`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/cpe_band_scan/speed.py tests/test_speed.py
```
```bash
git commit -m "feat: the speed probe finds the interface that reaches the router and names what a bypass meant"
```

---

### Task 3: DNS over the LAN, ping, download, and the probe object

**Files:**
- Modify: `src/cpe_band_scan/speed.py` (append)
- Modify: `tests/test_speed.py` (append)

**Interfaces:**
- Consumes: everything Task 2 produced.
- Produces: `speed.resolve(host, route, servers=None) -> str`, `speed.ping(route, ip) -> {"latency_ms": int, "jitter_ms": int}`, `speed.download(route, ip) -> {"mbps": float, "bytes": int, "seconds": float}`, `speed.public_ip(route | None) -> str`, and `speed.SpeedProbe(router_url)` with `.start() -> {"bypass": str, "lan_ip": str, "public_ip": str}` and `.measure() -> dict` (the ping and download keys merged, or `{"error": "blocked" | "no_answer"}`). Tasks 4 and 5 rely on `SpeedProbe`'s two methods and their return shapes exactly.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_speed.py`:

```python
import http.server
import struct
import threading
from urllib.parse import parse_qs, urlparse


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
    assert reading["mbps"] > 0 and reading["seconds"] > 0
    assert reading["mbps"] == round(reading["bytes"] * 8 / reading["seconds"] / 1e6, 1)


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
    monkeypatch.setattr(speed, "resolve", lambda host, route, servers=None: "127.0.0.1")
    probe = speed.SpeedProbe("http://127.0.0.1/")
    report = probe.start()
    assert report["bypass"] == "not_needed"          # loopback is its own default route
    assert report["lan_ip"] == "127.0.0.1" and report["public_ip"] == "127.0.0.1"
    reading = probe.measure()
    assert {"latency_ms", "jitter_ms", "mbps", "bytes", "seconds"} <= set(reading)


def test_a_band_whose_probe_fails_reports_no_answer_not_a_crash(speed_host, monkeypatch):
    monkeypatch.setattr(speed, "PUBLIC_DNS", "127.0.0.1")
    monkeypatch.setattr(speed, "resolve", lambda host, route, servers=None: "127.0.0.1")
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_speed.py -q`
Expected: the new tests FAIL with `AttributeError: module 'cpe_band_scan.speed' has no attribute 'resolve'` (and similar for `ping`, `download`, `public_ip`, `SpeedProbe`).

- [ ] **Step 3: Write the second half of the module**

Append to `src/cpe_band_scan/speed.py`:

```python
def _skip_name(data: bytes, at: int) -> int:
    while True:
        length = data[at]
        if length & 0xC0:             # a pointer: two bytes, and the name ends here
            return at + 2
        at += 1
        if not length:
            return at
        at += length


def resolve(host: str, route: Route, servers=None) -> str:
    """One A record for `host`, asked over the LAN socket: the router first (it is the LAN's
    resolver), then a public one. The system resolver is never consulted; a VPN owns it."""
    labels = b"".join(bytes([len(part)]) + part.encode() for part in host.split(".")) + b"\0"
    for server in servers or ((route.router_ip, 53), (PUBLIC_DNS, 53)):
        query = struct.pack("!HHHHHH", random.randrange(65536), 0x0100, 1, 0, 0, 0) + labels + struct.pack("!HH", 1, 1)
        try:
            with open_socket(route, socket.SOCK_DGRAM) as sock:
                sock.sendto(query, server)
                data, _ = sock.recvfrom(512)
        except OSError:
            continue
        if data[:2] != query[:2]:
            continue
        answers = struct.unpack("!H", data[6:8])[0]
        at = _skip_name(data, 12) + 4
        for _ in range(answers):
            at = _skip_name(data, at)
            kind, _, _, length = struct.unpack("!HHIH", data[at:at + 10])
            at += 10
            if kind == 1:
                return socket.inet_ntoa(data[at:at + 4])
            at += length
    raise OSError(f"no address for {host}")


def _wrap(sock: socket.socket) -> socket.socket:
    return ssl.create_default_context().wrap_socket(sock, server_hostname=HOST) if TLS else sock


def connect(route: Route, ip: str) -> socket.socket:
    sock = open_socket(route)
    sock.connect((ip, PORT))
    return _wrap(sock)


def _get(sock: socket.socket, path: str, seconds: float | None = None) -> tuple[bytes, int, float]:
    """GET `path` on an open connection as HOST. Returns (body, bytes received, seconds).
    With `seconds`, reading stops once that long has passed and the body is not kept: a
    speed window, not a download."""
    with sock:
        sock.sendall(f"GET {path} HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n".encode())
        response = http.client.HTTPResponse(sock, method="GET")
        response.begin()
        if response.status != 200:
            raise OSError(f"{HOST}{path} answered {response.status}")
        started = time.perf_counter()
        chunks, count = [], 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            count += len(chunk)
            if seconds is None:
                chunks.append(chunk)
            elif time.perf_counter() - started >= seconds:
                break
        return b"".join(chunks), count, time.perf_counter() - started


def ping(route: Route, ip: str) -> dict:
    """TCP connect time to the probe host in ms: the round trip an app feels, with none of
    the root that ICMP needs."""
    times = []
    for _ in range(PINGS):
        started = time.perf_counter()
        with open_socket(route) as sock:
            sock.connect((ip, PORT))
        times.append((time.perf_counter() - started) * 1000)
    return {"latency_ms": round(statistics.median(times)), "jitter_ms": round(max(times) - min(times))}


def download(route: Route, ip: str) -> dict:
    _, count, seconds = _get(connect(route, ip), DOWNLOAD.format(bytes=BYTES), seconds=SECONDS)
    if not count or seconds <= 0:
        raise OSError("nothing received")
    return {"mbps": round(count * 8 / seconds / 1e6, 1), "bytes": count, "seconds": round(seconds, 2)}


def public_ip(route: Route | None) -> str:
    """The address the internet sees this computer as: through `route` when given, through
    the default path (the VPN, when one is up) when None."""
    if route is None:
        sock = _wrap(socket.create_connection((HOST, PORT), timeout=TIMEOUT))
    else:
        sock = connect(route, resolve(HOST, route))
    body, _, _ = _get(sock, TRACE)
    for line in body.decode(errors="replace").splitlines():
        if line.startswith("ip="):
            return line[3:].strip()
    raise OSError("no ip= line in the trace")


class SpeedProbe:
    """One scan's speed and ping. start() once while the connection is up, to find the way
    past the VPN and prove it; measure() once per band."""

    def __init__(self, router_url: str):
        self.router_ip = urlparse(router_url).hostname or router_url
        self.route: Route | None = None
        self.bypass = "blocked"

    def start(self) -> dict:
        lan_public = ""
        try:
            self.route = lan_route(self.router_ip)
            default_ip = source_ip(PUBLIC_DNS)
            try:
                lan_public = public_ip(self.route)
            except FAILURES:
                lan_public = ""
            default_public = None
            if lan_public and default_ip != self.route.lan_ip:
                try:
                    default_public = public_ip(None)
                except FAILURES:
                    default_public = None
            self.bypass = verdict(default_ip, self.route.lan_ip, lan_public or None, default_public)
        except FAILURES:
            self.bypass = "blocked"
        return {"bypass": self.bypass, "lan_ip": self.route.lan_ip if self.route else "",
                "public_ip": lan_public}

    def measure(self) -> dict:
        if self.bypass == "blocked" or self.route is None:
            return {"error": "blocked"}
        try:
            ip = resolve(HOST, self.route)
            return {**ping(self.route, ip), **download(self.route, ip)}
        except FAILURES:
            return {"error": "no_answer"}


if __name__ == "__main__":            # python -m cpe_band_scan.speed [router-url]: the by-hand check
    import json
    probe = SpeedProbe(sys.argv[1] if len(sys.argv) > 1 else "http://192.168.8.1/")
    print(json.dumps({"start": probe.start(), "measure": probe.measure()}, indent=2))
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_speed.py -q`
Expected: PASS (all tests in the file).

- [ ] **Step 5: Run the by-hand check against the real internet**

Run: `.venv/bin/python -m cpe_band_scan.speed http://192.168.1.1/` (use the router address of the machine you are on; `192.168.8.1` on most Huawei routers).
Expected: JSON with `"bypass"` one of the four verdicts, and, unless blocked, `"mbps"` and `"latency_ms"` numbers. On a machine with a VPN up, `"bypass": "confirmed"` and `"public_ip"` is the mobile line's address, not the VPN's. Paste the output in the commit body's last line as `by-hand: bypass=<verdict> mbps=<n> ping=<n>`.

- [ ] **Step 6: Commit**

```bash
git add src/cpe_band_scan/speed.py tests/test_speed.py
```
```bash
git commit -m "feat: the speed probe resolves, pings and downloads through the LAN and proves the VPN bypass"
```

---

### Task 4: The scan carries the probe

**Files:**
- Modify: `src/cpe_band_scan/scanner.py` (`_scan_side`, `scan`)
- Modify: `tests/fakes.py` (add `FakeProbe`)
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `speed.DURATION`; an object with `.start() -> dict` and `.measure() -> dict` (Task 3's `SpeedProbe` or the fake).
- Produces: `scanner.scan(router, device, sides, bands, cancelled, sleep, probe=None)`. With a probe: `run["speed"]` is `probe.start()`'s dict, the `run_start` event carries `"speed"` too, every `set_result` result and `results[name]` carries `"speed"` (a reading or `{"error": ...}`), and every `eta_s` counts `PER_SET + speed.DURATION` per set. Without: none of those keys exist. `tests.fakes.FakeProbe(router_url="", bypass="confirmed", readings=None)`.

- [ ] **Step 1: Write the fake**

Append to `tests/fakes.py`:

```python
class FakeProbe:
    """Stands in for speed.SpeedProbe: no sockets, a fixed verdict, one reading per band."""

    READING = {"latency_ms": 80, "jitter_ms": 10, "mbps": 25.0, "bytes": 15_000_000, "seconds": 5.0}

    def __init__(self, router_url="", bypass="confirmed", readings=None):
        self.router_url = router_url
        self.bypass = bypass
        self.readings = list(readings or [])
        self.started = 0
        self.measured = 0

    def start(self):
        self.started += 1
        return {"bypass": self.bypass, "lan_ip": "192.168.8.2", "public_ip": "5.1.1.1"}

    def measure(self):
        self.measured += 1
        return self.readings.pop(0) if self.readings else dict(self.READING)
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_scanner.py` (the file already imports `scanner`, `Device`, `Router`, `FakeSession`, `Seq`, `factory` and defines `signal`, `build`, `run_scan`; add `FakeProbe` to the `from tests.fakes import ...` line and `from cpe_band_scan import speed` at the top):

```python
def test_with_a_probe_every_measured_set_carries_speed_and_the_run_carries_the_verdict():
    router, _ = build([signal(8)] * 200)
    probe = FakeProbe(bypass="confirmed")
    events = run_scan(router=router, device=DEVICE, sides=("lte",), probe=probe)
    results = [event for event in events if event["type"] == "set_result"]
    assert results and all(event["result"]["speed"] == FakeProbe.READING for event in results)
    run = events[-1]["run"]
    assert run["speed"]["bypass"] == "confirmed"
    assert run["sides"]["lte"]["results"]["auto"]["speed"] == FakeProbe.READING
    assert probe.started == 1 and probe.measured == len(results)


def test_the_probe_starts_before_the_first_lock_is_touched():
    """start() proves the bypass over the live connection; after the first lock change the
    link is down for half a minute and nothing could be proven."""
    router, session = build([signal(8)] * 200, lock={
        "lte_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "7"}]}, "all_bands": "7"},
        "nr_info": {"lock_mode": "0"}})
    order = []
    probe = FakeProbe()
    probe.start = lambda: order.append("start") or {"bypass": "not_needed", "lan_ip": "", "public_ip": ""}
    original_post = session.post_set
    session.post_set = lambda endpoint, data: order.append("lock") or original_post(endpoint, data)
    run_scan(router=router, device=DEVICE, sides=("lte",), probe=probe)
    assert order[0] == "start"


def test_run_start_carries_the_verdict_so_the_page_can_say_it_first():
    router, _ = build([signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",), probe=FakeProbe(bypass="failed"))
    start = next(event for event in events if event["type"] == "run_start")
    assert start["speed"]["bypass"] == "failed"


def test_the_eta_grows_by_the_probe_duration_per_set_only_when_a_probe_is_on():
    router, _ = build([signal(8)] * 200, bands="1,7")
    with_probe = run_scan(router=router, device=DEVICE, sides=("lte",), probe=FakeProbe())
    router, _ = build([signal(8)] * 200, bands="1,7")
    without = run_scan(router=router, device=DEVICE, sides=("lte",))
    plan_with = next(e for e in with_probe if e["type"] == "run_start")["plan"]["lte"]
    plan_without = next(e for e in without if e["type"] == "run_start")["plan"]["lte"]
    assert plan_with["eta_s"] == plan_without["eta_s"] + plan_with["total"] * speed.DURATION
    side_with = next(e for e in with_probe if e["type"] == "side_start")["eta_s"]
    side_without = next(e for e in without if e["type"] == "side_start")["eta_s"]
    assert side_with == side_without + plan_with["total"] * speed.DURATION


def test_without_a_probe_nothing_about_speed_appears_anywhere():
    router, _ = build([signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    run = events[-1]["run"]
    assert "speed" not in run
    assert "speed" not in next(e for e in events if e["type"] == "run_start")
    assert all("speed" not in row for row in run["sides"]["lte"]["results"].values())


def test_a_probe_reading_never_touches_the_ranking():
    """Spec R15. Two bands with identical radio numbers and wildly different speeds must
    rank exactly as they would without a probe."""
    fast_then_slow = [{"latency_ms": 30, "jitter_ms": 2, "mbps": 200.0, "bytes": 1, "seconds": 1.0},
                      {"latency_ms": 900, "jitter_ms": 50, "mbps": 0.2, "bytes": 1, "seconds": 1.0},
                      dict(FakeProbe.READING)]
    router, _ = build([signal(8)] * 200, bands="1,7")
    with_probe = run_scan(router=router, device=DEVICE, sides=("lte",), probe=FakeProbe(readings=fast_then_slow))
    router, _ = build([signal(8)] * 200, bands="1,7")
    without = run_scan(router=router, device=DEVICE, sides=("lte",))
    assert with_probe[-1]["run"]["sides"]["lte"]["order"] == without[-1]["run"]["sides"]["lte"]["order"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_scanner.py -q -k "probe or speed"`
Expected: FAIL with `TypeError: scan() got an unexpected keyword argument 'probe'`.

- [ ] **Step 4: Thread the probe through the scanner**

In `src/cpe_band_scan/scanner.py`:

Change the import line `from . import lockfreq, metrics` to `from . import lockfreq, metrics, speed`.

Change the signature of `_scan_side` from `def _scan_side(router, side, sets, expect_5g, cancelled, sleep):` to:

```python
def _scan_side(router, side, sets, expect_5g, cancelled, sleep, probe=None, per_set=PER_SET):
```

Inside it, replace both `PER_SET` uses (`"eta_s": total * PER_SET` in the `side_start` event and `"eta_s": (total - index + 1) * PER_SET` in the `set_start` event) with `per_set`.

Right after `measurement = metrics.measure(router, sleep=sleep)` and before `measurement["grade"] = ...`, add:

```python
            if probe is not None:
                measurement["speed"] = probe.measure()
```

Change the signature of `scan` to:

```python
def scan(router: Router, device, sides=("lte", "nr"), bands=None, cancelled=None, sleep=time.sleep, probe=None):
```

Replace its first lines up to and including the `run = {...}` literal and the `plan = ...` / `yield {"type": "run_start", ...}` block with:

```python
    cancelled = cancelled or (lambda: False)
    original = lockfreq.read_lock(router)
    report = probe.start() if probe is not None else None   # over the live link, before any lock change
    per_set = PER_SET + (speed.DURATION if probe is not None else 0)
    if original["lte"][0] or original["nr"][0]:
        lockfreq.lock(router)          # a lock in place hides which bands are really on air,
        sleep(SETTLE)                  # including whether 5G is available here at all
    baseline = metrics.sample(router)
    expect_5g = baseline["has5g"]
    run = {"kind": "scan", "started": _now(), "finished": "", "router_url": router.url,
           "device": device.as_dict(), "expect_5g": expect_5g, "baseline": baseline,
           "sides": {}, "applied": {"lte": [], "lte_scell": [], "nr": [], "nr_scell": []}}
    if report is not None:
        run["speed"] = report
    plan = {side: _sets_for(router, side, bands) for side in sides}
    start = {"type": "run_start", "sides": list(sides), "expect_5g": expect_5g, "baseline": baseline,
             "plan": {side: {"total": len(sets), "eta_s": len(sets) * per_set}
                      for side, sets in plan.items()}}
    if report is not None:
        start["speed"] = report
    yield start
```

And change the `_scan_side(...)` call inside the `for side in sides:` loop to:

```python
            for event in _scan_side(router, side, sets, expect_5g, cancelled, sleep, probe, per_set):
```

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: everything PASS except the two `test_parity.py::test_every_entry_is_actually_rendered_by_the_page` cases left over from Task 1 (fixed in Task 6).

- [ ] **Step 6: Commit**

```bash
git add src/cpe_band_scan/scanner.py tests/fakes.py tests/test_scanner.py
```
```bash
git commit -m "feat: a scan can carry a speed probe: verdict on the run, a reading on every band, longer ETAs"
```

---

### Task 5: Server, terminal and demo

**Files:**
- Modify: `src/cpe_band_scan/server.py` (module constants, `/api/scan`)
- Modify: `src/cpe_band_scan/cli.py` (`parse`, `render`, `results_table`, new `speed_note`, `main`)
- Modify: `tools/demo_server.py`
- Test: `tests/test_server_jobs.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `scanner.scan(..., probe=)`, `speed.SpeedProbe`, `FakeProbe`, the copy keys from Task 1.
- Produces: `server.PROBE` (module attribute, default `speed.SpeedProbe`, called as `PROBE(router.url)`); `/api/scan` body key `speed` (bool, default `true`). CLI `scan --no-speed` (`args.speed` is `False`). `cli.BASE_KEYS`, `cli.SPEED_KEYS = ("speed", "ping")`, `cli.SPEED_AT = 4`, `cli.column_keys(run) -> list[str]`, `cli.speed_note(run) -> str` (`""` when the run has no speed). Task 6 mirrors `SPEED_KEYS` and `SPEED_AT` in the page.

- [ ] **Step 1: Write the failing server tests**

Append to `tests/test_server_jobs.py` (add `FakeProbe` to its `from tests.fakes import ...` line):

```python
def test_a_scan_probes_speed_by_default_and_the_results_carry_it(live, monkeypatch):
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)
    made = []
    monkeypatch.setattr(server, "PROBE", lambda url: made.append(url) or FakeProbe(url))
    session, port = live
    connect(port, session)
    call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["7"]}, token=session.token)
    events = drain(port, session)
    run = next(event for event in events if event["type"] == "done")["run"]
    assert made == ["http://192.168.8.1/"], "the probe is built for the connected router"
    assert run["speed"]["bypass"] == "confirmed"
    assert run["sides"]["lte"]["results"]["B7"]["speed"]["mbps"] == FakeProbe.READING["mbps"]


def test_unticking_the_speed_test_builds_no_probe(live, monkeypatch):
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)
    monkeypatch.setattr(server, "PROBE", lambda url: pytest.fail("a probe was built with speed off"))
    session, port = live
    connect(port, session)
    call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["7"], "speed": False}, token=session.token)
    events = drain(port, session)
    run = next(event for event in events if event["type"] == "done")["run"]
    assert "speed" not in run
```

- [ ] **Step 2: Write the failing CLI tests**

Append to `tests/test_cli.py`:

```python
def test_scan_has_a_no_speed_switch_and_speed_is_on_by_default():
    assert cli.parse(["scan"]).speed is True
    assert cli.parse(["scan", "--no-speed"]).speed is False
    assert cli.parse(["scan", "--no-speed", "4g", "7"]).speed is False


def _run_with_speed():
    row = {"grade": "excellent", "floor": 7.0, "sinr": 9.0, "rsrq": -9.0, "rsrp": -80.0,
           "nrsinr": 12.0, "has5g": True, "band": "B7(N78)",
           "speed": {"latency_ms": 85, "jitter_ms": 12, "mbps": 42.5, "bytes": 1, "seconds": 5.0}}
    dead = dict(row, speed={"error": "no_answer"})
    return {"speed": {"bypass": "confirmed", "lan_ip": "192.168.8.2", "public_ip": "5.1.1.1"},
            "sides": {"lte": {"order": ["B7", "B3"], "results": {"B7": row, "B3": dead}}}}


def test_results_table_adds_speed_and_ping_after_the_5g_column_only_when_the_run_has_them():
    plain = {"sides": {"lte": {"order": ["B7"], "results": {"B7": {
        "grade": "excellent", "floor": 7.0, "sinr": 9.0, "rsrq": -9.0, "rsrp": -80.0,
        "nrsinr": 12.0, "has5g": True, "band": "B7(N78)"}}}}}
    assert cli.column_keys(plain) == list(cli.BASE_KEYS)
    keys = cli.column_keys(_run_with_speed())
    assert keys[cli.SPEED_AT:cli.SPEED_AT + 2] == ["speed", "ping"]
    assert keys[:cli.SPEED_AT] == list(cli.BASE_KEYS[:cli.SPEED_AT])
    header, _, first, second = cli.results_table(_run_with_speed()).splitlines()
    assert copy.COLUMNS["speed"]["label"] in header and copy.COLUMNS["ping"]["label"] in header
    cells = [cell.strip() for cell in first.split("|")[1:-1]]
    assert cells[cli.SPEED_AT] == "42.5" and cells[cli.SPEED_AT + 1] == "85"
    dead_cells = [cell.strip() for cell in second.split("|")[1:-1]]
    assert dead_cells[cli.SPEED_AT] == copy.NOTES["probe_no_answer"]


def test_the_speed_note_names_the_verdict_and_is_silent_without_one():
    assert cli.speed_note(_run_with_speed()) == copy.NOTES["probe_confirmed"]
    assert cli.speed_note({"sides": {}}) == ""


def test_render_says_speed_and_ping_when_a_result_has_them_and_not_when_the_probe_failed():
    with_speed = cli.render({"type": "set_result", "name": "B7",
                             "result": {"grade": "excellent", "floor": 7.0,
                                        "speed": {"latency_ms": 85, "jitter_ms": 1, "mbps": 42.5, "bytes": 1, "seconds": 5}}})
    assert "42.5" in with_speed and "85" in with_speed
    failed = cli.render({"type": "set_result", "name": "B7",
                         "result": {"grade": "excellent", "floor": 7.0, "speed": {"error": "no_answer"}}})
    assert "Mbit" not in failed


def test_render_opens_the_scan_with_the_bypass_verdict_when_there_is_one():
    line = cli.render({"type": "run_start", "sides": ["lte"], "expect_5g": True, "baseline": {},
                       "speed": {"bypass": "failed", "lan_ip": "", "public_ip": ""}})
    assert copy.NOTES["probe_failed"] in line
    plain = cli.render({"type": "run_start", "sides": ["lte"], "expect_5g": True, "baseline": {}})
    assert "VPN" not in plain
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_server_jobs.py tests/test_cli.py -q -k "speed or probe"`
Expected: FAIL with `AttributeError: module 'cpe_band_scan.server' has no attribute 'PROBE'` and `AttributeError: 'Namespace' object has no attribute 'speed'`.

- [ ] **Step 4: Server**

In `src/cpe_band_scan/server.py`, change the import `from . import copy, lockfreq, metrics, scanner, store` to `from . import copy, lockfreq, metrics, scanner, speed, store`.

Below the `SLEEP = time.sleep` block add:

```python
PROBE = speed.SpeedProbe   # built per scan for the connected router; the demo swaps in a fake
```

In `do_POST`, replace the `/api/scan` branch's `self.session.start(...)` call with:

```python
                probe = PROBE(router.url) if body.get("speed", True) else None
                self.session.start("scan", lambda cancelled: scanner.scan(
                    router, device, sides=sides, bands=bands, cancelled=cancelled, sleep=SLEEP, probe=probe))
```

- [ ] **Step 5: CLI**

In `src/cpe_band_scan/cli.py`, change the import `from . import copy, lockfreq, metrics, scanner, store` to `from . import copy, lockfreq, metrics, scanner, speed, store`.

In `parse`, after `scan_parser.add_argument("--save", ...)` add:

```python
    scan_parser.add_argument("--no-speed", dest="speed", action="store_false",
                             help="skip the per-band speed and ping probe")
```

In `render`, replace the `run_start` branch with:

```python
    if kind == "run_start":
        line = copy.text("PROGRESS", "run_start", count=len(event.get("sides", [])))
        if event.get("speed"):
            line += " " + copy.text("NOTES", f"probe_{event['speed']['bypass']}")
        return line
```

Replace the `set_result` branch with:

```python
    if kind == "set_result":
        result = event["result"]
        probe = result.get("speed") or {}
        if probe and "error" not in probe:
            return copy.text("PROGRESS", "set_result_probe", name=event["name"],
                             grade=copy.GRADES[result["grade"]], floor=f"{result['floor']:g}",
                             mbps=f"{probe['mbps']:g}", ping=probe["latency_ms"])
        return copy.text("PROGRESS", "set_result", name=event["name"],
                         grade=copy.GRADES[result["grade"]], floor=f"{result['floor']:g}")
```

Replace the whole `results_table` function with:

```python
BASE_KEYS = ("rank", "band", "grade", "five_g", "floor", "sinr", "rsrq", "rsrp", "nr_sinr", "carriers")
SPEED_KEYS = ("speed", "ping")
SPEED_AT = 4            # after the 5G column; app.js mirrors both of these, test_parity checks it


def column_keys(run: dict) -> list[str]:
    keys = list(BASE_KEYS)
    if run.get("speed"):
        keys[SPEED_AT:SPEED_AT] = SPEED_KEYS
    return keys


def _cells(position: int, name: str, row: dict) -> dict:
    probe = row.get("speed") or {}
    answered = bool(probe) and "error" not in probe
    return {"rank": str(position), "band": name, "grade": copy.GRADES[row["grade"]],
            "five_g": "yes" if row["has5g"] else "no",
            "speed": f"{probe['mbps']:g}" if answered else copy.NOTES["probe_no_answer"],
            "ping": str(probe["latency_ms"]) if answered else copy.NOTES["probe_no_answer"],
            "floor": f"{row['floor']:g}", "sinr": f"{row['sinr']:g}", "rsrq": f"{row['rsrq']:g}",
            "rsrp": f"{row['rsrp']:g}", "nr_sinr": f"{row['nrsinr']:g}", "carriers": row["band"]}


def results_table(run: dict) -> str:
    """The same columns the page shows, in the same order, in markdown, best first."""
    keys = column_keys(run)
    header = [copy.COLUMNS[key]["label"] or "-" for key in keys]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(keys)]
    for side, record in run.get("sides", {}).items():
        for position, name in enumerate(record["order"] + [n for n in record["results"]
                                                           if n not in record["order"]], 1):
            cells = _cells(position, name, record["results"][name])
            lines.append("| " + " | ".join(cells[key] for key in keys) + " |")
    return "\n".join(lines)


def speed_note(run: dict) -> str:
    """The sentence that says what the speed and ping columns mean, or nothing."""
    report = run.get("speed")
    return copy.text("NOTES", f"probe_{report['bypass']}") if report else ""
```

In `main`, in the `show` branch, after `print(results_table(run))` add:

```python
        note = speed_note(run)
        if note:
            print(note)
```

In the `scan` branch, replace `for event in scanner.scan(router, device, sides=sides, bands=bands or None):` with:

```python
            probe = speed.SpeedProbe(router.url) if args.speed else None
            for event in scanner.scan(router, device, sides=sides, bands=bands or None, probe=probe):
```

and after `print("\n" + results_table(run))` add:

```python
            note = speed_note(run)
            if note:
                print(note)
```

- [ ] **Step 6: Demo server**

In `tools/demo_server.py`, change `from tests.fakes import FakeSession, factory` to `from tests.fakes import FakeProbe, FakeSession, factory`, and after the `server.SLEEP = ...` line add:

```python
# No internet in the demo: a fixed set of readings, cycled per band, and a proven bypass.
_READINGS = [{"latency_ms": 62, "jitter_ms": 9, "mbps": 48.3, "bytes": 30_000_000, "seconds": 5.0},
             {"latency_ms": 140, "jitter_ms": 40, "mbps": 9.8, "bytes": 6_100_000, "seconds": 5.0},
             {"error": "no_answer"},
             {"latency_ms": 71, "jitter_ms": 5, "mbps": 33.1, "bytes": 20_700_000, "seconds": 5.0}]
server.PROBE = lambda url: FakeProbe(url, bypass="confirmed", readings=_READINGS * 3)
```

- [ ] **Step 7: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS except the two `test_parity.py` FIELDS/COLUMNS cases pending Task 6.

- [ ] **Step 8: Commit**

```bash
git add src/cpe_band_scan/server.py src/cpe_band_scan/cli.py tools/demo_server.py tests/test_server_jobs.py tests/test_cli.py
```
```bash
git commit -m "feat: the page's scan and the terminal's scan probe speed by default, and the table and log show it"
```

---

### Task 6: The page

**Files:**
- Modify: `src/cpe_band_scan/web/app.js` (`state`, new `toggle`, `scanCard`, `describe`, `onScan`, `resultsTable`)
- Test: `tests/test_parity.py`, `tests/test_page_quality.py`

**Interfaces:**
- Consumes: `/api/scan` body `speed`; run and event shapes from Task 4; copy keys from Task 1; `SPEED_KEYS`/`SPEED_AT` values from Task 5.
- Produces: `state.speedTest` (bool, default `true`); `toggle(key, checked, onChange, disabled)`; `SPEED_KEYS = ["speed", "ping"]`, `SPEED_AT = 4`, `columnKeys(run)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parity.py`:

```python
def test_the_page_and_the_terminal_put_the_speed_columns_in_the_same_place():
    """Mirrors need a parity check: the two front ends each insert the same two keys at the
    same index, and both only when the run carries speed."""
    from cpe_band_scan import cli
    keys = re.search(r"const SPEED_KEYS\s*=\s*\[(.*?)\]", APP_JS).group(1)
    page_keys = [key.strip().strip('"') for key in keys.split(",")]
    assert page_keys == list(cli.SPEED_KEYS)
    page_at = int(re.search(r"const SPEED_AT\s*=\s*(\d+)", APP_JS).group(1))
    assert page_at == cli.SPEED_AT
    table = re.search(r"function resultsTable\(run\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert "columnKeys(run)" in table and "run.speed" in table


def test_the_scan_form_offers_the_speed_test_on_by_default_and_sends_the_choice():
    assert re.search(r"speedTest:\s*true", APP_JS), "the speed test is on until unticked"
    card = re.search(r"function scanCard\(\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'toggle("speed_test"' in card
    scan = re.search(r"async function onScan\([^)]*\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert "speed: state.speedTest" in scan


def test_the_verdict_is_said_under_the_table_and_in_the_log():
    table = re.search(r"function resultsTable\(run\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'copy.NOTES["probe_" + run.speed.bypass]' in table
    describe = re.search(r"function describe\(event\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'copy.NOTES["probe_" + event.speed.bypass]' in describe
    assert "words.log_result_probe" in describe
```

Append to `tests/test_page_quality.py`:

```python
def test_the_speed_toggle_is_a_native_checkbox_in_a_choice_row():
    toggle = re.search(r"function toggle\([^)]*\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert 'type: "checkbox"' in toggle and 'class: "choice"' in toggle
    assert 'help("FIELDS", key)' in toggle, "the label carries its hover explanation like every field"


def test_speed_and_ping_cells_go_through_num_or_say_no_answer():
    cells = re.search(r"function speedCells\([^)]*\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert "num(" in cells and "copy.NOTES.probe_no_answer" in cells
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_parity.py tests/test_page_quality.py -q`
Expected: the new tests FAIL (`AttributeError: 'NoneType' object has no attribute 'group'` on the missing `SPEED_KEYS`, `toggle`, `speedCells`), and the two leftover `test_every_entry_is_actually_rendered_by_the_page` cases still FAIL.

- [ ] **Step 3: The state and the toggle helper**

In `src/cpe_band_scan/web/app.js`, in the `state` literal change the line

```js
  scope: "all", testTarget: "current", testPick: { lte: "", nr: "" }, testMinutes: "2",
```

to

```js
  scope: "all", speedTest: true, testTarget: "current", testPick: { lte: "", nr: "" }, testMinutes: "2",
```

After the `choices(...)` function add:

```js
function toggle(key, checked, onChange, disabled) {
  return el("label", { class: "choice" },
    el("input", { type: "checkbox", id: key, disabled, checked: checked ? "" : null,
                  onchange: (event) => onChange(event.target.checked) }),
    help("FIELDS", key));
}
```

- [ ] **Step 4: The scan form and the request**

Replace the `scanCard` function with:

```js
function scanCard() {
  const disabled = state.running || state.busy;
  return el("div", { class: "card span" },
    heading("h2", copy.APP.scan_heading),
    el("p", { class: "note" }, copy.NOTES.before_scan),
    el("div", { class: "form-row" },
      choices("scan_scope", state.scope, (value) => { state.scope = value; }, disabled),
      toggle("speed_test", state.speedTest, (on) => { state.speedTest = on; }, disabled),
      action("scan", () => onScan(SCOPES[state.scope]),
             { class: state.results ? "" : "primary", disabled })));
}
```

In `onScan`, change `await api("POST", "/api/scan", { sides });` to:

```js
    await api("POST", "/api/scan", { sides, speed: state.speedTest });
```

- [ ] **Step 5: The log lines**

In `describe`, add a `run_start` case before `case "set_start":`, and replace the `set_result` case:

```js
    case "run_start":
      return event.speed ? copy.NOTES["probe_" + event.speed.bypass] : null;
    case "set_result": {
      const speed = event.result.speed;
      const answered = speed && !speed.error;
      return coloured(answered ? words.log_result_probe : words.log_result,
                      { name: event.name, floor: event.result.floor, grade: "{grade}",
                        mbps: answered ? speed.mbps : "", ping: answered ? speed.latency_ms : "" },
                      "grade", el("span", { class: `grade-${event.result.grade}` }, copy.GRADES[event.result.grade]));
    }
```

- [ ] **Step 6: The table**

Replace the `COLUMN_KEYS` declaration and the `resultsTable` function with:

```js
const COLUMN_KEYS = ["rank", "band", "grade", "five_g", "floor", "sinr", "rsrq", "rsrp",
                     "nr_sinr", "carriers"];
const SPEED_KEYS = ["speed", "ping"];
const SPEED_AT = 4;            // after the 5G column; cli.py holds the same two values

function columnKeys(run) {
  const keys = COLUMN_KEYS.slice();
  if (run.speed) keys.splice(SPEED_AT, 0, ...SPEED_KEYS);
  return keys;
}

function speedCells(row) {
  const probe = row.speed;
  const answered = probe && !probe.error;
  return SPEED_KEYS.map((key) => el("td", { class: "num" },
    answered ? num(key === "speed" ? probe.mbps : probe.latency_ms) : copy.NOTES.probe_no_answer));
}

function resultsTable(run) {
  if (!run || !run.sides) return el("p", { class: "note" }, copy.NOTES.empty_results);
  const blocks = [];
  for (const [side, record] of Object.entries(run.sides)) {
    const ranked = record.order.concat(
      Object.keys(record.results).filter((name) => !record.order.includes(name)));
    const head = el("tr", {},
      columnKeys(run).map((key) => el("th", { scope: "col" }, help("COLUMNS", key))),
      el("th", { scope: "col" }));
    const rows = ranked.map((name, index) => {
      const row = record.results[name];
      const isBest = index === 0 && record.order.includes(name);
      const used = inUse(side, record, name);
      const cells = [
        el("td", { class: "num" }, record.order.includes(name) ? index + 1 : "—"),
        el("td", { class: "band" }, el("b", {}, name), isBest ? el("span", { class: "badge best" }, copy.NOTES.best) : null),
        el("td", { class: `grade-${row.grade}` }, copy.GRADES[row.grade]),
        el("td", {}, row.has5g ? "yes" : "no"),
        el("td", { class: "num" }, num(row.floor)),
        el("td", { class: "num" }, num(row.sinr)),
        el("td", { class: "num" }, num(row.rsrq)),
        el("td", { class: "num" }, num(row.rsrp)),
        el("td", { class: "num" }, num(row.nrsinr)),
        el("td", { class: "carriers" }, (row.carriers || []).map((carrier) => carrier.band).join(" + ") || row.band),
      ];
      if (run.speed) cells.splice(SPEED_AT, 0, ...speedCells(row));
      return el("tr", { class: [isBest ? "best" : "", used ? "used" : ""].join(" ").trim() },
        cells, applyCell(side, record, name));
    });
    const skipped = Object.keys(record.skipped);
    blocks.push(el("div", { class: "card span" },
      heading("h2", fill(copy.APP.results_side_heading, { side: copy.SIDES[side] })),
      el("div", { class: "table-scroll" }, el("table", {}, el("thead", {}, head), el("tbody", {}, rows))),
      skipped.length
        ? el("p", { class: "note" }, `${skipped.join(", ")}: ` + copy.PROGRESS.no_service.replace("{name}", "").trim())
        : null,
      el("p", { class: "note" }, copy.NOTES.auto_row),
      run.speed ? el("p", { class: "note" }, copy.NOTES["probe_" + run.speed.bypass]) : null));
  }
  return blocks;
}
```

- [ ] **Step 7: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, everything, including the two parity cases pending since Task 1.

- [ ] **Step 8: Look at it**

Run: `.venv/bin/python tools/demo_server.py` and open `http://127.0.0.1:8766/`. Check at 1440px and 375px, light and dark:
- the scan form shows the checkbox ticked, with the hover text, on the same row as the scope radios and the button;
- during the scan the 4G log opens with the "measured straight through the router" sentence and each finished band's line ends with `… Mbit/s, … ms`;
- the results table has Speed and Ping right after the 5G column, the third band's row says "no answer" in both, and the verdict sentence sits under the table;
- untick the checkbox and scan again: no Speed/Ping columns, no verdict sentence, no `Mbit/s` in the log.
Stop the demo server when done (Ctrl-C), and check with `lsof -i :8766` that nothing is left listening.

- [ ] **Step 9: Commit**

```bash
git add src/cpe_band_scan/web/app.js tests/test_parity.py tests/test_page_quality.py
```
```bash
git commit -m "feat: the page offers the speed test as a ticked checkbox and shows speed, ping and the VPN verdict"
```

---

### Task 7: Docs, skill and design ruling

**Files:**
- Modify: `README.md`, `skills/bandscan/SKILL.md`, `skills/bandscan/reference.md`, `docs/design/2026-09-16-page-redesign.md`

**Interfaces:**
- Consumes: the wording from `copy.py` (quote labels exactly: "Measure speed and ping on each band", "Speed", "Ping").

- [ ] **Step 1: README**

In the **Scan** section, after the choices table paragraph that begins "The scan locks each band in turn", add:

```markdown
**Measure speed and ping on each band** is ticked by default. After the radio samples of each band the
app pings the internet five times and downloads for five seconds through the router, from this computer,
and adds two columns to the results. It costs about 10 seconds and up to 50 MB per band, so a full
scan of every band can use up to about 1.4 GB on a fast link; slow links use far less because the
window closes at five seconds. Untick it on a metered plan you are close to using up.
```

In the **Read the results** column table, insert after the `| 5G |` row:

```markdown
| Speed | download in Mbit/s over five seconds, straight through the router. One moment's reading: cell load changes it hour to hour. Shown, never used to rank |
| Ping | time to reach the internet in ms, the middle of five tries. Under 50 feels instant, over 150 you notice |
```

After that table's following paragraph ("When the scan ends, the app locks the best band itself…"), add:

```markdown
Speed and ping never move a band up or down the ranking. The rating is the radio; the two columns are
what that radio delivered at that moment. Under each table one sentence says what they mean: measured
past your VPN, measured through it, measured with no VPN active, or not measured because the VPN blocked
it.
```

Replace the **Using a VPN** section with:

```markdown
### Using a VPN

Keep it on. The signal numbers come from the router itself, so a VPN doesn't change them. Stay on one
server for the whole scan, because switching servers mid-run changes what you feel while the
measurements stay the same.

The speed and ping probe is different: measured through the VPN, every band would look like the VPN
server. So the probe goes around it. Each probe connection is pinned to the network interface that
reaches the router, and the probe host's address is looked up through the router too, because some
VPNs answer every name lookup with an address only the tunnel can route. Before the first band the app
checks that the address the internet sees through the router differs from the one it sees through the
VPN, and tells you which of these you are in:

- no VPN was active: the numbers are your plain connection;
- measured straight through the router, past your VPN: the numbers are the band's own;
- the VPN couldn't be bypassed: the numbers include it, so compare rows with each other only;
- the VPN blocks everything outside its tunnel: speed and ping weren't measured. Allow local network
  access in the VPN's settings, or scan with the speed test unticked.

If the app can't reach the router at all while the VPN is up, turn on your VPN's local network access
setting.
```

In **From the terminal instead**, after the `cpe-band-scan scan --save "Office"` line add:

```bash
cpe-band-scan scan --no-speed        # skip the per-band speed and ping probe
```

In **Known limits**, add a bullet:

```markdown
- **The speed test costs data and reads one moment.** Up to 50 MB per band, so a full scan of every band can use
  up to about 1.4 GB on a fast link; slow links use far less because the window closes at five
  seconds. Cell load changes hour to hour. It is shown next to the rating and never decides it.
  Untick **Measure speed and ping on each band** on a plan you are close to using up.
```

- [ ] **Step 2: Skill**

In `skills/bandscan/SKILL.md`:

In the commands table, add a row after `cpe-band-scan scan 7 40`:

```markdown
| `cpe-band-scan scan --no-speed` | the same scan without the per-band speed and ping probe (on by default: five TCP pings and a 5 s download through the router after each band's radio samples, up to 50 MB per band) | saves ~10 s per band | yes |
```

Replace step 1 with:

```markdown
1. **VPN stays on.** Many users run a VPN at all times and it is part of their real connection quality. Never ask them to disconnect it. The radio numbers come from the router's LAN API, so the VPN cannot touch them. The speed and ping probe would be poisoned by a VPN, so the app routes around it itself: probe sockets are pinned to the interface that reaches the router and the probe host is resolved through the router, not the system resolver (some VPNs hand out fake 198.18.x.x addresses for every name). The scan's first log line says which case applies: no VPN, bypassed and proven, not bypassed (numbers include the VPN; compare rows with each other only), or blocked (the VPN allows nothing outside its tunnel; ask them to allow local network access in the VPN, or run `scan --no-speed`). Each lock change drops the link for ~30 s and the VPN will reconnect each time; that is expected. If the router API is unreachable with the VPN up, ask them to enable the VPN's "allow LAN / local network access" option, not to disconnect.
```

In step 8, change "The app prints a markdown table per side (band, rating, lowest/typical/peak SINR, RSRQ, RSRP, 5G kept, carriers)" to "The app prints a markdown table per side (band, rating, 5G kept, speed in Mbit/s and ping in ms when the probe ran, lowest/typical SINR, RSRQ, RSRP, 5G quality, carriers) and, under it, the one-sentence VPN verdict for the speed columns" and add this sentence at the end of the step: "Speed and ping are shown, never ranked: cell load changes hour to hour. Read them as 'what this band delivered at that moment'; when two bands tie on rating, the faster one is the one to `test` for longer, and say so."

In **Common mistakes**, add a row:

```markdown
| Ranking or recommending by the Speed column alone | It is one five-second reading under that hour's cell load. Rating first, then floor; use speed to break a tie between equally rated bands, and confirm with `test`. |
```

- [ ] **Step 3: Reference**

In `skills/bandscan/reference.md`, under **Reading the numbers**, add two bullets:

```markdown
- Speed (Mbit/s) and Ping (ms) are the path from this computer through the router to `speed.cloudflare.com` at that moment: width, cell load and core path in one number. They change with the hour; the radio numbers do not, which is why they never rank.
- The probe bypasses a VPN by scoping sockets to the LAN interface (`IP_BOUND_IF` / `SO_BINDTODEVICE` / `IP_UNICAST_IF`) and resolving the host through the router. Fake-IP VPNs (198.18.0.0/15 answers) make the DNS step mandatory: a scoped connect to a system-resolved name just times out (seen 2026-09-16).
```

- [ ] **Step 4: Design ruling**

Append to `docs/design/2026-09-16-page-redesign.md`:

```markdown
## Ruling 2026-09-16, later: speed is shown, never ranked

The scan form gains one native checkbox, **Measure speed and ping on each band**, ticked by default,
in the same row as the scope radios; its hover text states the data cost. The results table gains
**Speed** and **Ping** right after the 5G column, only when the run carries them, and one sentence under
the table says how the VPN was handled (`copy.NOTES.probe_*`). The two columns never enter the
ranking: cell load moves hour to hour, and a ranking that flips between scans is worse than one that
ignores speed. The page and the terminal share the column position through `SPEED_KEYS`/`SPEED_AT`,
guarded by `test_the_page_and_the_terminal_put_the_speed_columns_in_the_same_place`.

Follow-up: once saved runs show how stable per-band speed is across hours, decide whether it may break
ties inside a rating. Not before.
```

- [ ] **Step 5: Run the suite one last time**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md skills/bandscan/SKILL.md skills/bandscan/reference.md docs/design/2026-09-16-page-redesign.md
```
```bash
git commit -m "docs: README, skill and design doc cover the speed probe, its VPN bypass and its data cost"
```

---

## Self-review

**Spec coverage.** R13 (opt-in default on, checkbox, `--no-speed`): Tasks 5 and 6. R14 (bypass with DNS, verified and stated): Tasks 2, 3, plus the sentences in Task 1 and their rendering in Tasks 5 and 6. R15 (same place in both front ends, never ranked): Task 5 `column_keys`, Task 6 `columnKeys`, parity test in Task 6, ranking test in Task 4. R16 (data cost by the checkbox): Task 1 test on `FIELDS["speed_test"]["help"]`. The four verdicts each have a sentence (Task 1) and the scanner carries the verdict on the run and on `run_start` (Task 4). The skill rule "never ask to disconnect a VPN" holds: `probe_blocked` offers the VPN's local-network setting or unticking; `test_no_string_asks_the_user_to_turn_off_a_vpn` guards it.

**Placeholders.** None; every step has its code.

**Type consistency.** `probe.start()` returns `{"bypass", "lan_ip", "public_ip"}` in Task 3, `FakeProbe.start()` in Task 4, and the page reads `run.speed.bypass` / `event.speed.bypass` in Task 6. `probe.measure()` returns ping+download keys or `{"error"}`; `_cells` (Task 5) and `speedCells` (Task 6) both test `"error" not in probe` / `!probe.error`. `SPEED_KEYS`/`SPEED_AT` are `("speed", "ping")`/`4` in both cli.py and app.js and asserted equal by the parity test. The `/api/scan` body key is `speed` in server (Task 5) and in `onScan` (Task 6). `scan(..., probe=)` is the keyword in scanner (Task 4), server and cli (Task 5).

**Task interaction.** Task 4's ETA change touches `_scan_side` events that the page's progress bar reads (`eta_s`); the page only formats minutes, so no page change is needed. Task 5's CLI `render` for `run_start` appends the verdict to an existing sentence; `test_render_ignores_events_with_nothing_to_say` still holds because `run_start` still returns a non-None line. The demo (Task 5) swaps `server.PROBE` before `serve()`, and `/api/scan` reads `PROBE` at request time, so the swap takes effect. Task 6's `describe("run_start")` returns null without speed, which keeps the existing log behaviour for probe-less scans. Task 1 leaves two parity tests red until Task 6; each intermediate task says so and the final task closes them.
