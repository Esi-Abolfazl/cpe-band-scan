"""The README's no-router path: tools/demo_server.py starts, connects and answers the page."""
import runpy
import threading
from pathlib import Path

from cpe_band_scan import api, server
from cpe_band_scan.api import ROUTES
from tests.test_server import call

DEMO = Path(__file__).resolve().parents[1] / "tools" / "demo_server.py"


def test_the_demo_connects_to_its_fake_router_and_serves_its_status(monkeypatch):
    """Regression: the demo called Session.connect with two of its three arguments and died on
    start, and no gate ran it."""
    handed = {}
    monkeypatch.setattr(server, "serve", lambda **kwargs: handed.update(kwargs))
    monkeypatch.setattr(api, "SLEEP", api.SLEEP)      # the demo swaps both; put them back after
    monkeypatch.setattr(api, "PROBE", api.PROBE)
    runpy.run_path(str(DEMO), run_name="__main__")
    session = handed["session"]
    httpd = server.build(port=0, session=session)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
    try:
        status, body = call(httpd.server_address[1], "GET", ROUTES["status"], token=session.token)
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200 and body["device"]["model"] == "H155-381"
