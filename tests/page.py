"""Executes page scripts in Node (already a gate: .nvmrc, check-repo) so a test asserts on what the
page does and sends, not on its source text. Scripts share one global scope, as in the browser;
`script` runs last, inside an async function, and its return value comes back as `result`."""
import json
import shutil
import subprocess
from pathlib import Path

from cpe_band_scan import api, copy, metrics

WEB = Path(api.__file__).parent / "web"
HARNESS = Path(__file__).with_name("page_vm.mjs")


def run(files, script, responses=None) -> dict:
    """`responses` maps "METHOD /path" to {"status": int, "body": {...}}; anything else is 200 {}."""
    node = shutil.which("node")
    assert node, "the page tests need Node, pinned in .nvmrc"
    spec = {"files": [str(WEB / name) for name in files], "script": script, "responses": responses or {},
            "bootstrap": {"token": "t", "copy": copy.bundle(), "routes": api.ROUTES, "floors": metrics.FLOOR,
                          "defaults": {"url": "192.168.8.1", "username": "admin", "remembered": False}}}
    done = subprocess.run([node, str(HARNESS)], input=json.dumps(spec), capture_output=True, text=True,
                          timeout=30, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)
