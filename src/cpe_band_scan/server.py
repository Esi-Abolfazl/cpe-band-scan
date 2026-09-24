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
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import api, config, copy, metrics, scanner, speed, store
from .config import DEFAULT_URL
from .device import probe
from .router import Router, RouterError, host

WEB = Path(__file__).parent / "web"
ALLOWED_HOSTS = ("127.0.0.1", "localhost")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8"}


def finite(value):
    """JSON has no spelling for NaN, and a browser refuses a body that carries one."""
    if isinstance(value, float) and value != value:
        return None
    if isinstance(value, dict):
        return {key: finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite(item) for item in value]
    return value


SETTLE_GRACE = scanner.PER_SET + speed.DURATION + 5   # worst case: cancel lands just as a band's
                                     # settle-and-measure window starts, including the probe's own
                                     # window; give the job's finally block that long to clear the
                                     # lock and restore automatic mode


MAX_BODY = 1 << 20   # the largest body is a saved 10-minute test: 60 samples x ~0.3 KB = 18 KB


def _default_router(url, password, username):
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

    def connect(self, url, password, username):
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
        self._send(status, json.dumps(finite(payload), default=str).encode(), "application/json")

    def _fail(self, code, status=409, **fields):
        self._json({"error": code, "message": copy.text("ERRORS", code, **fields)}, status)

    def _body(self) -> dict:
        """ValueError for anything but a JSON object, before a handler can act on it."""
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 <= length <= MAX_BODY:
            raise ValueError(f"Content-Length {length}")
        body = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(body, dict):
            raise ValueError(f"body must be a JSON object, got {type(body).__name__}")
        return body

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
        bootstrap = json.dumps({"token": self.session.token, "copy": copy.bundle(), "routes": api.ROUTES,
                                "floors": metrics.FLOOR,
                                "defaults": {"url": host(saved.get("router_url", DEFAULT_URL)),
                                             "username": saved.get("username") or config.username(),
                                             "remembered": bool(saved.get("password"))}})
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self._send(200, html.replace("/*BOOTSTRAP*/", f"window.CPE_BAND_SCAN = {bootstrap};").encode(),
                   TYPES[".html"])

    def do_GET(self):
        path = urlparse(self.path).path
        asset = WEB / path.lstrip("/")
        if path in ("/", "/index.html") or (asset.parent == WEB and asset.suffix in TYPES and asset.is_file()):
            if not self._host_allowed():
                return
            if path in ("/", "/index.html"):
                return self._page()
            return self._send(200, asset.read_bytes(), TYPES[asset.suffix])
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def _dispatch(self, method):
        """Route → handler in api.HANDLERS; its exceptions become the HTTP answers."""
        parsed = urlparse(self.path)
        hit = api.match(parsed.path)
        if hit is None or (method, hit[0]) not in api.HANDLERS:
            return self._json({"error": "not_found"}, 404)
        if not self._allowed():
            return
        body = {}
        try:
            if method == "POST":
                body = self._body()
            return self._json(api.HANDLERS[(method, hit[0])](self.session, body, hit[1], parse_qs(parsed.query)))
        except KeyError:
            return self._json({"error": "not_found"}, 404)
        except RouterError as error:
            url = host(body.get("url") or DEFAULT_URL) if method == "POST" else getattr(self.session.router, "url", "")
            return self._fail(error.code, detail=error.detail, url=url)
        except ValueError as error:
            return self._fail("bad_request", 400, detail=str(error))
        except Exception as error:                      # a crash must still answer the page
            return self._fail("crash", 500, detail=repr(error))


class LocalServer(ThreadingHTTPServer):
    """Bind without the reverse DNS lookup HTTPServer does by default: on a machine whose
    resolver is slow or VPN-routed it blocks for tens of seconds before the page is reachable,
    and the name it resolves is only used for CGI variables this server never emits.
    socketserver's backlog of 5 is below one page load's burst of connections; macOS resets
    the overflow, so a script fails to load and the page comes up blank."""
    request_queue_size = 128

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
