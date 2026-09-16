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

Registration is explicit: routes are an `if path ==` chain in `server.py:166-311`, subcommands an
`argparse` list in `cli.py:19-46`. There is no module list yet because there are no modules
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
| `store.py` | what did I save | `~/.cpe-band-scan` | runs, profiles, settings | none yet |
| `copy.py` | what does the person read | every sentence | catalogue dicts, `text` | none yet |
| `cli.py`, `server.py`, `web/` | the two front ends | argument parsing; routes, session, token | — | none yet |

## Request path (one worked example): the page starts a scan

1. `web/app.js:485` — `api("POST", "/api/scan", { sides, speed })`; `api()` at `app.js:22` adds the
   `X-CPE-Band-Scan-Token` header baked into the page.
2. `server.py:207` `Handler.do_POST` → `server.py:148` `_allowed` checks Host and the token with
   `hmac.compare_digest` → `server.py:254` matches `/api/scan`.
3. `server.py:261` `Session.start("scan", …)` (`server.py:88`) spawns the one job thread; a second
   job raises `RouterError("busy")` (`server.py:86`).
4. `scanner.py:133` `scan` reads the current lock, then per side `scanner.py:29` `_scan_side`:
   `lockfreq.py:37` `lock` → `metrics.py:57` `measure` → `speed.py:263` `SpeedProbe.measure` →
   yields `set_result` events; `scanner.py:78` `_restore` puts the original lock back on exit.
5. Events land in `Session.events`; `web/app.js:501` `poll` reads `GET /api/events?since=`
   (`server.py:186`) and renders progress, logs and the table.
6. `scanner.py:93` `choose` picks the winner and applies it; the run is kept in memory until the
   page saves it through `POST /api/runs` (`server.py:295` → `store.py`).

## Cross-cutting machinery (`con-16`)

| Mechanic | Implementation (`file:line`) | Convention line | Test that fails when it stops |
| --- | --- | --- | --- |
| Every `/api` request checks Host + token | `server.py:148` `_allowed` | README § Known limits | `tests/test_server.py` (token and Host cases) |
| Every failure becomes a sentence | `router.py:20` + `copy.py:181` | `py-02` | `tests/test_copy.py` |
| The page uses only catalogue words | `copy.py`, `web/app.js` | `py-03` | `tests/test_parity.py` |
| Tests never touch the real home | `tests/conftest.py:5` | `py-04` | every test (autouse) |
| A scan always restores the lock it found | `scanner.py:78` `_restore`, `server.py:45` `SETTLE_GRACE` | — | `tests/test_scanner.py` (restore cases) |

## What we deliberately don't have yet

- **Slices and modules** (`vs-01`, `vs-03`) — 15 routes in one handler, 9 subcommands in one file.
  Trigger: the first new route; it lands as one file per use case and the handler reads a list.
- **A `config.py`** (`llm-12`) — env is read in `store.py` and `cli.py`. Trigger: Phase 2 of the
  scorecard.
- **Route constants shared by server, page and tests** (`tst-04`) — 71 literals in tests and 16 in the page today. Trigger:
  Phase 2.
- **A linter and formatter** — `ruff` is proposed in a handoff; adding it is ask-first (`con-10`).
- **Scope cards** — one root `AGENTS.md` covers a 2.5k-line package. Trigger: the first module folder.
- **Firmware 3.x support** — a different router interface; the app refuses in words (`device.py:37`).
- **PyPI release** — installs from the folder; trigger: the first person who cannot `git clone`.
