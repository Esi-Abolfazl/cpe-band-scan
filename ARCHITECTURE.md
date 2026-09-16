# cpe-band-scan — architecture

What exists and how the pieces fit, as of the last change to this file. Decisions live in
`docs/adr/`; rules in `docs/conventions/`; this file narrates the current shape with pointers.

## Shape

One Python package, `src/cpe_band_scan/`, flat. Two front ends share one engine: `cli.py`
(terminal) and `server.py` (a stdlib `ThreadingHTTPServer` on `127.0.0.1` serving `web/` and
`/api/*`). The engine is `scanner.py` composing `lockfreq.py` (write the lock), `metrics.py`
(read the signal), `speed.py` (probe the internet through the router). `router.py` is the only
module that imports `huawei_lte_api`; every other module reaches the router through `Router.get`
and `Router.post`. `store.py` owns the home folder. `copy.py` owns every sentence.

Registration is explicit: every `/api` route is one line of `api.ROUTES` (`api.py:12`) and one line
of `api.HANDLERS` (`api.py:182`); subcommands are an `argparse` list in `cli.py:14-41`. The page
receives `ROUTES` in its bootstrap (`server.py:153`) and the tests import it. `config.py` is the
only module that reads the environment. There is no module list because there are no modules
(`docs/adoption-scorecard.md` § seams).

## Modules

| Module | Product question it answers | Owns | Exposes | Card |
| --- | --- | --- | --- | --- |
| `router.py` | how do we talk to the router | the `huawei_lte_api` session, `RouterError` | `Router`, `RouterError`, `host` | none yet |
| `device.py` | can this router lock bands | firmware/model probe | `Device`, `probe` | none yet |
| `lockfreq.py` | what is locked, lock this | the lock-freq payload shape | `lock`, `read_lock`, `bands_of` | none yet |
| `metrics.py` | how good is this band | samples, summaries, grades, ranking | `measure`, `grade`, `rank` | none yet |
| `speed.py` | what did the band deliver, past the VPN | LAN route pinning, DNS via router, verdict | `SpeedProbe`, `verdict` | none yet |
| `scanner.py` | which band is steadiest here | the run shape, restore-on-exit | `scan`, `trace`, `choose` | none yet |
| `config.py` | what did the environment say | every `os.environ` read (`llm-12`) | `home`, `router_url`, `username`, `password`, `DEFAULT_URL` | none yet |
| `api.py` | what answers each `/api` request | `ROUTES`, `HANDLERS`, one function per route | `match`, the two tables | none yet |
| `store.py` | what did I save | `~/.cpe-band-scan` | runs, profiles, settings | none yet |
| `copy.py` | what does the person read | every sentence | catalogue dicts, `text` | none yet |
| `cli.py`, `server.py`, `web/*.js` | the two front ends | argument parsing; session, token, dispatch; one page script per section | — | none yet |

## Request path (one worked example): the page starts a scan

1. `web/scan.js:218` — `api("POST", routes.scan, { sides, speed })`; `api()` at `web/app.js:26` adds
   the `X-CPE-Band-Scan-Token` header, and `routes` came with the token in the page bootstrap.
2. `server.py:173` `Handler.do_POST` → `server.py:179` `_dispatch`: `api.match` (`api.py:36`) names
   the route, `server.py:144` `_allowed` checks Host and token with `hmac.compare_digest`, then
   `api.HANDLERS[("POST", "scan")]` runs `api.scan` (`api.py:80`).
3. `api.py:87` `Session.start("scan", …)` (`server.py:84`) spawns the one job thread; a second
   job raises `RouterError("busy")` (`server.py:82`).
4. `scanner.py:133` `scan` reads the current lock, then per side `scanner.py:29` `_scan_side`:
   `lockfreq.py:37` `lock` → `metrics.py:57` `measure` → `speed.py:263` `SpeedProbe.measure` →
   yields `set_result` events; `scanner.py:78` `_restore` puts the original lock back on exit.
5. Events land in `Session.events`; `web/scan.js:234` `poll` reads `routes.events` (`api.py:57`)
   and renders progress, logs and the table.
6. `scanner.py:93` `choose` picks the winner and applies it; the run is kept in memory until the
   page saves it through `routes.runs` (`api.save_run` → `store.py`).

## Cross-cutting machinery (`con-16`)

| Mechanic | Implementation (`file:line`) | Convention line | Test that fails when it stops |
| --- | --- | --- | --- |
| Every `/api` request checks Host + token | `server.py:144` `_allowed`, called once in `_dispatch` | README § Known limits | `tests/test_server.py` (token and Host cases) |
| Every write endpoint holds the session lock | `api.py` handlers `with session.lock:` | — | `tests/test_server_jobs.py` `test_the_write_endpoints_hold_the_session_lock` |
| Routes are spelled once | `api.py:12` `ROUTES` | `llm-01`, `tst-04` | `check-repo forbidden-patterns` (`tst-04`, `llm-01`) |
| Every failure becomes a sentence | `router.py:20` + `copy.py:181` | `py-02` | `tests/test_copy.py` |
| The page uses only catalogue words | `copy.py`, `web/*.js` | `py-03` | `tests/test_parity.py` |
| Tests never touch the real home | `tests/conftest.py:5` | `py-04` | every test (autouse) |
| A scan always restores the lock it found | `scanner.py:78` `_restore`, `server.py:42` `SETTLE_GRACE` | — | `tests/test_scanner_restore.py` |

## What we deliberately don't have yet

- **One file per route** (`vs-01`) — the 16 handlers share `api.py` (200 lines). Trigger: `api.py`
  crossing 300 lines; the handler that pushes it over moves to its own file, `HANDLERS` stays.
- **Modules with contracts doors** (`vs-03`, `vs-04`) — a flat package of 12 modules. Trigger: a
  second product (another router family) that must not see this one's internals.
- **A linter and formatter** — `ruff` is proposed in a handoff; adding it is ask-first (`con-10`).
- **Scope cards** — one root `AGENTS.md` covers a 2.5k-line package. Trigger: the first module folder.
- **Firmware 3.x support** — a different router interface; the app refuses in words (`device.py:37`).
- **PyPI release** — installs from the folder; trigger: the first person who cannot `git clone`.
