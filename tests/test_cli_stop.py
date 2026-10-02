"""However the terminal's scan is stopped, the lock the router arrived with goes back."""
import signal
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


TERMINATED_SCAN = """
import threading, time
from cpe_band_scan import cli
from tests.fake_scan_router import ARRIVES_LOCKED, DEVICE, build, last_write, signal
router, session = build([signal(8)] * 200, lock=ARRIVES_LOCKED)
cli.connect = lambda args: (router, DEVICE)
def cleared():
    while not session.posts:
        time.sleep(0.05)
    print("cleared", flush=True)
threading.Thread(target=cleared, daemon=True).start()
code = cli.main(["scan", "--no-speed"])
bands = [entry["band"] for entry in last_write(session)["lte_info"]["freq_infos"]["freq_info"]]
print("restored", bands, code, flush=True)
"""


@pytest.mark.skipif(sys.platform == "win32", reason="Windows has no SIGTERM to deliver")
def test_a_terminated_scan_puts_the_arriving_lock_back():
    """Regression: stopping a background scan sends SIGTERM, not Ctrl-C. Unhandled, it skipped
    the scan's finally and left the router locked to the band under test."""
    child = subprocess.Popen([sys.executable, "-c", TERMINATED_SCAN], cwd=ROOT, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in child.stdout:
        if line.strip() == "cleared":
            break
    child.send_signal(signal.SIGTERM)
    out, err = child.communicate(timeout=20)
    assert "restored ['7'] 130" in out, err
