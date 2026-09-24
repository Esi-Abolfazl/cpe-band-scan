---
status: done
run-with: not yet run
origin: .agents/handoffs/2026-09-21-project-review.md
---

# Project review fixes (2026-09-21 review, re-verified 2026-09-23)

**Goal:** close every confirmed finding of the 2026-09-21 review plus three found on
re-verification, each with a regression test written first (red → green).

**Architecture:** no new modules, no new dependency, no wire-name renames. Each fix lands in
the layer that owns the rule: restore boundary in `scanner.py`, timeouts in `router.py`,
grading in `metrics.py`, request framing in `server.py`, lock semantics in `api.py`, file
safety in `store.py`, page logic in `web/*.js`, words in `copy.py`.

## Verification of the review (2026-09-23, commit `411c033`)

| # | Finding | Verdict | Evidence | Severity (review → here) |
|---|---|---|---|---|
| 1 | Restore starts after first mutation | ✅ reproduced | scan: signal failure after clear → writes `[('', '')]`, B7/N78+41 never restored. trace: close after `trace_start` → writes only B3 | P1 → P1 |
| 2 | No router timeout | ✅ read | `router.py:58` passes no `timeout`; installed `Connection(..., timeout=None)` forwards to every request | P1 → P1 |
| 3 | NR rank led by LTE grade | ✅ reproduced | `rank({N41: nrsinr -5, N78: nrsinr 25}, side="nr")` → `['N41', 'N78']` | P1 → P1 |
| 4 | Malformed body still writes | ✅ read | `server.py:131-136` maps bad JSON to `{}`, outside the `try` at :189; `[]`/`null` → `AttributeError`, no response | P1 → **P2** (token-gated: only the page can send; still a crash path) |
| 5 | LTE apply drops NR secondaries | ✅ reproduced | `apply({"lte": ["3"]})` with N78+41 → writes NR `78` | P2 → P2 |
| 6 | Auto test row tests current lock | ✅ read | `test.js:118` drops empty `lte`; `api.py:99` + `scanner.py:198` collapse `[]`/absent | P2 → P2 |
| 7 | Profile "In use" ignores secondaries | ✅ read | `profiles.js:10` compares `[0]` only | P2 → P2 |
| 8 | Store races / non-atomic writes | ✅ read | `store.py:40,82,157,189` write in place; read-modify-write unlocked | P2 → split: **8a P2** (data loss, see N1), **8b P3** (race needs two simultaneous requests from one person) |
| 9 | `.env` not ignored | ✅ read | `.gitignore` has no `.env`; `config.py:28` + README use it | P2 → P2 |
| 10 | `show` of a test run / missing id | ✅ reproduced | `cli.main(["show", "<missing>"])` → uncaught `KeyError` | P2 → P3 |
| 11 | Profile fetch failure shows empty list | ✅ read | `profiles.js:56` `catch { state.profiles = []; }` | P2 → P3 |
| 12 | `--write` can raise the ratchet | ✅ read | `check_baseline.py:29` writes before the growth check | P3 → P3 |
| — | Demo `connect` arity | ✅ read | `tools/demo_server.py:92` two args, `server.py:66` needs three; handoff `2026-09-19-demo-server-connect-arity.md` open | → P2 (blocks all manual QA) |

**Found on re-verification (not in the review):**

- **N1 (P2, data loss)** — a corrupt `profiles.json` reads as `[]` (`store.py:75`), and the next
  `save_profile` writes `rows + [profile]` (`store.py:97`) over it: every saved profile is gone.
  Same shape for `settings.json` (`store.py:34` → `:46`). This is the sharp end of #8.
- ~~**N2 (P3)**~~ — withdrawn on implementation: `cli test` calls `scanner.trace(router)` with
  no cancel callback and the fixed 120 s / 10 s, so a zero-sample test cannot happen there;
  Ctrl-C leaves through the `KeyboardInterrupt` branch before any save.
- **N3 (P3)** — `trace()` grades with LTE criteria too (`scanner.py:216`); an NR-only test gets
  an LTE grade. Same root as #3 and closed by the same `grade(side=…)` change.

## Decisions (recommended defaults — confirm or change before Task 3, 6, 8)

