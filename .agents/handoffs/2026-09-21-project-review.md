---
status: done
area: package
date: 2026-09-21
origin: none — found during the owner's project review from zero
---

# Handoff: reliability, correctness, and usability improvements

## Context

The owner requested a review and suggestions. Implementation is outside this review's scope.
No application source or tests were changed. The development environment was installed with
`uv sync --extra dev`. This source snapshot has no `.git`, so history and tracked-secret
inspection were unavailable. No real router was contacted or written to.

The review covered the router adapter, scan and measurement engine, API, local storage, terminal,
page scripts, tests, packaging, CI, and repository conventions. Python reproductions used the
existing library-seam fakes and temporary storage. JavaScript behavior was exercised with Node's
standard-library VM. Full browser/visual QA remains outstanding: the documented demo fails to start.

Keep the compact architecture: the shared engine, single router adapter, explicit routes, and
central copy catalogue are useful foundations. Prioritize observable correctness over new layers.

Gate evidence before this documentation-only handoff (Python 3.14.7; locally available Node
26.8.2, whereas `.nvmrc` specifies Node 24; the Node 24 environment was not verified):

```text
uv run pytest -q
359 passed in 32.58s
node scripts/check-repo.mjs
check-repo: ok
uv run scripts/check_baseline.py
check-baseline: ok
```

The pytest run also printed an HTTP worker exception fragment. The existing
`2026-09-17-flaky-fake-download-server.md` handoff records the matching symptom; the partial
output here does not independently establish its cause.

## Problem

### 1. P1 — Restoration starts after the first router mutation

- `src/cpe_band_scan/scanner.py:138` clears an existing lock, but the protected `try/finally`
  starts at line 157. A baseline read, band discovery, or settle failure in between skips restore.
- `scanner.py:198` changes a test lock; the protected block starts at line 204, after settling,
  reading the lock again, and yielding `trace_start`.
- Reproduced scan startup failure with an existing B7 lock and a failing signal read:
  `scan_start_failure: unreachable writes: ['0']`. Only automatic mode was written.
- Reproduced test startup read-back failure: only B3 was written; original B7 was not restored.
- Move the recovery boundary before the first mutation, including early generator closure.

### 2. P1 — Router operations have no network timeout

- `src/cpe_band_scan/router.py:58` creates the connection without `timeout`.
- The installed, locked `huawei-lte-api 2.0.1` exposes `Connection(..., timeout=None)` and
  passes that value through its HTTP requests. This was checked in the installed library source.
- A router that accepts a connection but never responds can leave connect, scan, or restore
  waiting indefinitely. `server.py:238` joining the daemon worker cannot force restoration.
- Add explicit finite connect/read limits at the router boundary and test a nonresponding local
  HTTP peer. Ensure cancellation/shutdown accounts for bounded reads and restoration.

### 3. P1 — 5G ranking is dominated by the 4G grade

- `src/cpe_band_scan/metrics.py:90` uses `grade()` as the first sort key for both sides;
  `grade()` at line 70 reads LTE `floor` and `rsrq` even when `side='nr'`.
- A constructed N41 measurement with NR SINR -5 dB and excellent LTE ranks above N78 with
  NR SINR +25 dB and good LTE: `NR_rank_LTE_grade_dominates: ['N41', 'N78']`.
- This contradicts the intended NR behavior documented at `metrics.py:84` and can affect
  automatic application through `scanner.py:124`.
- Make ranking and displayed grades use consistent criteria for the side being measured.
  Define missing-NR-data handling and verify LTE fluctuations cannot alone reorder NR results.

### 4. P1 — Malformed requests can still write to the router

- `src/cpe_band_scan/server.py:131` converts invalid JSON to `{}`; it does not require an object.
  Body parsing also occurs outside the dispatch exception handler at line 188.
- Reproduced an authenticated clear request with body `{broken`: HTTP result 200,
  `{'applied': True}`, and one fake router write.
- Bodies `[]` and `null` passed to connect raise uncaught `AttributeError` instead of a JSON error.
- Validate body framing, maximum size, JSON object shape, and each handler's inputs before side
  effects. Use the existing `bad_request` response; unexpected server failures also need a
  consistent response. A malformed request must produce zero router writes and start no job.

### 5. P2 — Applying 4G drops secondary carriers from untouched 5G

- `src/cpe_band_scan/api.py:116` reads both complete locks, but line 120 omits `nr_scell`.
- Reproduced current NR anchor 78 with secondary 41, then applied LTE B7 only: the outgoing
  NR `all_bands` was `78`, losing 41.
