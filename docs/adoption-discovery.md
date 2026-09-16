# Adoption discovery — what this repo already does

Phase 0a of `docs/conventions/` adoption (llm-friendly-framework 0.2.0), run 2026-09-16 on
commit `317579a`. Read-only mining of the repo's own conventions. Input to
`docs/adoption-scorecard.md`.

Stack: Python 3.14 (`requires-python >= 3.10`), stdlib `http.server` + a vanilla JS page, one
runtime dependency (`huawei-lte-api`), pytest. No lint or format tool, no CI, no instruction files.

| Observed convention | Evidence (`file:line`) | Proposed rule ID or "keep as-is" |
| --- | --- | --- |
| No `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `CONTRIBUTING.md` | `ls` at root: none | Phase 1 installs the truth layer |
| Flat package, one module per concern, each with a one-paragraph docstring saying what it owns | `src/cpe_band_scan/router.py:1`, `store.py:1`, `server.py:1`, `cli.py:1` | keep as-is; matches `llm-02` (path predicts content). Not sliced by use case (`vs-01`) — see scorecard, Phase 3 |
| No `utils` / `helpers` / `common` grab-bag files | `find` over `src tests tools`: 0 | keep as-is (`llm-02`) |
| One barrel: the package init re-exports `main` | `src/cpe_band_scan/__init__.py:1` | `llm-03` violation ×1 → Phase 2 |
| Every registration explicit: routes are an `if path == "/api/…"` chain, subcommands an `argparse` list | `src/cpe_band_scan/server.py:166-311`, `cli.py:19-46` | keep as-is (`llm-04`); the route strings are duplicated in `web/app.js` and tests (`llm-01`, `tst-04`) — Phase 2 |
| One typed error: `RouterError(code, detail)`; `code` selects the sentence in the copy catalogue | `src/cpe_band_scan/router.py:20`, `copy.py:181` (`ERRORS`) | keep as-is; already the `err-01`/`err-02` shape with a string code instead of a class per failure. Named `py-02` in `docs/conventions/python.md` |
| Every user-facing word lives in one catalogue; a parity test proves the page uses only catalogue keys | `src/cpe_band_scan/copy.py:1`, `tests/test_parity.py:1` | keep as-is; `py-03`. Reference for `con-03` (one source of truth) |
| Tests never touch the real home: an autouse fixture redirects `CPE_BAND_SCAN_HOME` | `tests/conftest.py:5` | keep as-is; `py-04` |
| Tests fake the router at the `huawei_lte_api.Connection` seam, never the app's own modules | `tests/fakes.py:1`, `src/cpe_band_scan/router.py:46` (`connection_factory`) | keep as-is; matches `tst-09` (behavior, not collaborators) |
| Test files are named after the module under test, `test_<module>.py` | `tests/test_router.py`, `tests/test_speed.py` … 18 files | keep as-is until slices exist; `tst-01` then asks for one per slice |
| Env is read at four sites in two files | `src/cpe_band_scan/store.py:16`, `cli.py:21-22`, `cli.py:50-53` | `llm-12` violation ×4 → Phase 2 (`config.py`) |
| No `TODO` / `FIXME` / `HACK` anywhere | `grep` over `src tests tools`: 0 | keep as-is (`llm-10`); the `DEBT #N` ledger starts empty |
| Comments carry only what the code cannot say (why, ceiling) | `src/cpe_band_scan/server.py:41-46`, `scanner.py:72` | keep as-is (`con-05`) |
| Broad `except Exception` at three points, each with a stated reason; two `except … : pass` | `metrics.py:106` (no reason), `scanner.py:72`, `cli.py:259`, `server.py:356`, `speed.py:95` | `err-06` candidates ×3 (`metrics.py:106`, `speed.py:95`, `speed.py:129`) → Phase 2; the rest are documented boundaries |
| Three files over 300 lines | `server.py` (364), `web/app.js` (922), `tests/test_scanner.py` (583) | `llm-06` ×3 → Phase 2/3 |
| Commit subjects are `type: sentence`; no scope, no hook | `git log`: 26 commits, all `feat:`/`fix:`/`docs:` | partial `vc-01`; scope-enum and hook → Phase 2 |
| Work happens on a feature branch (`speed-probe`), `main` receives it later | `git branch` | keep as-is (`vc-08`) |
| Plans and specs live under `docs/superpowers/`, and two plans hold absolute home paths | `docs/superpowers/plans/2026-09-16-cpe-band-scan.md:62`, `…review-fixes.md:24` | `vc-09` ×2, `doc-01` (plans belong in `.agents/plans/`) → Phase 4 |
| Toolchain: `requires-python >= 3.10`, dev venv on 3.14.7, no `.python-version`, no lockfile | `pyproject.toml:9` | `vc-10` → Phase 1 pins `.python-version` and `.nvmrc` (Node only runs `check-repo`) |
| No generated output, no codegen | `grep` for `generated` / `DO NOT EDIT`: 0 | keep as-is; `llm-08` gate has nothing to hold yet |
| No formatter, no linter | no `ruff.toml`, `.editorconfig`, `setup.cfg` | Phase 2 asks before adding `ruff` (`con-10`) — handoff |
| No CI | no `.github/` | Phase 1 adds one job running the `AGENTS.md` gate list |