- **D1 · NR grade rule (#3).** Recommended: `summarise` adds `nrfloor = min(nrsinr)`; the NR side
  grades on `nrfloor` with the same SINR thresholds as LTE (5 / 0 / −5 dB) and no RSRQ gate (the
  router reports no NR RSRQ in `SIGNAL_FIELDS`); NR rank keys become `("nrfloor", "nrsinr")`.
  A row with NaN NR values stays out of the ranking, as today.
- **D2 · Store across processes (#8b).** Recommended: in-process `threading.Lock` + atomic
  `os.replace`. Ceiling: two `ui` processes on the same home can still interleave profile edits —
  named in a `ponytail:` comment. Correct-everywhere alternative: an `O_EXCL` lock file with
  stale-lock handling (Windows is supported, so no `fcntl`) — ~40 lines, only worth it if two
  instances on one home is a real use.
- **D3 · Page behaviour tests (#6, #7, #11).** Recommended: pytest runs `node` (already pinned in
  `.nvmrc` for `check-repo`, already in CI) against a small `vm` harness that loads `app.js` +
  the file under test with stubbed `state`/`copy`/`api`. No npm package. Makes `uv run pytest`
  require Node — Ask-first under `con-10` as a tooling change.
- **D4 · Router timeout values (#2).** `TIMEOUT = (5, 30)` seconds (connect, read) in
  `router.py`. The lock-freq POST on firmware 4.x takes a few seconds; 30 s leaves margin.

## Tasks

Each task: write the failing test, see it fail, fix, see it pass, run the three gates, one commit.

### Phase 1 — P1: the router is never left locked or hung

**Task 1 · Restore boundary before the first write (#1).**
- `scanner.scan`: open the `try/finally` right after `original = lockfreq.read_lock(router)`, so
  the up-front clear, settle, baseline read, band discovery and `yield start` are all inside it.
- `scanner.trace`: open the `try` before the test lock at `:199`; the `trace_start` yield and its
  `read_lock` move inside.
- Tests (`tests/test_scanner_restore.py`, `tests/test_scanner_trace.py`): baseline signal read
  fails after the clear → last write is the original lock; generator closed right after
  `run_start` → original restored; trace read-back fails / closed after `trace_start` → original
  restored. Assert exactly one restore write (no double restore).

**Task 2 · Bounded router calls (#2).**
- `router.py`: `TIMEOUT = (5, 30)`; `_session` passes `timeout=TIMEOUT` to the factory.
  `requests.Timeout` already subclasses `OSError` → `RouterError("unreachable")`, no new code.
- `tests/fakes.py`: `factory.make` accepts `timeout=None`.
- Test (`tests/test_router.py`): a local socket on `port=0` that accepts and never answers →
  `Router(...).get(...)` raises `RouterError("unreachable")` within the bound (monkeypatch
  `router.TIMEOUT` to `(0.2, 0.2)` so the test is fast).
- `server.SETTLE_GRACE` stays; with bounded calls the shutdown join at `server.py:238` can no
  longer be outlived by a hung read.

**Task 3 · NR ranked and graded by NR (#3, N3) — needs D1.**
- `metrics.summarise`: add `nrfloor`. `metrics.grade(measurement, expect_5g, side="lte")`: NR
  side uses `nrfloor` and skips RSRQ. `RANK_KEYS["nr"] = ("nrfloor", "nrsinr")`; `rank` passes
  `side` to `grade`.
- Callers: `scanner._scan_side` passes `side`; `scanner.trace` passes `"nr"` only when the test
  locked NR and not LTE.
- Tests (`tests/test_metrics.py`, `tests/test_scanner_scan.py`): the N41/N78 regression; NR order
  unchanged when only LTE fields vary across rows; auto-apply picks N78 end to end.

### Phase 2 — P2: correctness

**Task 4 · Request framing before any side effect (#4).**
- `server._body`: raise `ValueError` for a bad `Content-Length`, a body over 1 MiB, invalid JSON,
  or a non-object. Call it inside the `try` in `_dispatch`.
- `_dispatch`: add a last `except Exception` → `_fail("crash", 500, detail=repr(error))` so no
  request ends as a dropped connection; the `RouterError` branch reads `url` from a body that is
  now guaranteed a dict.
- Tests (`tests/test_server.py`): `{broken`, `[]`, `null`, `Content-Length: x` to `apply`, `clear`,
  `connect`, `scan` → 400 `bad_request`, fake `posts == []`, no job started.

**Task 5 · An omitted side keeps its whole lock (#5).**
- `api.apply`: `nr_scell = current["nr"][1] if "nr" not in body else []` and pass it.
- Tests (`tests/test_server_jobs.py`): LTE-only apply keeps N78+41; NR-only apply keeps B7+B3.

**Task 6 · Test "automatic" means automatic (#6) — needs D3 for the page test.**
- Contract: a side present in the `test` body is locked for the test, `[]` = automatic; an absent
  side keeps its lock. `api.test` passes `None` for absent; `scanner.trace(lte=None, nr=None, …)`
  guards on `is not None`.
- `test.js`: the auto row sends `lte: []` (no `scell`); `lockSentence` names it with an existing
  or new `copy.NOTES` entry for "automatic" (new key → `CONTEXT.md` if it is a new term).
- Tests: API/engine in `tests/test_scanner_trace.py` (auto with B7 locked → write `lte_info`
  mode 0, then B7 restored); page payload in the D3 harness.

**Task 7 · "In use" means the whole lock matches (#7) — needs D3.**
- `profiles.js:10`: compare anchors and secondaries of both sides with `sameBands`.
- Test (D3 harness): B7+B3 current vs saved B7+B1 → not in use, Apply shown.

**Task 8 · Store never destroys what it can't read (#8a, #8b, N1) — needs D2.**
- One `_write(path, text, private=False)`: temp file in the same folder, `chmod 0o600` before the
  swap when `private`, `os.replace`. All four writers use it.
- `_LOCK = threading.Lock()` around every read-modify-write (settings, profiles, run rename).
- Corrupt `profiles.json` → `RouterError("store_unreadable", path)` (new catalogue line) from
  reads and writes; never overwritten. Corrupt `settings.json` → renamed to
  `settings.json.bad` once and read as empty (the page must still load; nothing is destroyed).
- Tests (`tests/test_store.py`, `tests/test_settings.py`): two concurrent renames both survive;
  a write that fails mid-way leaves the old file intact; corrupt profiles → error, file bytes
  unchanged after a save attempt; settings stays `0o600`.

**Task 9 · Local credential files are ignored (#9).**
- `.gitignore`: `.env`, `.env.*`, `!.env.example`.
- Test (`tests/test_packaging.py`): `git check-ignore` says `.env` and `.env.local` are ignored,
  `.env.example` is not.

**Task 10 · Demo starts (handoff `2026-09-19-demo-server-connect-arity.md`).**
- Follow that handoff's contract and acceptance; mark it `done`.

### Phase 3 — P3

**Task 11 · Terminal `show` / `runs` / `test` (#10, N2).**
- `runs` and `show` move inside the `try`; `KeyError` → new `run_not_found` catalogue line, exit 1.
- `show` of `kind == "test"` prints the summary with the page's `traceSummary` keys
  (`floor, sinr, rsrq, rsrp, five_g, carriers`) through `copy.COLUMNS`.
- Tests (`tests/test_cli.py`): saved test prints 7.5; missing id → exit 1, catalogue sentence,
  no traceback; an unreadable run file → `store_unreadable`, exit 1.

**Task 12 · A failed profile read keeps the list (#11) — needs D3.**
- `refreshProfiles`: keep `state.profiles` on failure and `showError(failure.message)`.
- Test (D3 harness): rejected `api` → previous list kept, error shown.

**Task 13 · `--write` only lowers (#12).**
- `check_baseline.main`: with `--write`, a grown count prints the growth and exits 1 without
  writing. A newly approved entry is added to `gates-baseline.json` by hand in its own reviewed
  diff (AGENTS.md § Baseline).
- Test (`tests/test_check_baseline.py`): grown `--write` → exit 1, file bytes unchanged; lowered
  `--write` → exit 0, count lowered.

## Not in this plan

- Flaky fake download server noise → `2026-09-17-flaky-fake-download-server.md` (open).
- `ruff` → `2026-09-16-ruff-lint-format-gate.md` (Ask first).
- Review's "later product improvements" (page run history, longer contender comparison, UTC
  timestamps / `con-15`) — product choices, not bugs; each gets its own handoff if wanted.
- A failed restore on the error path is not reported to the person (`scanner.py:188` drops
  `_restore`'s result) — small, but it changes the event contract; handoff if wanted.

## Acceptance

- [x] Every task's named test fails on `411c033` and passes after its commit.
- [x] `uv run pytest -q` → all pass.
- [x] `node scripts/check-repo.mjs` → `check-repo: ok`.
- [x] `uv run scripts/check_baseline.py` → `check-baseline: ok`.
- [x] Manual QA on the demo (after Task 10), temp home: connect, scan then cancel, auto-row test
  then restore, profile differing only in secondaries, reload after a test; 375 px and 1440 px,
  keyboard, both colour schemes.

## Manual QA findings (2026-09-24)

- Fixed: after a reload, a test was worded from the router's whole lock. A 4G-automatic test read
  "Locked to N78", and a test of the connection as it is read as a lock. `trace_start` now carries
  the test's `plan`, and the live page and `resume()` both word it through `testWhat`.
- Fixed: `socketserver`'s listen backlog of 5 is smaller than one page load's burst of
  connections. macOS reset the overflow, and about 1 load in 20 came up blank
  (`LocalServer.request_queue_size = 128`).
- Handoff: `.agents/handoffs/2026-09-24-keep-last-scan-results.md`. A stopped 0-band scan, or a
  reload after a test, wipes the last scan's results off the page.
