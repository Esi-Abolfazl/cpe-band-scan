---
status: done
area: module
date: 2026-09-24
origin: .agents/plans/2026-09-23-project-review-fixes.md (manual QA)
---

# Handoff: a stopped scan or a later test wipes the last scan's results off the page

## Context

Found during the review-fixes plan's manual QA on the demo (`uv run tools/demo_server.py`). The
page only shows the results of the job the server holds last. That was out of scope for the
review fixes: it's a product choice about what "the results" are, not a regression.

## Problem

- `src/cpe_band_scan/web/scan.js:243` and `src/cpe_band_scan/web/page.js:41` both set
  `state.results = event.run` on any `done` event.
- Start a scan and press Stop before a band is measured. The log ends "Finished the 4G bands:
  0 measured." and the finished tables are replaced by an empty 4G table. The test picker then
  says "Run a scan first".
- Finish a scan, then run a test, then reload. `resume()` replays only the server's last job, the
  test, so `state.results` is empty. The tables and the picker are gone, although the scan
  finished minutes ago and nothing was saved.

## Contract

- A scan that measured nothing never replaces the results on screen.
- A reload after a test still shows the last finished scan. The server keeps the last scan's
  `done` run apart from the last job, or `/api/events` returns it; the page never re-derives it.
- One source for "the last results", shared by the live path and `resume()`. Today there are two
  copies of the same line.

## Acceptance

- [x] `uv run pytest -q tests/test_page_behaviour.py` → a stopped 0-band scan leaves
  `state.results` as it was.
- [x] `uv run pytest -q tests/test_server_jobs.py` → after a scan then a test, a fresh events
  read still yields the scan's run.
- [x] `uv run pytest -q` → all pass.

## Resolution (2026-09-24)

`Session.results` holds the last scan whose run measured a band (`server.py`, `_drive`), and
`/api/events` returns it as `results`. `poll()` and `resume()` both take `state.results` from that
answer, so the page no longer derives it from `done` events.
