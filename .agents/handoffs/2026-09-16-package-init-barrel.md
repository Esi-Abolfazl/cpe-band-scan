---
status: done
area: src/cpe_band_scan
date: 2026-09-16
origin: none — found during llmfw adoption Phase 0 (docs/adoption-scorecard.md, llm-03 row)
---

# Handoff: the package init re-exports nothing

## Context

`llm-03`: no barrels. The package's `__init__.py` re-exports `main` and nobody needs it there.

## Problem

- `src/cpe_band_scan/__init__.py:1` — `from .cli import main`.
- Every real entry names the module: `pyproject.toml:12-13` (`cpe_band_scan.cli:main`),
  `src/cpe_band_scan/__main__.py:1` (`from .cli import main`).
- Side effect: importing any submodule (`from cpe_band_scan import copy` in `tests/test_parity.py:7`)
  imports `cli`, and through it `argparse`, `getpass`, `server` dependencies.

`llmfw.config.json` exempts the file under `llm-03`.

## Contract

- `__init__.py` becomes empty (zero bytes, or the one-line package docstring).
- `tests/test_packaging.py` gains one assertion: the init file has no `import` line.
- Remove the `llm-03` exemption from `llmfw.config.json`.

## Acceptance

- [ ] `grep -c "import" src/cpe_band_scan/__init__.py` → `0`
- [ ] `.venv/bin/cpe-band-scan help` → prints the command table
- [ ] `.venv/bin/python -m cpe_band_scan help` → prints the command table
- [ ] `node scripts/check-repo.mjs` → `check-repo: ok` with no `llm-03` exemption
- [ ] `.venv/bin/python -m pytest -q` → one more test than before, all passing
