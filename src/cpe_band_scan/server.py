"""The local web front end.

It binds 127.0.0.1 and every /api call must carry the token that was baked into the page.
A hostile site in another tab can fire a request at localhost, but it can't read our page to
learn the token, and the custom header forces a preflight it can't satisfy. The Host check
blocks DNS rebinding.
"""
from __future__ import annotations

import hmac
import json
import secrets
import socketserver
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import copy, lockfreq, metrics, scanner, store
from .device import probe
from .router import Router, RouterError

WEB = Path(__file__).parent / "web"
DEFAULT_URL = "http://192.168.8.1/"
ALLOWED_HOSTS = ("127.0.0.1", "localhost")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8"}
SLEEP = time.sleep    # real between-band and between-sample waits; read at call time so
                      # tests can swap in a no-op instead of waiting out real settle/gap delays
SETTLE_GRACE = scanner.PER_SET + 5   # worst case: cancel lands just as a band's settle-and-
                                     # measure window starts; give the job's finally block
                                     # that long to clear the lock and restore automatic mode


def _default_router(url, password, username="admin"):
    return Router(url, password, username=username)


class Session:
    """One router and one job at a time. Held in memory; nothing here reaches the disk."""

    def __init__(self, router_factory=_default_router):
        self.token = secrets.token_urlsafe(24)
        self._router_factory = router_factory
        self.lock = threading.Lock()          # public: the handler is a legitimate second user
        self.router = None
        self.device = None
        self.events = []
        self.kind = ""
        self.thread = None
        self.cancelled = False

    def connect(self, url, password, username="admin"):
        router = self._router_factory(url or DEFAULT_URL, password, username)
        self.device = probe(router)          # raises RouterError carrying the reason
        self.router = router
        return self.device

    def require_router(self) -> Router:
        if self.router is None:
            raise RouterError("not_connected")
        return self.router

    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def require_idle(self) -> None:
        if self.running():
            raise RouterError("busy")

    def start(self, kind: str, make_events):
        """Run an event generator on a worker thread. One job at a time, always."""
        with self.lock:
            self.require_idle()
            self.events, self.kind, self.cancelled = [], kind, False
            self.thread = threading.Thread(target=self._drive, args=(make_events,), daemon=True)
            self.thread.start()

    def cancel(self) -> None:
        self.cancelled = True

    def _drive(self, make_events):
        try:
            for event in make_events(lambda: self.cancelled):
                self.events.append(event)
        except RouterError as error:
            self.events.append({"type": "error", "code": error.code, "detail": error.detail,
                                "message": copy.text("ERRORS", error.code, detail=error.detail,
                                                     url=getattr(self.router, "url", ""))})
        except Exception as error:                      # a crash must still reach the page
            self.events.append({"type": "error", "code": "crash", "detail": repr(error),
                                "message": copy.text("ERRORS", "crash", detail=repr(error))})
        finally:
            self.events.append({"type": "finished", "kind": self.kind})