- Preserve the entire omitted side, including its secondary carriers. Keep explicit clearing
  separate from omission, and cover both LTE-only and NR-only writes.

### 6. P2 — Choosing automatic mode for a test tests the current lock instead

- `src/cpe_band_scan/web/test.js:7` includes the auto row in choices. Lines 118–119 omit empty
  band selections from the request. `api.py:99` and `scanner.py:198` also collapse empty/absent.
- Executed `onTest()` with the LTE auto row selected: the request was only
  `{"seconds":60,"gap":10}`. With B7 currently locked, the test therefore measures B7.
- Represent keep-current and explicit automatic mode distinctly through UI, API, and engine.
  Restore the original lock afterward and describe the chosen automatic side in the page copy.

### 7. P2 — A different profile can be marked In use and cannot be applied

- `src/cpe_band_scan/web/profiles.js:10` compares only anchors, ignoring secondary carriers.
  At line 33, a match replaces Apply with the In use badge.
- Executed comparison of current B7 + B3 secondary and saved B7 + B1 secondary:
  `different_secondaries_marked_in_use: true`.
- Compare both portions of both sides, with appropriate set semantics. The profile should
  remain applicable whenever its complete lock differs from the current lock.

### 8. P2 — Concurrent storage updates lose successful changes

- `src/cpe_band_scan/store.py:108` and line 118 independently read, modify, and rewrite the
  profiles file; API rename/delete handlers have no shared storage lock.
- Reproduced two successful concurrent renames of different profiles using a barrier at the
  filesystem write boundary. Final names were `['B', 'A renamed']`; B's rename was lost.
- Files are also overwritten in place at `store.py:40`, 82, 157, and 189. An interrupted write
  can truncate the only copy. Reading corrupt settings/profiles silently returns empty data.
- Serialize read/modify/write operations, use atomic file replacement, preserve private settings
  permissions, and handle unreadable/corrupt data visibly. Define behavior for multiple app
  processes sharing the same home; an in-process mutex alone does not cover that case.

### 9. P2 — The documented password file is not ignored by Git

- `src/cpe_band_scan/config.py:28` reads `.env`; README's terminal instructions recommend it.
  `.gitignore:1`–9 contains no `.env` or `.env.*` rule.
- This is an accidental commit risk, not evidence that a credential has leaked. This snapshot
  has no Git history to inspect.
- Ignore local credential files while allowing a deliberately sanitized example if needed.
  Add a packaging/repository regression check without committing any password fixture.

### 10. P2 — Saved terminal tests cannot be usefully reopened

- `src/cpe_band_scan/cli.py:190` always renders a scan table for `show`, while trace runs store
  `summary` and `samples` (`scanner.py:217`) instead of scan sides.
- Reproduced a saved test whose summary contains 7.5 dB: `show` exited 0 and printed only the
  name and empty table headers; no 7.5 value appeared.
- `show` and `runs` also execute before the CLI exception boundary at line 199. A nonexistent
  run ID raised uncaught `KeyError` in the reproduction.
- Render each run kind appropriately and handle missing/corrupt stored runs with catalogue
  messages and a nonzero exit code.

### 11. P2 — Profile read failures are displayed as an empty list

- `src/cpe_band_scan/web/profiles.js:56` catches every request failure and replaces profiles
  with `[]`. The UI can tell a person there are no saved profiles after an actual read failure.
- Preserve the last successful list, report failure through the error banner, and offer refresh.
  Add a behavior check for rejected profile requests, not just a source-text assertion.

### 12. P3 — The baseline rewrite can increase the ratchet

- `scripts/check_baseline.py:29` writes the current count unconditionally with `--write`,
  bypassing the growth check at line 31.
- Isolated fixture: stored count 1, actual hits 2; normal check fails, `--write` succeeds and
  stores 2, then normal check passes. The current committed baseline is empty, so this is a
  tooling contract gap rather than a current product failure.
- Reject count increases through the normal lowering command. Decide explicitly how a newly
  approved baseline entry is introduced; preserve a separate review path for that action.

### Already tracked — Demo startup and test noise

- `tools/demo_server.py:92` calls `Session.connect` without `username`. Launching the documented
  demo raised `TypeError: Session.connect() missing 1 required positional argument: 'username'`.
  Reuse `2026-09-19-demo-server-connect-arity.md`; add a startup smoke check.
