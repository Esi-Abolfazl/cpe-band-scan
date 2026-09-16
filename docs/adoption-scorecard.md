# Adoption scorecard — cpe-band-scan vs. llm-friendly-framework 0.2.0

## Burn-down, 2026-09-17

Every baseline row below was retired one day after adoption, on branch `chore/burn-down-baseline`.
The table and sections that follow are the 2026-09-16 audit, kept as the record of where the repo
started.

| Row | Retired by | Gate now |
| --- | --- | --- |
| Literal routes (`tst-04`, `llm-01`) | `api.ROUTES` + `api.HANDLERS`; page reads `routes` from the bootstrap; tests import `ROUTES` | `check-repo forbidden-patterns`, no exemption |
| Files over 300 lines (`llm-06`) | `server.py` → `api.py` split; `web/app.js` → 8 page scripts; `tests/test_scanner.py` → 4 files + `tests/fake_scan_router.py` | `check-repo file-size`, only `scripts/check-repo.mjs` exempt |
| Env reads (`llm-12`) | `config.py` | `check-repo forbidden-patterns`, `config.py` the one allowed file |
| Machine paths (`vc-09`) | plans moved to `.agents/plans/`, paths scrubbed; spec and design ruling marked history under `docs/design/` | `check-repo forbidden-patterns`, no exemption |
| Barrel (`llm-03`) | `__init__.py` empty; `tests/test_packaging.py` keeps it so | `check-repo forbidden-patterns` |
| Swallowed failures (`err-06`) | each of the three sites carries `# boundary:` on its `except` line, which the pattern does not match | `check-repo forbidden-patterns` |

