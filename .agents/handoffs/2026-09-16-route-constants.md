---
status: open
area: src/cpe_band_scan, tests
date: 2026-09-16
origin: none — found during llmfw adoption Phase 0 (docs/adoption-scorecard.md, gap 1)
---

# Handoff: routes are spelled once, in a constant the server, the page and the tests all read

## Context

Scorecard gap 1 (`tst-04`, `llm-01`). The `/api/*` paths are literals in three places; renaming
one leaves a green test hitting a 404 the assertion never checks.

## Problem

- `src/cpe_band_scan/server.py:166-311` — 15 routes in the `if path ==` chain.
- `src/cpe_band_scan/web/app.js:149, 166, 183, 255, 485, 498, 502, 616 …` — 16 literals.
- `tests/test_server_jobs.py`, `tests/test_server_runs.py`, `tests/test_server.py`,
  `tests/test_end_to_end.py` — 71 literals.

`gates-baseline.json`: `literal-routes-in-tests` = 71, `route-literals-in-page` = 16.

## Contract

- `server.py` (or a new `routes.py`, ask-first as a new module — `AGENTS.md`) declares one mapping
  `ROUTES = {"status": "/api/status", "scan": "/api/scan", …}`; the handler chain matches against
  `ROUTES[...]`. Prefix routes (`/api/runs/<id>`) keep their prefix in the same mapping.
- The page receives `ROUTES` the same way it receives the token today (baked into `index.html`
  at `server.py:171`); `app.js` calls `api("POST", ROUTES.scan, …)`.
- Tests import `ROUTES` from the server module; no `"/api/` literal remains under `tests/`.
- Flip: in `llmfw.config.json` remove the four `tst-04` exemptions; in `gates-baseline.json` run
  `--write` (both counts reach 0) and then delete the two counters — a rule at zero is enforced by
  `check-repo`, not ratcheted.

## Acceptance

- [ ] `grep -rn "\"/api/" tests/` → no output
- [ ] `grep -c "/api/" src/cpe_band_scan/web/app.js` → `0`
- [ ] `node scripts/check-repo.mjs` → `check-repo: ok` with no `tst-04` exemption
- [ ] `.venv/bin/python -m pytest -q` → `339 passed` or more
- [ ] `.venv/bin/python -m pytest tests/test_parity.py -q` → passes (the page still uses only catalogue words)