- Reuse `2026-09-17-flaky-fake-download-server.md` for the HTTP worker exception noise.
- Ruff remains an optional, ask-first dependency proposal in
  `2026-09-16-ruff-lint-format-gate.md`. It has lower priority than the behavior gaps above.

## Contract

Implement items 1–4 first, then 5–10 plus the demo repair. Extend checks around each reproduced
failure. Keep the existing runtime architecture and wire names; put new user-visible words in
`copy.py`. Any dependency, new top-level module, ADR, or wire-key rename still follows AGENTS.md.

Testing improvement: execute page behavior and request payloads, not only regex assertions like
`tests/test_page_quality.py:130`. Node's built-in VM can cover pure logic now without a dependency.
Browser automation for connect, scan/cancel, apply, profiles, and reload needs a separate tooling
decision if a new dependency is proposed. Exercise early errors and cleanup, not just happy paths.

Later product improvements, proposed rather than classified as bugs:

- Preserve completed page scans and offer run history. `server.py:88` discards prior events for
  every new job; `web/page.js:37` only recovers scans present in those events. The existing run
  storage/API can support this. `ARCHITECTURE.md` request-path step 6 incorrectly implies the
  page already saves runs; align that document with whichever behavior ships.
- Offer a longer comparison of close contenders before automatic application. Measurements use
  five samples (`metrics.py:16`), so repeated measurements and visible sample counts would help
  users judge consistency. Treat this as a product choice; do not claim calibrated confidence.
- Store timezone-aware UTC instants and format locally at display time. `store.py:86` and 150
  currently persist naive local timestamps, contrary to `con-15`. Preserve readable older data.

## Acceptance

These commands are implementation acceptance targets. Add the named regression cases first;
existing green tests alone do not resolve this review.

- [ ] `uv run pytest -q tests/test_scanner_restore.py tests/test_scanner_trace.py` → passes with
  startup failure, settle interruption, and early generator-close restoration regressions.
- [ ] `uv run pytest -q tests/test_router.py tests/test_server_jobs.py` → passes with a local
  nonresponding peer, bounded timeout behavior, and shutdown/cancel cleanup coverage.
- [ ] `uv run pytest -q tests/test_metrics.py tests/test_scanner_scan.py` → passes with an NR
  ordering regression where LTE grades vary independently of unchanged NR measurements.
- [ ] `uv run pytest -q tests/test_server.py tests/test_server_jobs.py` → malformed/non-object
  requests return 400 with `bad_request`, write nothing, and start no job; all assertions pass.
- [ ] `uv run pytest -q tests/test_server_jobs.py` → an LTE-only apply preserves the complete
  existing NR lock, including its secondary carriers; the reciprocal case also passes.
- [ ] `uv run pytest -q tests/test_scanner_trace.py tests/test_page_quality.py` → passes with
  executed JavaScript/API coverage of explicit auto versus keep-current and complete profile
  equality; differing secondary carriers leave Apply available.
- [ ] `uv run pytest -q tests/test_settings.py tests/test_store.py tests/test_server_runs.py`
  → concurrent changes to separate profiles both survive; interrupted writes preserve the old
  valid file; settings privacy and corrupt-file error handling assertions pass.
- [ ] `uv run pytest -q tests/test_packaging.py` → includes passing ignore-rule checks for
  `.env` and local `.env.*` files, with any sanitized example exception explicitly covered.
- [ ] `uv run pytest -q tests/test_cli.py` → saved trace summaries print their measurements;
  absent/corrupt runs return a nonzero status and a catalogue sentence without a traceback.
- [ ] `uv run pytest -q tests/test_page_quality.py` → a failed profile fetch preserves existing
  profiles and shows an error in an executed behavior regression.
- [ ] `uv run pytest -q tests/test_check_baseline.py` → a growing `--write` exits nonzero and
  leaves the baseline unchanged; lowering a count still succeeds.
- [ ] `uv run pytest -q` → complete suite passes, including demo startup coverage and the above
  regressions, without the known fake download-server exception noise.
- [ ] `node scripts/check-repo.mjs` → `check-repo: ok`.
- [ ] `uv run scripts/check_baseline.py` → `check-baseline: ok`.

Manual QA after demo repair: use a temporary application home and the fake router. Check connect,
scan then cancel, explicit-auto test then restore, a profile differing only in secondary carriers,
and reload after a test. Inspect at 375 px and 1440 px, with keyboard navigation and both color
schemes. This review did not claim completion of those visual checks or real-router validation.
