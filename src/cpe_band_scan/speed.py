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
DURATION = 12                 # the most one band's probe may take: measure() stops at this wall-clock bound
TRIES = 3                     # start() attempts before "blocked" sticks for the whole scan
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


def open_socket(route: Route, kind=socket.SOCK_STREAM, deadline: float | None = None) -> socket.socket:
    sock = socket.socket(socket.AF_INET, kind)
    left = TIMEOUT if deadline is None else deadline - time.monotonic()
    if left <= 0:
        sock.close()
        raise OSError("out of time")
    sock.settimeout(min(TIMEOUT, left))
    if route.ifindex is not None:
        try:
            scope(sock, route.ifindex, route.ifname)
        except OSError:         # boundary: verdict(), not this call, decides whether the bypass held
            pass
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


def _skip_name(data: bytes, at: int) -> int:
    while True:
        length = data[at]
        if length & 0xC0:             # a pointer: two bytes, and the name ends here
            return at + 2
        at += 1
        if not length:
            return at
        at += length


def resolve(host: str, route: Route, servers=None, deadline: float | None = None) -> str:
    """One A record for `host`, asked over the LAN socket: the router first (it is the LAN's
    resolver), then a public one. The system resolver is never consulted; a VPN owns it."""
    try:
        socket.inet_aton(host)
        return host                   # already an address: nothing to ask
    except OSError:               # boundary: not an address, so ask the resolvers below
        pass
    labels = b"".join(bytes([len(part)]) + part.encode() for part in host.split(".")) + b"\0"
    for server in servers or ((route.router_ip, 53), (PUBLIC_DNS, 53)):
        query = struct.pack("!HHHHHH", random.randrange(65536), 0x0100, 1, 0, 0, 0) + labels + struct.pack("!HH", 1, 1)
        try:
            with open_socket(route, socket.SOCK_DGRAM, deadline) as sock:
                sock.sendto(query, server)
                data, _ = sock.recvfrom(512)
        except OSError:
            continue
        try:
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
        except (struct.error, IndexError):
            continue
    raise OSError(f"no address for {host}")


def _wrap(sock: socket.socket) -> socket.socket:
    return ssl.create_default_context().wrap_socket(sock, server_hostname=HOST) if TLS else sock


def connect(route: Route, ip: str, deadline: float | None = None) -> socket.socket:
    sock = open_socket(route, deadline=deadline)
    try:
        sock.connect((ip, PORT))
        return _wrap(sock)
    except BaseException:
        sock.close()
        raise


def _get(sock: socket.socket, path: str, seconds: float | None = None,
         deadline: float | None = None) -> tuple[bytes, int, float]:
    """GET `path` on an open connection as HOST. Returns (body, bytes received, seconds).
    With `seconds`, reading stops once that long has passed and the body is not kept: a
    speed window, not a download. A `deadline` only shortens the window."""
    with sock:
        sock.sendall(f"GET {path} HTTP/1.1\r\nHost: {HOST}\r\nConnection: close\r\n\r\n".encode())
        response = http.client.HTTPResponse(sock, method="GET")
        response.begin()
        if response.status != 200:
            raise OSError(f"{HOST}{path} answered {response.status}")
        keep = seconds is None
        window = seconds
        if deadline is not None:
            left = deadline - time.monotonic()
            window = left if window is None else min(window, left)
        started = time.perf_counter()
        chunks, count = [], 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            count += len(chunk)
            if keep:
                chunks.append(chunk)
            if window is not None and time.perf_counter() - started >= window:
                break
        return b"".join(chunks), count, time.perf_counter() - started


def ping(route: Route, ip: str, deadline: float | None = None) -> dict:
    """TCP connect time to the probe host in ms: the round trip an app feels, with none of
    the root that ICMP needs."""
    times = []
    for _ in range(PINGS):
        started = time.perf_counter()
        with open_socket(route, deadline=deadline) as sock:
            sock.connect((ip, PORT))
            times.append((time.perf_counter() - started) * 1000)
    return {"latency_ms": round(statistics.median(times)), "jitter_ms": round(max(times) - min(times))}


def download(route: Route, ip: str, deadline: float | None = None) -> dict:
    _, count, seconds = _get(connect(route, ip, deadline), DOWNLOAD.format(bytes=BYTES),
                             seconds=SECONDS, deadline=deadline)
    if not count:
        raise OSError("nothing received")
    return {"mbps": round(count * 8 / max(seconds, 1e-9) / 1e6, 1), "bytes": count, "seconds": round(seconds, 3)}


def public_ip(route: Route | None, deadline: float | None = None) -> str:
    """The address the internet sees this computer as: through `route` when given, through
    the default path (the VPN, when one is up) when None."""
    if route is None:
        sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
        try:
            sock = _wrap(sock)
        except BaseException:
            sock.close()
            raise
    else:
        sock = connect(route, resolve(HOST, route, deadline=deadline), deadline)
    body, _, _ = _get(sock, TRACE, deadline=deadline)
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
        """The verdict is sticky for the whole scan, so one hiccup at the moment the scan
        starts (a VPN reconnecting, a slow trace) must not silence every band: a "blocked"
        attempt is retried TRIES times, each bounded by DURATION."""
        for _ in range(TRIES):
            report = self._attempt()
            if report["bypass"] != "blocked":
                break
        return report

    def _attempt(self) -> dict:
        lan_public = ""
        deadline = time.monotonic() + DURATION
        try:
            self.route = lan_route(self.router_ip)
            default_ip = source_ip(PUBLIC_DNS)
            try:
                lan_public = public_ip(self.route, deadline)
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
        deadline = time.monotonic() + DURATION
        try:
            ip = resolve(HOST, self.route, deadline=deadline)
            return {**ping(self.route, ip, deadline), **download(self.route, ip, deadline)}
        except FAILURES:
            return {"error": "no_answer"}


if __name__ == "__main__":            # python -m cpe_band_scan.speed [router-url]: the by-hand check
    import json
    probe = SpeedProbe(sys.argv[1] if len(sys.argv) > 1 else "http://192.168.8.1/")
    print(json.dumps({"start": probe.start(), "measure": probe.measure()}, indent=2))