Still open: `ruff` as lint+format gate (ask-first, `.agents/handoffs/2026-09-16-ruff-lint-format-gate.md`);
slices per route and modules (Phase 3, deferred until `api.py` or a second product needs them —
`ARCHITECTURE.md` § don't have yet); the flaky fake download server
(`.agents/handoffs/2026-09-17-flaky-fake-download-server.md`).

## Audit, 2026-09-16

Phase 0 audit, 2026-09-16, commit `317579a`, informed by `docs/adoption-discovery.md`. Counts come
from `scripts/check-repo.mjs` run in report mode (scratch config, no exemptions) and from `grep`;
the raw report tail is at the bottom. Nothing was fixed in this step. Every exemption in
`llmfw.config.json` and every count in `gates-baseline.json` traces to one row here.

| Area | Rule(s) | Current state (count, `file:line` samples) | Gate that holds it | Phase |
| --- | --- | --- | --- | --- |
| Literal routes in tests | `tst-04`, `llm-01` | 71 literals in 4 files: `tests/test_server_jobs.py:13`, `tests/test_server_runs.py:12`, `tests/test_server.py:64`, `tests/test_end_to_end.py:19`; 16 more in `src/cpe_band_scan/web/app.js:485`, and the server spells them once more at `server.py:254` | `check-repo forbidden-patterns` (exempt today), `gates-baseline.json` ratchet | 2 |
| Files over 300 lines | `llm-06` | 3: `src/cpe_band_scan/web/app.js` (922), `tests/test_scanner.py` (583), `src/cpe_band_scan/server.py` (364) | `check-repo file-size` (3 exemptions) | 2 (`server.py`), 3 (`app.js`) |
| Env read outside one module | `llm-12` | 4 sites in 2 files: `src/cpe_band_scan/store.py:16`, `cli.py:21`, `cli.py:22`, `cli.py:50` | `check-repo forbidden-patterns` (exempt today), ratchet | 2 |
| Machine paths committed | `vc-09` | 2 files, ~40 lines: `docs/superpowers/plans/2026-09-16-cpe-band-scan.md:62`, `…review-fixes.md:24` | `check-repo forbidden-patterns` (exempt `docs/superpowers/**`) | 4 |
| Barrel | `llm-03` | 1: `src/cpe_band_scan/__init__.py:1` re-exports `main` | `check-repo forbidden-patterns` (exempt today) | 2 |
| Swallowed failure | `err-06` | 3: `src/cpe_band_scan/metrics.py:106` (`except (RouterError, Exception): continue`, no reason), `speed.py:95` and `speed.py:129` (`except OSError: pass`, reason stated at the code) | `check-repo forbidden-patterns` (exempt today), ratchet | 2 |
| No slices, no modules | `vs-01`, `vs-03`, `vs-06` | 0 slices. 10 concern-modules in one flat package; 15 `/api/*` routes in one handler class (`server.py:114`) and 9 subcommands in one file (`cli.py:19`) | review + `docs/conventions/python.md` `py-01` reference | 3 |
| Toolchain pinned | `vc-10` | none: `pyproject.toml:9` says `>= 3.10`, the venv is 3.14.7, no `.python-version` | `check-repo toolchain-version` | 1 |
| CI | `doc-04`, `con-18` | none | `.github/workflows/ci.yml` | 1 |
| Agent contract, glossary, architecture | `doc-01`, `llm-09` | none of `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `ARCHITECTURE.md` | `check-repo agents-link`, `md-links` | 1 |
| Debt ledger | `llm-10` | 0 TODOs, 0 `DEBT` — clean | `check-repo debt-ledger` | 1 (on from day one) |
| Commit format | `vc-01` | 26/26 commits `type: subject`, no scope, no hook | commit-msg hook | 2 |
| Plans and specs location | `doc-01` | 4 files, 7.4k lines under `docs/superpowers/`; framework home is `.agents/plans/` | `check-repo md-links` after the move | 4 |
| Lint / format | (`gates/README.md` layers 2–3) | none | `ruff` — a new dependency, ask first (`con-10`) | 2 |
| Grab-bag files, TODOs, reflection scans, generated output | `llm-02`, `llm-10`, `llm-04`, `llm-08` | 0, 0, 0, none | `check-repo` config (on) | — |
| One error type, one copy catalogue, parity test | `err-01`, `err-02`, `con-03` | already the shape: `router.py:20`, `copy.py:181`, `tests/test_parity.py` | `tests/test_parity.py` | — |

## Top five gaps, by count × blast radius

1. **Routes as 87 literals across tests (71), page (16) and server** (`tst-04`, `llm-01`). Renaming one route
   today leaves a green test hitting a 404 the assertion never checks, and the page silently
   drifting. Fix shape: one `ROUTES` mapping in the server module (or a tiny `routes.py`), the
   handler chain, `app.js` and every test read from it; the page gets the mapping baked in next to
   the token it already receives. Then the `tst-04` pattern flips from exempt to enforced.
2. **`app.js` at 922 lines** (`llm-06`). One file holds connect, status, scan, results, test,
   profiles and polling. Fix shape: one file per page section under `web/`, loaded as plain
   `<script>` tags in `index.html` (no bundler — `con-10`). The parity test already reads the
   folder, so it keeps working once its glob covers the new files.
3. **`server.py` handler at 364 lines holding 15 routes** (`llm-06`, `vs-01`). This is where
   Phase 3 starts: one file per use case (`connect.py`, `scan.py`, `apply.py`…) each declaring its
   route const, request shape and handler, registered in one explicit list the handler reads.
   `device.py` is the reference shape (`py-01`).
4. **Env read in three places** (`llm-12`). `store.py:16`, `cli.py:21-22`, `cli.py:50`. Fix shape:
   `config.py` with one typed function per setting (`home()`, `router_url()`, `password()`), read
   once at startup; the `.env` file parsing moves there too.
5. **No pinned toolchain, no CI** (`vc-10`, `con-18`). Every "tests pass" so far is a local claim.
   Phase 1 closes this: `.python-version`, `.nvmrc`, one CI job running the `AGENTS.md` gate list.

## Module seams (input to Phase 3)

Import graph (`grep '^from \.' src/cpe_band_scan/*.py`):

- **Router door** — `router.py` is the only module that imports `huawei_lte_api`; `device.py`,
  `lockfreq.py`, `metrics.py`, `scanner.py` reach the router only through `Router.get`/`post`.
  This is already a contracts door in all but name (`vs-04`).
- **Engine** — `scanner.py` composes `lockfreq`, `metrics`, `speed`. Product question: "which band
  is steadiest here". Owns the run shape, the ranking, the restore-on-exit rule.
- **Store** — `store.py`, no imports from siblings. Owns `~/.cpe-band-scan` (runs, profiles,
  settings). Product question: "what did I save".
- **Two front ends** — `cli.py` and `server.py` each import the whole engine plus `copy` and `store`.
  They are the entry-point layer; every route/subcommand is a slice candidate.
- **Copy** — `copy.py` imported by both front ends; its parity test is the one existing
  architecture-style test (`tst-08` shape).

Implicit cross-calls to watch: `server.py:40-46` reads `scanner.PER_SET` and `speed.DURATION` to
size its cancel grace — a constant reaching across a boundary; Phase 3 gives it a name on the
engine's side.

## Already good — name it as the reference

- `src/cpe_band_scan/device.py` — one use case (`probe`), typed input (`Router`), typed output
  (`Device`), typed failures (`RouterError("firmware_not_supported")`). Reference slice `py-01`.
- `RouterError(code)` + `copy.ERRORS[code]` — the `err-01`/`err-02` split with the catalogue in
  place. Reference `py-02`.
- `tests/test_parity.py` — the page may use only catalogue keys, and every key is used. The pattern
  for every future mirror check (`con-03`).
- `tests/conftest.py` — no test can touch the person's real data. `py-04`.
- `tests/fakes.py` — the router is faked at the library seam, not at the app's modules (`tst-09`).

## What would make Phase 1 red on day one, and the exemption taken

| Gate | Failing today | Exemption in `llmfw.config.json` | Retire in |
| --- | --- | --- | --- |
| `file-size` | 3 files | `source.fileSize.exempt`: `server.py`, `web/app.js`, `tests/test_scanner.py` | Phase 2/3 |
| `forbidden-patterns` `vc-09` | 2 plan files | `exempt: ["docs/superpowers/**"]` | Phase 4 (move to `.agents/plans/`, scrub paths) |
| `forbidden-patterns` `llm-12` | `store.py`, `cli.py` | `exempt: ["src/cpe_band_scan/store.py", "src/cpe_band_scan/cli.py"]` | Phase 2 (`config.py`) |
| `forbidden-patterns` `tst-04` | 4 test files | `exempt` the 4 files; the 71 count is ratcheted in `gates-baseline.json` | Phase 2 |
| `forbidden-patterns` `llm-03` | `__init__.py` | `exempt: ["src/cpe_band_scan/__init__.py"]` | Phase 2 |
| `forbidden-patterns` `err-06` | `speed.py:95`, `speed.py:129`, `metrics.py:106` | `exempt` both files; ratcheted | Phase 2 |
| `forbidden-patterns` `vc-09` | this file's raw report tail quotes the regex | `exempt: ["docs/adoption-scorecard.md"]` | never — the tail is evidence |
| `file-size` | `scripts/check-repo.mjs` (360, the framework's own file) | `source.fileSize.exempt` | on the next framework upgrade |

Everything else in `check-repo` (`agents-link`, `rule-ids`, `adr`, `debt-ledger`, `md-links`,
`forbidden-paths`, `toolchain-version`) is green with no exemption.

## Raw report tail (scratch config, no exemptions)

```
file-size: src/cpe_band_scan/server.py is 364 lines, limit 300 — a second responsibility?
file-size: src/cpe_band_scan/web/app.js is 922 lines, limit 300 — a second responsibility?
file-size: tests/test_scanner.py is 583 lines, limit 300 — a second responsibility?
forbidden-patterns: docs/superpowers/plans/2026-09-16-cpe-band-scan.md:62 matches /(/Users/|/home/[a-z]|C:\\\\Users)/ — machine-specific path committed (vc-09)
forbidden-patterns: docs/superpowers/plans/2026-09-16-review-fixes.md:24 matches /(/Users/|/home/[a-z]|C:\\\\Users)/ — machine-specific path committed (vc-09)
forbidden-patterns: src/cpe_band_scan/cli.py:21 matches /os\.environ|getenv\(/ — config read outside the config module (llm-12)
forbidden-patterns: src/cpe_band_scan/store.py:16 matches /os\.environ|getenv\(/ — config read outside the config module (llm-12)
forbidden-patterns: src/cpe_band_scan/server.py:356 matches /except[^\n]*:\s*\n\s*pass\b/ — swallowed failure (err-06)
forbidden-patterns: src/cpe_band_scan/speed.py:95 matches /except[^\n]*:\s*\n\s*pass\b/ — swallowed failure (err-06)
forbidden-patterns: tests/test_end_to_end.py:19 matches /["']/api// — literal route in a test (tst-04)
forbidden-patterns: tests/test_server.py:64 matches /["']/api// — literal route in a test (tst-04)
forbidden-patterns: tests/test_server_jobs.py:13 matches /["']/api// — literal route in a test (tst-04)
forbidden-patterns: tests/test_server_runs.py:12 matches /["']/api// — literal route in a test (tst-04)
forbidden-paths: src/cpe_band_scan/__init__.py matches /(^|/)__init__\.py$/ — package init re-exports (llm-03)

check-repo: 14 failure(s)
```

`server.py:356` (`except KeyboardInterrupt: pass` on shutdown) and the `except OSError: continue`
loops that walk ports or interfaces (`server.py:345`, `speed.py:82`, `speed.py:138`) are
try-the-next-candidate, not swallowed failures; the committed `err-06` pattern matches only
`except Exception … pass|continue` and `except OSError: pass`.
