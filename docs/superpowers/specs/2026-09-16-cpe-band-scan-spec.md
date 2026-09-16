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
| Stored data | `~/.cpe-band-scan` | Terminal runs, lock profiles and the remembered router address. The password only behind the page's Remember tick, in an owner-only file (superseded 2026-09-16: the user asked not to retype it) |
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
| ~~Throughput/speed test per band~~ | Retired 2026-09-16: the user asked "but what Mbps?". See the addendum below. | — |
| Firmware 3.x/2.x driver (`net-mode` band mask) | No device on hand to test the write against; a wrong mask can drop the connection. The probe already names the case. | A 3.x device is available to test on |
| Signed, double-clickable native bundle (PyInstaller/Tauri) | Needs code signing and notarisation per OS to avoid scary warnings. | Distributing beyond people who can run one install command |
| Password in the OS keychain | In-memory is enough for a single run and avoids a `keyring` dependency plus a per-OS unlock prompt. Retyping did annoy, so the page now offers an opt-in owner-only file instead (2026-09-16). | Someone wants it out of a plain file: keychain becomes the next step |
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

## Addendum 2026-09-16: per-band speed and ping

**Why.** The ranking measures the radio (SINR floor, RSRQ). Three things that decide what a person
feels are invisible to it: carrier width, cell load and the core-network path. A clean 12 dB band can be
the slowest option at 8 pm. A width tiebreaker was considered and dropped: it only fires on a grade tie,
never contradicts the grade, and the firmware often omits the width. What gives a real-world expectation
is a measurement of the thing itself, per band.

**What.** Opt-in, default on, one checkbox on the scan form and `--no-speed` in the terminal. After the
radio samples of each band (including the auto row), the app measures from this computer through the
router: five TCP connects to a fixed host for the ping (median and spread), then a five-second download
capped at 50 MB for the speed. Both are shown as two extra columns, Speed (Mbit/s) and Ping (ms). They
**never enter the ranking**: cell load moves hour to hour, so a single reading cannot be a rank key until
repeated scans show how stable it is (a follow-up, not a v1 rule).

**The VPN is bypassed, and the bypass is proven, not assumed.** A VPN on this computer would make every
band look like the VPN server. So the probe routes past it: every probe socket is scoped to the network
interface that reaches the router (`IP_BOUND_IF` on macOS, `SO_BINDTODEVICE` on Linux, `IP_UNICAST_IF`
on Windows) and bound to this computer's LAN address. **DNS goes through the LAN too**: the 2026-09-16
check on a Mac with a fake-IP VPN (the tunnel answers every name with a 198.18.x.x address only it can
route) showed a scoped connect to a system-resolved address simply times out. The probe host is resolved
with a plain DNS query sent through the scoped socket to the router, falling back to 1.1.1.1. Before the
first band the app compares the public address seen through the LAN socket with the one seen through the
default route and tells the person which of four cases they are in:

| verdict | meaning | sentence the person reads |
|---|---|---|
| `not_needed` | the default route already leaves by the LAN: no tunnel | no VPN was active; the numbers are the plain connection |
| `confirmed` | a tunnel is up and the two public addresses differ | measured straight through the router, past the VPN |
| `failed` | a tunnel is up and both addresses are the same | the VPN couldn't be bypassed; the numbers include it; compare rows with each other |
| `blocked` | a tunnel is up and nothing answers outside it | the VPN blocks traffic outside itself; speed and ping were not measured; allow local network access or untick |

The skill rule "never ask the user to disconnect a VPN" stands: the bypass makes disconnecting unnecessary,
and the `blocked` sentence offers the VPN's local-network setting or unticking the probe, never turning
the VPN off.

**Requirements added**

| # | Requirement | Where it lands |
|---|---|---|
| R13 | Per-band ping and download, opt-in default on, page checkbox and `--no-speed` | plan 2026-09-16-speed-probe, Tasks 3-6 |
| R14 | Probe traffic bypasses any VPN on this computer, DNS included, and the outcome is verified and stated | Tasks 2-3 |
| R15 | Speed and ping are shown in both front ends in the same place and never influence the ranking | Tasks 5-6, parity test |
| R16 | The data cost is stated next to the checkbox (up to 50 MB per band) | Task 1 |

**Costs named.** About 10 to 12 seconds more per band; up to 50 MB per band, so a full scan of every band can
use up to about 1.4 GB on a fast link; slow links use far less because the window closes at five
seconds. The probe host is `speed.cloudflare.com` (its `/__down` and
`/cdn-cgi/trace` endpoints); it measures the path to that host at that moment, which is the point.