class Handler(BaseHTTPRequestHandler):
    session: Session = None
    server_version = "cpe-band-scan"

    def log_message(self, *args):
        pass                                   # the terminal is for progress, not request logs

    def _send(self, status, body: bytes, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200):
        self._send(status, json.dumps(payload, default=str).encode(), "application/json")

    def _fail(self, code, status=409, **fields):
        self._json({"error": code, "message": copy.text("ERRORS", code, **fields)}, status)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return {}

    def _host_allowed(self) -> bool:
        if (self.headers.get("Host") or "").split(":")[0] in ALLOWED_HOSTS:
            return True
        self._json({"error": "forbidden"}, 403)
        return False

    def _allowed(self) -> bool:
        if not self._host_allowed():
            return False
        if not hmac.compare_digest(self.headers.get("X-CPE-Band-Scan-Token") or "",
                                   self.session.token):
            self._json({"error": "forbidden"}, 403)
            return False
        return True

    def _page(self):
        saved = store.settings()
        bootstrap = json.dumps({"token": self.session.token, "copy": copy.bundle(),
                                "defaults": {"url": saved.get("router_url", DEFAULT_URL),
                                             "remembered": bool(saved.get("password"))}})
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self._send(200, html.replace("/*BOOTSTRAP*/", f"window.CPE_BAND_SCAN = {bootstrap};").encode(),
                   TYPES[".html"])

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/app.js", "/style.css"):
            if not self._host_allowed():
                return
            if path in ("/", "/index.html"):
                return self._page()
            asset = WEB / path.lstrip("/")
            return self._send(200, asset.read_bytes(), TYPES[asset.suffix])
        if not path.startswith("/api/") or not self._allowed():
            return
        try:
            if path == "/api/status":
                router = self.session.require_router()
                return self._json({"device": self.session.device.as_dict(),
                                   "lock": lockfreq.read_lock(router),
                                   "signal": metrics.sample(router),
                                   "visible": metrics.visible_bands(router),
                                   "running": self.session.running(),
                                   "suggested_name": store.default_name(self.session.device.carrier)})
            if path == "/api/events":
                since = max(0, int(parse_qs(urlparse(self.path).query).get("since", ["0"])[0]))
                events = self.session.events[since:]
                return self._json({"since": since + len(events), "events": events,
                                   "running": self.session.running(), "kind": self.session.kind})
            if path == "/api/runs":
                return self._json({"runs": store.list_runs()})
            if path == "/api/profiles":
                return self._json({"profiles": store.list_profiles()})
            if path.startswith("/api/runs/"):
                try:
                    return self._json({"run": store.load(unquote(path.split("/")[3]))})
                except KeyError:
                    return self._json({"error": "not_found"}, 404)
        except RouterError as error:
            return self._fail(error.code, detail=error.detail,
                              url=getattr(self.session.router, "url", ""))
        except ValueError as error:
            return self._fail("bad_request", 400, detail=str(error))
        self._json({"error": "not_found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._json({"error": "not_found"}, 404)
        if not self._allowed():
            return
        body = self._body()
        try:
            if path == "/api/connect":
                with self.session.lock:
                    self.session.require_idle()
                    password = body.get("password") or store.remembered_password()
                    device = self.session.connect(body.get("url") or DEFAULT_URL, password,
                                                  body.get("username") or "admin")
                    store.save_settings(router_url=self.session.router.url,
                                        username=body.get("username") or "admin")
                    if "remember" in body:                  # the page decides; absent means keep as is
                        store.remember_password(password if body["remember"] else None)
                return self._json({"device": device.as_dict(),
                                   "suggested_name": store.default_name(device.carrier)})
            if path == "/api/forget":
                store.remember_password(None)
                return self._json({"remembered": False})
            if path == "/api/profiles":
                router = self.session.require_router()
                profile = store.save_profile(body.get("name") or "", self.session.device.carrier,
                                             lockfreq.read_lock(router))
                return self._json({"profile": profile})
            if path.startswith("/api/profiles/") and path.endswith("/rename"):
                try:
                    return self._json({"profile": store.rename_profile(unquote(path.split("/")[3]),
                                                                       body.get("name") or "")})
                except KeyError:
                    return self._json({"error": "not_found"}, 404)
            if path.startswith("/api/profiles/") and path.endswith("/apply"):
                try:
                    profile = store.load_profile(unquote(path.split("/")[3]))
                except KeyError:
                    return self._json({"error": "not_found"}, 404)
                lock = profile["lock"]
                with self.session.lock:
                    self.session.require_idle()
                    lockfreq.lock(self.session.require_router(), lte=lock["lte"][0], lte_scell=lock["lte"][1],
                                  nr=lock["nr"][0], nr_scell=lock["nr"][1])
                return self._json({"applied": True})
            if path == "/api/scan":
                router, device = self.session.require_router(), self.session.device
                sides = tuple(body.get("sides") or ("lte", "nr"))
                if any(side not in scanner.SIDES for side in sides):
                    raise ValueError(f"sides {sides!r}")
                bands = lockfreq.bands_of(body.get("bands") or []) or None
                self.session.start("scan", lambda cancelled: scanner.scan(
                    router, device, sides=sides, bands=bands, cancelled=cancelled, sleep=SLEEP))
                return self._json({"started": True})
            if path == "/api/test":
                router = self.session.require_router()
                seconds = int(body["seconds"]) if "seconds" in body else 120
                gap = int(body["gap"]) if "gap" in body else 10
                if not 0 < gap <= seconds:
                    raise ValueError(f"seconds={seconds} gap={gap}")
                lte = lockfreq.bands_of(body.get("lte") or [])
                nr = lockfreq.bands_of(body.get("nr") or [])
                scell = lockfreq.bands_of(body.get("scell") or [])
                self.session.start("test", lambda cancelled: scanner.trace(
                    router, seconds=seconds, gap=gap, cancelled=cancelled, sleep=SLEEP,
                    lte=lte, nr=nr, lte_scell=scell))
                return self._json({"started": True})
            if path == "/api/cancel":
                self.session.cancel()
                return self._json({"cancelling": True})
            if path == "/api/apply":
                with self.session.lock:
                    self.session.require_idle()
                    router = self.session.require_router()
                    current = lockfreq.read_lock(router)     # an absent side keeps the lock it has
                    lte = body["lte"] if "lte" in body else current["lte"][0]
                    scell = body["scell"] if "scell" in body else current["lte"][1]
                    nr = body["nr"] if "nr" in body else current["nr"][0]
                    lockfreq.lock(router, lte=lte, lte_scell=scell, nr=nr)
                return self._json({"applied": True})
            if path == "/api/clear":
                with self.session.lock:
                    self.session.require_idle()
                    lockfreq.lock(self.session.require_router())
                return self._json({"applied": True})
            if path == "/api/runs":
                return self._json({"run": store.save(body.get("run") or {}, body.get("name"))})
            if path.startswith("/api/runs/") and path.endswith("/rename"):
                try:
                    return self._json({"run": store.rename(unquote(path.split("/")[3]),
                                                           body.get("name") or "")})
                except KeyError:
                    return self._json({"error": "not_found"}, 404)
        except RouterError as error:
            return self._fail(error.code, detail=error.detail, url=body.get("url") or DEFAULT_URL)
        except ValueError as error:
            return self._fail("bad_request", 400, detail=str(error))
        self._json({"error": "not_found"}, 404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        remove = {"/api/runs/": store.delete, "/api/profiles/": store.delete_profile}
        prefix = next((known for known in remove if path.startswith(known)), None)
        if prefix is None:
            return self._json({"error": "not_found"}, 404)
        if not self._allowed():
            return
        try:
            remove[prefix](unquote(path.split("/")[3]))
            return self._json({"deleted": True})
        except KeyError:
            self._json({"error": "not_found"}, 404)


class LocalServer(ThreadingHTTPServer):
    """Bind without the reverse DNS lookup HTTPServer does by default: on a machine whose
    resolver is slow or VPN-routed it blocks for tens of seconds before the page is reachable,
    and the name it resolves is only used for CGI variables this server never emits."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


def build(port=8765, session=None) -> ThreadingHTTPServer:
    Handler.session = session or Session()
    return LocalServer(("127.0.0.1", port), Handler)


def serve(port=8765, open_browser=True, session=None) -> int:
    for attempt in range(10):
        try:
            httpd = build(port + attempt, session)
            break
        except OSError:
            continue
    else:
        raise SystemExit(copy.text("ERRORS", "busy"))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"{copy.APP['name']} — {url}")
    print(copy.NOTES["password_note"])
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        session = Handler.session
        if session and session.running():
            session.cancel()
            session.thread.join(timeout=SETTLE_GRACE)   # let the finally restore automatic mode
        httpd.server_close()
    return 0
