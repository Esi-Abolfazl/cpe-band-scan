# CPE Band Scan — spec

**Date:** 2026-09-16
**Origin:** the `bandscan` Claude Code skill, now turned into a standalone app so people can run it
without an LLM. The skill itself survives, moved inside the app's own repository.

## Names

| Thing | Name | Why |
|---|---|---|
| The product | **CPE Band Scan** | An app can afford real words. It names the work and the hardware: CPE is the industry term for a fixed home 4G or 5G router |
| Install name | `cpe-band-scan` | `pipx install cpe-band-scan` |
| Import package | `cpe_band_scan` | |
| Commands | `cpe-band-scan`, with `cpescan` as a short alias | Both reach the same CLI. `cpe-band-scan ui` opens the page |
| Stored data | `~/.cpe-band-scan` | Saved runs and the remembered router address. Never a password |
| The bundled skill | `bandscan`, invoked `/bandscan` | A slash command is typed often, so it stays short. It ships in `skills/bandscan` inside this repo |

## Goal

A local app that finds the LTE/NR band giving the steadiest connection on a Huawei CPE router, ranks the
bands, and locks the one the user picks. No LLM anywhere in the loop.

## Shape

A **local web GUI**: a Python process on the user's own machine serves one page at `127.0.0.1:8765` and
drives the router's HTTP API. The same package also exposes a CLI, because the GUI is a thin client over
the same engine.

Why a local page instead of a native GUI: no toolkit dependency, works the same on macOS/Windows/Linux,
and the browser tab survives the ~30 s connection drops that every band change causes (the page talks to
localhost, not through the router's WAN).

## Requirements

| # | Requirement | Where it lands |
|---|---|---|
| R1 | Default router address `192.168.8.1`, editable | Task 10 (server default), Task 13 (field) |
| R2 | Ask the user for the router admin password | Task 13 |
| R3 | If the device isn't supported, say so **and why** | Task 2 (probe + reason codes), Task 8 (messages) |
| R4 | Scan every supported band, both 4G and 5G | Task 6 |
| R5 | Rank results best to worst in a table with a rating | Task 4 (grade/rank), Task 14 (table) |
| R6 | User applies any row; the top row is the default | Task 14 |
| R7 | Test/trace option (2 minutes, no change) | Task 6 (engine), Task 15 (view) |
| R8 | Every field and action has a `?` explaining it | Task 8 (copy), Tasks 13-15 (popovers), Task 16 (parity test) |
| R9 | All text follows the `ux-writing` skill | Task 8, reviewed in Task 16 |
| R10 | Save a finished run under a name; browse saved runs and open their details | Task 7 (store), Task 12 (API), Task 15 (UI) |
| R11 | Default name comes from the carrier name | Task 2 (carrier read), Task 7 (`default_name`) |
| R12 | The assistant skill ships with the app, still called `bandscan` | Task 18 |

## Rules carried over from the skill

- **Firmware decides the driver, never the model name.** `SoftwareVersion` 4.x + `lock_freq_switch` = 3 +
  a readable `net/lock-freq` → the lock-freq driver. Anything else stops with a reason. Never write
  `LTEBand` to `api/net/net-mode` on 4.x: it answers `-1` and still applies the mode part, silently
  killing 5G.
- **Never ask the user to disconnect a VPN.** The scan reads the router's LAN API, so a VPN doesn't change
  the numbers. Ask for one stable server for the duration; if the API is unreachable, point at the VPN's
  "allow local network access" setting.
- **Rank by the SINR floor, not the peak.** Single windows swing ±5 dB. A band that loses the `N` carrier
  is never recommended.
- **A single-band lock kills carrier aggregation.** Runner-up bands go in as secondaries (`all_bands`).

## Out of scope for v1 (named, not forgotten)

| Left out | Why | Add when |
|---|---|---|
| Throughput/speed test per band | Measures the whole path (VPN, peering, server), not the radio; slow and noisy. The radio metrics answer the question asked. | Users ask "but what Mbps?" — then add an opt-in per-band speedtest with a clear label that it measures the whole path |
| Firmware 3.x/2.x driver (`net-mode` band mask) | No device on hand to test the write against; a wrong mask can drop the connection. The probe already names the case. | A 3.x device is available to test on |
| Signed, double-clickable native bundle (PyInstaller/Tauri) | Needs code signing and notarisation per OS to avoid scary warnings. | Distributing beyond people who can run one install command |
| Password in the OS keychain | In-memory is enough for a single run and avoids a `keyring` dependency plus a per-OS unlock prompt. | Users run scans often enough to be annoyed by retyping |
| Persian UI | Not requested. `copy.py` is a flat dict, so a second language is a second dict, not a refactor. | Asked for |
| Scheduled / repeated scans | The lock is set once per location; re-scanning is a manual decision. | Someone wants an overnight comparison |
| Multiple routers at once | One radio, one lock. | Never, probably |

## Risks

- **The router's API can stop answering XML.** Seen on 2026-09-16: `/api/webserver/SesTokInfo` returned
  `<meta http-equiv="refresh" url="/index">` instead of a token, and the library died on `KeyError: 'token'`.
  The app must report this as "answered, but not a Huawei router API", never as a crash.
- **Every band change drops the link for ~30 s.** A full scan is ~18 LTE + ~10 NR sets, so ~30 minutes of
  intermittent connectivity. The UI must say this before the first scan, not after.
- **The scan must always restore automatic mode**, including on cancel, crash, or process kill.
