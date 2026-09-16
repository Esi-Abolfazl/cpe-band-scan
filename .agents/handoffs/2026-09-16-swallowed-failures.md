---
status: done
area: src/cpe_band_scan
date: 2026-09-16
origin: none — found during llmfw adoption Phase 0 (docs/adoption-scorecard.md, err-06 row)
---

# Handoff: three swallowed failures either say why at the code or stop swallowing

## Context

`err-06` / `con-14`. The committed pattern in `llmfw.config.json` matches three sites, exempted at
baseline (`gates-baseline.json` `broad-except-swallowed` = 3).

## Problem

- `src/cpe_band_scan/metrics.py:106` — `except (RouterError, Exception): continue` in
  `visible_bands`. No reason given; `Exception` already covers `RouterError`. A router that refuses
  `device/nbrcellinfo` is silently the same as a router that lists no cells.
- `src/cpe_band_scan/speed.py:95` — `except OSError: pass` after `scope()`; the comment says
  `verdict()` decides whether the bypass held. Reason stated, so this one may stay — as a named
  boundary, not an accident.
- `src/cpe_band_scan/speed.py:129` — `except OSError: pass` inside `resolve`. Read the function
  and decide: fallback by design (say so in ≤ 3 lines, `con-05`) or a lost failure.

## Contract

- `metrics.py:106`: catch `RouterError` only; the docstring already says the result is a hint.
  If any other exception is expected, name it.
- Each site that stays gains a comment stating the boundary it implements (`con-05`), and the
  `err-06` pattern in `llmfw.config.json` learns to skip a trailing `# boundary:` marker — or the
  file exemption stays and the scorecard row says so. Pick one; do not leave both.
- Run `scripts/check_baseline.py --write` when the count changes.

## Acceptance

- [ ] `sed -n 106p src/cpe_band_scan/metrics.py` → `except RouterError:`
- [ ] `.venv/bin/python -m pytest tests/test_metrics.py -q` → passes
- [ ] `.venv/bin/python scripts/check_baseline.py` → `check-baseline: ok` with `broad-except-swallowed.count` ≤ 2
- [ ] `node scripts/check-repo.mjs` → `check-repo: ok`
