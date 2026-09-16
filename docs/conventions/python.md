# Python — stack rules for cpe-band-scan

Rule IDs: `py-`. Project-owned; framework files in this folder stay verbatim. Each rule names the
file that already follows it — copy that, not a description of it.

## py-01 — Reference slice: `src/cpe_band_scan/device.py`

One use case (`probe`), a typed input (`Router`), a typed output (`Device`, a dataclass), typed
failures (`RouterError("firmware_not_supported")`). A new use case copies this shape: constants,
then the public function, then private helpers below it (`llm-05`). Its test is
`tests/test_device.py`, named after the module.

## py-02 — `RouterError(code)` is the only error; `code` is the wire key

Every failure the router side raises is `RouterError(code, detail)` (`src/cpe_band_scan/router.py:20`).
The `code` is a `snake_case` literal that exists as a key in `copy.ERRORS`
(`src/cpe_band_scan/copy.py:181`); the sentence is never written at the raise site (`err-02`).
Adding a code adds the catalogue line in the same change. Renaming a code is a wire change to the
page and the terminal — ask first (`err-01`).

## py-03 — Every user-facing word lives in `copy.py`

`src/cpe_band_scan/copy.py` is the one home for labels, help, errors, notes and progress lines for
both front ends. `tests/test_parity.py` fails when the page uses a key the catalogue lacks or the
catalogue holds a key the page never renders. A sentence typed into `app.js`, `cli.py` or
`server.py` directly is a defect.

## py-04 — Tests never touch the real `~/.cpe-band-scan`

`tests/conftest.py:5` redirects `CPE_BAND_SCAN_HOME` to a temp folder for every test, autouse. A
test that reads or writes the home path any other way is a defect, and so is a new setting that
bypasses `store.home()`.

## py-05 — The router is faked at the library seam

Tests substitute `huawei_lte_api.Connection` through `Router(connection_factory=…)` with
`tests/fakes.py`, never patch the app's own modules (`tst-09`). A test that mocks `lockfreq`,
`metrics` or `scanner` to test `scanner` is testing the implementation.

## Gate mapping

| Rule | Gate |
| --- | --- |
| `py-02` | `tests/test_copy.py` (every raised code has a sentence) |
| `py-03` | `tests/test_parity.py` |
| `py-04` | `tests/conftest.py` fixture; review |
| `llm-01`, `llm-03`, `llm-04`, `llm-06`, `llm-10`, `llm-12`, `tst-04`, `err-06`, `vc-09` | `scripts/check-repo.mjs` + `llmfw.config.json`, no exemptions except the framework's own script |
| `vs-06` (routes) | `api.HANDLERS` is the list; `tests/test_server_jobs.py` `test_the_write_endpoints_hold_the_session_lock` reads it |
| a rule violated again | `gates-baseline.json` + `scripts/check_baseline.py` (empty today) |

Version: 0.2.0
