---
status: done
area: src/cpe_band_scan, tests
date: 2026-09-16
origin: none — found during llmfw adoption Phase 0 (docs/adoption-scorecard.md, gaps 2 and 3)
---

# Handoff: bring the three files over 300 lines under the limit

## Context

`llm-06`. Three files are exempt from `check-repo file-size` in `llmfw.config.json`. Each needs
a different cut; do them as three PRs, `server.py` first because it seeds Phase 3.

## Problem

- `src/cpe_band_scan/web/app.js` — 922 lines: connect, status, scan, results, test, profiles,
  polling, all in one file.
- `tests/test_scanner.py` — 583 lines: scan, trace, choose and restore cases together.
- `src/cpe_band_scan/server.py` — 364 lines: `Session`, `Handler` with 15 routes, `serve`.

## Contract

- `server.py`: one file per use case under `src/cpe_band_scan/` (`scan.py`? no — `scanner.py`
  exists; name them after the route: `api_scan.py`, `api_apply.py`, …, or a `routes/` folder as
  a new module — ask first, `vs-03`), each in the `vs-01` order: route const, request shape,
  handler. `server.py` keeps `Session`, `Handler` and an explicit list the handler reads
  (`vs-06`). Depends on `2026-09-16-route-constants.md`.
- `app.js`: one file per page section (`connect.js`, `scan.js`, `results.js`, `test.js`,
  `profiles.js`, `poll.js`), plain `<script>` tags in `index.html` in dependency order, no
  bundler (`con-10`). `tests/test_parity.py` reads `web/*.js` instead of `app.js`; `TYPES` in
  `server.py:29` already serves any `.js`.
- `tests/test_scanner.py`: split by the function under test — `test_scanner_scan.py`,
  `test_scanner_trace.py`, `test_scanner_choose.py`; shared fakes stay in `tests/fakes.py`.
- Each PR removes its file from `source.fileSize.exempt` in `llmfw.config.json`.

## Outcome (2026-09-17)

`server.py` was split into transport (`server.py`) and one `api.py` holding every handler plus
the `ROUTES`/`HANDLERS` lists, not one file per route: 16 handlers fit in 200 lines. The per-route
split is the next cut when `api.py` crosses 300 (`ARCHITECTURE.md` § don't have yet).

## Acceptance

- [ ] `node scripts/check-repo.mjs` → `check-repo: ok` with `source.fileSize.exempt` holding only `scripts/check-repo.mjs`
- [ ] `wc -l src/cpe_band_scan/*.py src/cpe_band_scan/web/*.js tests/*.py | awk '$1>300'` → only the total line
- [ ] `.venv/bin/python -m pytest -q` → `339 passed` or more
- [ ] `python tools/demo_server.py` then a scan, an apply and a test in the browser complete (manual §1)
