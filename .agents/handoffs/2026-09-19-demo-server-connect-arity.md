---
status: done
area: tooling
date: 2026-09-19
origin: none — found during the pip → uv toolchain migration, when the README line finally had an interpreter again
---

# Handoff: `tools/demo_server.py` crashes on startup — `Session.connect` gained a third argument

## Context

The uv migration changed README § "Try it without a router" from `python tools/demo_server.py`
to `uv run tools/demo_server.py`, because the removed `source .venv/bin/activate` had been the
only thing putting `cpe_band_scan` on the path. Running it then exposed a second, older break
that the missing interpreter had been hiding. The fix is in `tools/`, outside a toolchain change,
so it stopped here.

## Problem

`tools/demo_server.py:92` calls `connect` with two arguments:

```python
session.connect("192.168.8.1", "demo")
```

`src/cpe_band_scan/server.py:66` takes three:

```python
def connect(self, url, password, username):
```

`uv run tools/demo_server.py` dies immediately:

```
TypeError: Session.connect() missing 1 required positional argument: 'username'
```

Pre-existing: the same two-argument call is at the base of the migration branch. Nothing in
`tests/` or `llmfw.config.json` references `demo_server`, which is why no gate caught it — the
README's only no-router path has been dead since `username` was added.

## Contract

- `tools/demo_server.py` passes the username the fake router expects (`_demo_router` at
  `tools/demo_server.py:78` accepts whatever `Session` forwards; `admin` matches the real
  default).
- The demo path gets one gate so it cannot rot again: a test that imports `demo_server` with a
  stubbed `server.serve` and asserts the session connects, or a smoke check that starts it on a
  free port and expects HTTP 200.

## Acceptance

- [ ] `uv run tools/demo_server.py` → serves on 8766, no traceback
- [ ] `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8766/` → `200`
- [ ] `uv run pytest -q` → passes, with the new demo-path test included
