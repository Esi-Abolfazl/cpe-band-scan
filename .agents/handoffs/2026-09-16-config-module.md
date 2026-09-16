---
status: open
area: src/cpe_band_scan
date: 2026-09-16
origin: none — found during llmfw adoption Phase 0 (docs/adoption-scorecard.md, llm-12 row)
---

# Handoff: one `config.py` reads every environment variable

## Context

Phase 2 item 4 of `docs/conventions/` adoption. `llm-12` says configuration is read in exactly
one module; today it is read in two, and the `.env` file is parsed inline in the CLI.

## Problem

- `src/cpe_band_scan/store.py:16` — `os.environ.get("CPE_BAND_SCAN_HOME")`
- `src/cpe_band_scan/cli.py:21` — `os.environ.get("CPE_BAND_SCAN_URL", DEFAULT_URL)`
- `src/cpe_band_scan/cli.py:22` — `os.environ.get("CPE_BAND_SCAN_USER", "admin")`
- `src/cpe_band_scan/cli.py:50-53` — `os.environ.get("CPE_BAND_SCAN_PASSWORD")` then a hand-rolled
  `.env` reader.
- `DEFAULT_URL` is spelled twice: `cli.py:16` and `server.py:26`.

`gates-baseline.json` `env-reads-outside-config` = 4; `llmfw.config.json` exempts both files.

## Contract

- New `src/cpe_band_scan/config.py`: `home() -> Path`, `router_url() -> str`, `username() -> str`,
  `password() -> str | None` (env, then `.env`, else `None`), `DEFAULT_URL`. Each function reads
  the env once and validates its shape (`con-13`); a malformed value raises `RouterError` with a
  new code that gets its `copy.ERRORS` line (`py-02`).
- `store.home()` delegates to `config.home()`; `cli.parse` and `cli.read_password` call `config`.
  `server.py` imports `DEFAULT_URL` from `config`.
- `tests/conftest.py` keeps setting `CPE_BAND_SCAN_HOME`; `config.home()` must read it at call
  time, not import time (`py-04`).
- Remove the two exemptions under `llm-12` in `llmfw.config.json`, add `src/cpe_band_scan/config.py`
  as the one allowed file, and run `scripts/check_baseline.py --write`.

## Acceptance

- [ ] `grep -rn "os.environ" src/cpe_band_scan/ | grep -v config.py` → no output
- [ ] `node scripts/check-repo.mjs` → `check-repo: ok` with no `llm-12` exemption in the config
- [ ] `.venv/bin/python scripts/check_baseline.py` → `check-baseline: ok` with `env-reads-outside-config.count` = 1
- [ ] `.venv/bin/python -m pytest -q` → `339 passed` or more
