---
status: done
area: module
date: 2026-09-24
origin: .agents/plans/2026-09-23-project-review-fixes.md (Task 3)
---

# Handoff: the 5G table's Lowest column shows the 4G floor the rating no longer uses

## Context

Task 3 of the review-fixes plan made the 5G side graded and ranked on the NR carrier alone
(`metrics.FLOOR["nr"] == "nrfloor"`). The progress line now reads the rated floor from the
`set_result` event's `floor` key. The results tables were left alone to keep that change to the
ranking rule.

## Problem

- `src/cpe_band_scan/web/results.js:61` renders `row.floor` (the LTE SINR floor) in the Lowest
  column of both tables.
- `src/cpe_band_scan/cli.py:133` does the same in `results_table`.
- On the 5G table a row can read "Excellent" beside a Lowest of −8 dB, because the rating rests
  on `nrfloor`, which no column shows.

## Contract

- The 5G table's Lowest column shows `nrfloor`; the 4G table's keeps `floor`.
- One source for which floor a side rests on: `metrics.FLOOR`. The page must not re-spell the
  mapping; carry it in the run record or the bootstrap rather than in a JS literal.
- Runs saved before 2026-09-24 have no `nrfloor`: show "–" for them, never the LTE floor.

## Acceptance

- [x] `uv run pytest -q tests/test_cli.py` → a saved NR scan prints its `nrfloor` in Lowest.
- [x] `uv run pytest -q tests/test_parity.py` → page and terminal pick the same floor per side.
- [x] `uv run pytest -q` → all pass.

## Resolution (2026-09-24)

The page bootstrap carries `floors: metrics.FLOOR`. `results.js` renders `row[floors[side]]` and
`cli._cells` reads `metrics.FLOOR[side]`. A missing or NaN floor prints "—", the page's `num()`
dash, not the en dash this contract named, so page and terminal agree.
