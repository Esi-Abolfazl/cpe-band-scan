---
name: bandscan
description: Use when someone with a Huawei 4G/5G CPE router (H155-381, H155-181, H122, H112, B818, B525 and similar) has an unstable or slow mobile connection and wants to find and lock the best LTE/NR band, compare bands at a new location or provider, or asks "which band is best", "lock band", "band lock", "5G keeps dropping", "/bandscan". Also when a generic Huawei band tool returned error -1 / 100002 / 100006 or switched 5G off.
argument-hint: "[scan [4g|5g] [bands...]] | status | test | apply <bands> [--scell <bands>] [--nr <bands>] | clear | runs | show <id> | ui | help"
---

# bandscan

Find the LTE anchor band (and NR band) that gives the cleanest link at this spot, then lock it. Everything goes through the router's own HTTP API, via the CPE Band Scan app; nothing is flashed. The one rule: **the router's firmware decides which endpoint is safe, never a library default.**

## Commands

`/bandscan $ARGUMENTS`, bare = `scan`. The app is `cpe-band-scan`; `cpe-band-scan help` prints this table, show it to the user on `help` or when the arguments are unclear.

| command | what it does | time | changes lock |
|---|---|---|---|
| `cpe-band-scan scan` | every supported LTE band, then every NR band; ranks by rating, then SINR floor, with 5G kept; the auto row competes; applies the winner with runner-ups as secondaries | 20-30 min | yes, many times |
| `cpe-band-scan scan 4g` / `scan 5g` | one side only | 10-15 min | yes |
| `cpe-band-scan scan 7 40` | only the listed bands, each still measured on its own (not multi-band anchor combos — `apply --scell` covers combos once you know the winner) | ~1 min per band | yes |
| `cpe-band-scan scan --no-speed` | the same scan without the per-band speed and ping probe (on by default: five TCP pings and a 5 s download through the router after each band's radio samples, up to 50 MB per band) | saves ~10 s per band | yes |
| `cpe-band-scan status` | current lock, live signal line, visible bands | 5 s | no |
| `cpe-band-scan test` | 2-minute trace of the current lock, 10 s samples, ends with floor/median/peak table | 2 min | no |
| `cpe-band-scan apply 7` | anchor only on B7 | ~30 s | yes |
| `cpe-band-scan apply 7 --scell 3,40` | anchor B7, B3 and B40 allowed as secondary carriers only | ~30 s | yes |
| `cpe-band-scan apply 7 --nr 78` | anchor B7, and lock the NR side to N78 in the same call (NR always rides the LTE anchor in NSA, so it is set alongside one, never on its own) | ~30 s | yes |
| `cpe-band-scan clear` | back to auto, both sides | ~30 s | yes |
| `cpe-band-scan runs` | list saved runs on this computer | 1 s | no |
| `cpe-band-scan show <id>` | reopen a saved run's table | 1 s | no |
| `cpe-band-scan ui` | opens a local web page with the same scan, the same ranked table and a 1-to-10-minute test of any band from the results | | no |
| `cpe-band-scan help` | the table | | |

## Steps

1. **VPN stays on.** Many users run a VPN at all times and it is part of their real connection quality. Never ask them to disconnect it. The radio numbers come from the router's LAN API, so the VPN cannot touch them. The speed and ping probe would be poisoned by a VPN, so the app routes around it itself: probe sockets are pinned to the interface that reaches the router and the probe host is resolved through the router, not the system resolver (some VPNs hand out fake 198.18.x.x addresses for every name). The scan's first log line says which case applies: no VPN, bypassed and proven, not bypassed (numbers include the VPN; compare rows with each other only), or blocked (the VPN allows nothing outside its tunnel; ask them to allow local network access in the VPN, or run `scan --no-speed`). Each lock change drops the link for ~30 s and the VPN will reconnect each time; that is expected. If the router API is unreachable with the VPN up, ask them to enable the VPN's "allow LAN / local network access" option, not to disconnect.
2. **Locate the router.** Default gateway: `netstat -rn | grep '^default'` (macOS/BSD) or `ip route`. Confirm the IP with the user. If the machine's own default route is this router, every lock change blips the connection for ~30 s: say so before the first write.
3. **Password stays out of the chat.** Ask the user to create `.env` in the folder they'll run commands from: `PASSWORD=<router admin password>`. Never accept it pasted in chat; if they paste it anyway, tell them to change it when done. Remind them again at the end. The router address defaults to `http://192.168.8.1/`; pass `--url <address>` (e.g. `--url 192.168.1.1`) if theirs is different.
4. **Setup once:** `pipx install cpe-band-scan` (or `pip install --user cpe-band-scan`). Every command below is `cpe-band-scan <command>`, run from the folder that holds `.env`; `cpescan` is a shorter alias for the same thing. The app also has a GUI: `cpe-band-scan ui` opens a local page with the same scan, the same ranked table and a 1-to-10-minute test of any band from the results. It shows the connection per network (4G carriers with width, then 5G), both sides' progress with their own time left, and the 4G and 5G logs side by side. Offer it whenever the person would rather click than read a table in chat.
5. **Identify the firmware before any write.** Device names are ambiguous (the same box ships with 3.x and 4.x); the router decides, not the box. Run `cpe-band-scan status`: its first line prints the model, firmware and carrier (e.g. `H155-381 · firmware 4.0.0.5 · MCI`), and it refuses with the reason in words if the device isn't supported — firmware below 4.x, or firmware 4.x without the band-lock page. On refusal, show the user that line, do not guess or fall back to another write path; see [reference.md](reference.md) for what unsupported firmware would need instead.
6. **Baseline:** `cpe-band-scan status`. Record the band string; it must contain an `N` carrier (e.g. `N78`) if the user has 5G now.
7. **Scan, in the background, with progress relayed.** The scan takes up to 30 minutes and the user must never wonder whether it is stuck:
   - Start it as a background command, teeing the app's own output to a file for tailing: `cpe-band-scan scan [4g|5g|bands...] 2>&1 | tee /tmp/bandscan-$(date +%Y%m%d-%H%M).log`. The app saves the finished run itself (under `~/.cpe-band-scan/runs`); the tee is only so progress can be tailed while it's running.
   - Tell the user immediately: how many bands, the worst-case time, that the link blips per band, and that they can keep working.
   - Every ~2 minutes read the log tail and post one line: which band is being measured, what the last finished band scored, how many are left — the app already timestamps and phrases each line, so relay it rather than re-deriving it.
   - The app restores auto on a crash or Ctrl-C. Never run two scans at once (a second one is refused with "a scan is already running").
8. **Read the result table.** The app prints a markdown table per side (band, rating, 5G kept, speed in Mbit/s and ping in ms when the probe ran, lowest/typical SINR, RSRQ, RSRP, 5G quality, carriers) and, under it, the one-sentence VPN verdict for the speed columns and saves the run. Relay the table to the user as-is. Stability comes from the anchor's SINR **floor** (want > 0 dB) and RSRQ (better than -12 dB); RSRP above -90 dBm hardly matters. Any band that lost the `N` carrier is out. On NSA the NR side follows the LTE anchor; the app still scans NR so the user sees which NR bands are on air, and applies an NR lock only if two or more are live. Speed and ping are shown, never ranked: cell load changes hour to hour. Read them as 'what this band delivered at that moment'; when two bands tie on rating, the faster one is the one to `test` for longer, and say so.
9. **The app applies the winner itself** (anchor = top-ranked band, other ranked bands as secondaries; if the auto row ranks first it leaves that side on automatic). Confirm with `cpe-band-scan status` that the `N` carrier is still there. Then offer, do not assume: "want me to `test` this lock and the runner-up (2 minutes each) for a firmer pick?" If yes, from the terminal: `cpe-band-scan test`, `cpe-band-scan apply <runner-up> --scell <others>`, `cpe-band-scan test` again, compare floors, re-apply the better one. On the page this is one form: pick the runner-up 4G and 5G bands from the results and a length (1, 2, 5 or 10 min); it locks them for the test and puts the applied lock back by itself, so nothing needs re-applying unless the runner-up wins — then its row's **Apply** does that, and the row the router really holds shows **In use**. Report before/after signal lines; `cpe-band-scan runs` / `show <id>` reopens either run later.
10. **Save the winner as a profile.** On the page, **Save current lock** stores the lock under a name (carrier and place); later, **Apply** on that row puts it back in one click, which is the answer when the person moves between places or swaps SIMs: one profile each, no re-scan. The page can also remember the admin password (opt-in, owner-readable file, **Forget the password** removes it); mention it only if they ask about typing it every time.
11. **Close:** remind the user to change the router password, and that the lock survives reboots (`cpe-band-scan clear` to undo, re-scan after moving or changing SIM/provider).

## Common mistakes

| Mistake | Fix |
|---|---|
| Using `huawei-lte-api`'s `set_net_mode` / any tool that writes `LTEBand` to `api/net/net-mode` on firmware 4.x | Rejected with `-1` yet `NetworkMode` is applied: this switches 5G off silently. Use `api/net/lock-freq` via `cpe-band-scan`. If it already happened, set network mode back to Auto in the router UI. |
| Running the scan in the foreground and going quiet for 20-30 minutes | Background + a progress line every ~2 minutes from the log tail. |
| Trusting the neighbour-cell list as the band inventory | It only lists cells near the current anchor. The default scan covers every supported band for that reason. |
| Judging by peak or by one 25 s window | Noise is ±5 dB; a band can swing -4 to 18 dB. Rank by rating then floor, confirm close calls with `test`. |
| Locking a single band and losing carrier aggregation | `--scell` keeps other bands as secondaries; the scan applies runner-ups that way automatically. |
| Ranking or recommending by the Speed column alone | It is one five-second reading under that hour's cell load. Rating first, then floor; use speed to break a tie between equally rated bands, and confirm with `test`. |
| Password in the URL (`http://admin:p@ss@ip/`) or on the command line | Symbols break URL parsing, and argv lands in shell history. `.env`, `CPE_BAND_SCAN_PASSWORD`, or the prompt only. |
| Asking the user to turn off their VPN "for a clean test" | Never. The VPN is part of their connection. Ask for one stable VPN server during the test; enable LAN access if the router API is blocked. |
