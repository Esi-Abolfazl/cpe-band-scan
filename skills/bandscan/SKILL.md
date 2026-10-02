---
name: bandscan
description: Use when someone with a Huawei 4G/5G CPE router (H155-381, H155-181, H153, H158 and relatives on 4.x/10.x firmware) has an unstable or slow mobile connection and wants to find and lock the best LTE/NR band, compare bands at a new location or provider, or asks "which band is best", "lock band", "band lock", "5G keeps dropping", "/bandscan". Also when a generic Huawei band tool returned error -1 / 100002 / 100006 or switched 5G off.
argument-hint: "[scan [4g|5g] [bands...]] | status | test | apply <bands> [--scell <bands>] [--nr <bands>] | clear | runs | show <id> | ui | help"
---

# bandscan

Find the LTE anchor band (and NR band) that gives the cleanest link at this spot, then lock it. Everything goes through the router's own HTTP API, via the CPE Band Scan app; nothing is flashed. The one rule: **the router's firmware decides which endpoint is safe, never a library default.**

## Commands

`/bandscan $ARGUMENTS`, bare = `scan`. The app is `cpe-band-scan`. Show the table below to the user on `help` or when the arguments are unclear (`cpe-band-scan help` prints a shorter list without times).

| command | what it does | time | changes lock |
|---|---|---|---|
| `cpe-band-scan scan` | every supported LTE band, then every NR band; ranks by rating, then SINR floor, with 5G kept; the auto row competes; applies the winner with runner-ups as secondaries | 20-30 min | yes, many times |
| `cpe-band-scan scan 4g` / `scan 5g` | one side only | 10-15 min | yes |
| `cpe-band-scan scan 7 40` | only these 4G bands (bare numbers are always LTE), each still measured on its own (not multi-band anchor combos — `apply --scell` covers combos once you know the winner) | ~1 min per band | yes |
| `cpe-band-scan scan 5g 78 41` | only these 5G bands (`5g` before the numbers); one call scans one side, so B7 plus N78 takes two scans | ~1 min per band | yes |
| `cpe-band-scan scan --no-speed` | the same scan without the per-band speed and ping probe (on by default: five TCP pings and a 5 s download through the router after each band's radio samples, up to 50 MB per band) | saves ~10 s per band | yes |
| `cpe-band-scan status` | current lock, live signal line, visible bands | 5 s | no |
| `cpe-band-scan test` | 2-minute trace of the current lock, 10 s samples, ends with a summary (Lowest and Typical SINR, Channel, Strength, 5G, Carriers) | 2 min | no |
| `cpe-band-scan apply 7` | anchor only on B7; the NR side goes back to auto unless `--nr` is passed (apply always rewrites both sides) | ~30 s | yes |
| `cpe-band-scan apply 7 --scell 3,40` | anchor B7, B3 and B40 allowed as secondary carriers only | ~30 s | yes |
| `cpe-band-scan apply 7 --nr 78` | anchor B7, and lock the NR side to N78 in the same call (NR always rides the LTE anchor in NSA, so it is set alongside one, never on its own) | ~30 s | yes |
| `cpe-band-scan clear` | back to auto, both sides | ~30 s | yes |
| `cpe-band-scan runs` | list saved runs on this computer | 1 s | no |
| `cpe-band-scan show <id>` | reopen a saved run's table | 1 s | no |
| `cpe-band-scan ui` | opens a local web page with the same scan, the same ranked table and a 1-to-10-minute test of any band from the results | | no |
| `cpe-band-scan help` | a shorter command list | | |

## Steps

1. **VPN stays on.** It is part of their real connection: never ask the user to disconnect it, ask them to stay on one VPN server for the whole scan. The radio numbers come from the router's LAN API, so the VPN cannot touch them, and the app routes the speed and ping probe around it itself (mechanics: [reference.md](reference.md)). The first timestamped line (`Starting. …`) ends with the VPN verdict (none with `--no-speed`); relay it as printed. Each lock change drops the link for ~30 s and the VPN will reconnect each time; that is expected. If the router API is unreachable with the VPN up, ask them to enable the VPN's "allow LAN / local network access" option, not to disconnect.
2. **Locate the router.** Default gateway: `netstat -rn -f inet | grep '^default' | grep -v utun` (macOS; a VPN adds `utun` default lines, skip those), `ip route | grep default` (Linux), or `ipconfig` and read the Default Gateway line (Windows). Confirm the IP with the user. If the machine's own default route is this router, every lock change blips the connection for ~30 s: say so before the first write. A B525, B818, B535, H112 or H122 on 2.x/3.x firmware has no driver here and every command, `status` included, refuses: say so before setup. For any other model, `status` decides.
3. **Password stays out of the chat.** Ask the user to create `.env` in the folder they'll run commands from: `PASSWORD=<router admin password>`. Never accept it pasted in chat; if they paste it anyway, tell them to change it when done. Remind them again at the end. The router address defaults to `http://192.168.8.1/`. If theirs is different, put `--url` before the command (`cpe-band-scan --url 192.168.1.1 status`; after the command it is rejected), or export `CPE_BAND_SCAN_URL=192.168.1.1` for the session; that variable is not read from `.env`.
4. **Setup once:** `uv tool install <repo>`, where `<repo>` is the folder two levels above this file (this skill ships inside the repo, at `skills/bandscan/`; resolve the symlink if the skill was linked into `~/.claude/skills`). uv only, never pip, and never a bare `cpe-band-scan` — it is not on PyPI, so the name will not resolve. If the commands are not found afterwards, uv said where it put them: `uv tool update-shell`, then a new terminal. Every command below is `cpe-band-scan <command>`, run from the folder that holds `.env`; `cpescan` is a shorter alias for the same thing. Offer `cpe-band-scan ui` whenever the person would rather click than read a table in chat.
5. **Ask the router for the band-lock page before any write.** Device names are ambiguous (the same box ships with 3.x, 4.x and 10.x); the page decides, not the box and not the version number. Run `cpe-band-scan status`: its first line prints the model, firmware and carrier (e.g. `H155-381 · firmware 4.0.0.5 · MCI`), and it refuses with the reason in words if the page isn't there — a 2.x/3.x box, or a current firmware whose `net/lock-freq` doesn't answer. On refusal nothing is printed on stdout: relay the error sentence the app prints instead, word for word, and do not guess or fall back to another write path; see [reference.md](reference.md) for what unsupported firmware would need instead.
6. **Baseline:** from that same `status` output, record the band string (it must contain an `N` carrier, e.g. `N78`, if the user has 5G now) and the `lock` object: it is what goes back if a scan dies hard.
7. **Scan, in the background, with progress relayed.** The scan takes up to 30 minutes and the user must never wonder whether it is stuck:
   - Start it as a background command, teeing the app's own output to a file for tailing: `cpe-band-scan scan [4g|5g] [bands...] 2>&1 | tee /tmp/bandscan-$(date +%Y%m%d-%H%M).log`. The app saves the finished run itself (under `~/.cpe-band-scan/runs`); the tee is only so progress can be tailed while it's running.
   - Tell the user immediately: how many bands, the worst-case time, that the link blips per band, and that they can keep working.
   - Every ~2 minutes read the log tail and post one line: which band is being measured, what the last finished band scored, how many are left — the app already timestamps and phrases each line, so relay it rather than re-deriving it.
   - Stopping it (Ctrl-C, or stopping the background task) puts back the lock you had before the scan, which is automatic if there was none. If it dies hard (SIGKILL, power loss, the laptop sleeping), run `status` and put the recorded lock back with `apply`, or `clear` if there was none.
   - Never run two scans at once. Nothing enforces this across processes: the page refuses only its own second scan, and a CLI scan is never refused. Before starting, ask whether the page (`cpe-band-scan ui`) is open and scanning or testing, and check `pgrep -fl cpe-band-scan` (Windows: `tasklist | findstr cpe-band-scan`).
8. **Read the result table.** The app prints a markdown table per side (band, rating, 5G kept, speed in Mbit/s and ping in ms when the probe ran, lowest/typical SINR, RSRQ, RSRP, 5G quality, carriers) and, under it, the one-sentence VPN verdict for the speed columns and saves the run. Relay the table to the user as-is. Stability comes from the anchor's SINR **floor** and RSRQ; the Rating column already folds both in (the cutoffs live in `metrics.GRADES`), so explain a band by its Rating, not a remembered number. RSRP above -90 dBm hardly matters. Any band that lost the `N` carrier is out. On NSA the NR side follows the LTE anchor; the app still scans NR so the user sees which NR bands are on air, and applies an NR lock only if two or more are live. Speed and ping are shown, never ranked: cell load changes hour to hour. Read them as 'what this band delivered at that moment'; when two bands tie on rating, the faster one is the one to `test` for longer, and say so.
9. **The app applies the winner itself** (anchor = top-ranked band, other ranked bands as secondaries; if the auto row ranks first it leaves that side on automatic). Confirm with `cpe-band-scan status` that the `N` carrier is still there. Then offer, do not assume: "want me to `test` this lock and the runner-up (2 minutes each) for a firmer pick?" If yes, from the terminal: read the NR anchors from `status` (the first list in `lock.nr`); if there are any, pass them as `--nr <bands>` on both applies below, or `apply` puts NR back to auto. Then `cpe-band-scan test`, `cpe-band-scan apply <runner-up> --scell <others>`, `cpe-band-scan test` again, compare the two summaries' Lowest (SINR floor) lines, re-apply the better one. On the page this is one form: pick the runner-up 4G and 5G bands from the results and a length (1, 2, 5 or 10 min); it locks them for the test and puts the applied lock back by itself, so nothing needs re-applying unless the runner-up wins — then its row's **Apply** does that, and the row the router really holds shows **In use**. Report before/after signal lines; `cpe-band-scan runs` / `show <id>` reopens either run later.
10. **Save the winner as a profile.** On the page, **Save current lock** stores the lock under a name (carrier and place); later, **Apply** on that row puts it back in one click, which is the answer when the person moves between places or swaps SIMs: one profile each, no re-scan. The page can also remember the admin password (opt-in, owner-readable file, **Forget the password** removes it); mention it only if they ask about typing it every time.
11. **Close:** remind the user to change the router password, and that the lock survives reboots (`cpe-band-scan clear` to undo, re-scan after moving or changing SIM/provider).

## Common mistakes

| Mistake | Fix |
|---|---|
| Using `huawei-lte-api`'s `set_net_mode` / any tool that writes `LTEBand` to `api/net/net-mode` on firmware 4.x | Rejected with `-1` yet `NetworkMode` is applied: this switches 5G off silently. Use `api/net/lock-freq` via `cpe-band-scan`. If it already happened, set network mode back to Auto in the router UI. |
| Trusting the neighbour-cell list as the band inventory | It only lists cells near the current anchor. The default scan covers every supported band for that reason. |
| Judging by peak or by one 25 s window | Noise is ±5 dB; a band can swing -4 to 18 dB. Rank by rating then floor, confirm close calls with `test`. |
| Password in the URL (`http://admin:p@ss@ip/`) or on the command line | Symbols break URL parsing, and argv lands in shell history. `.env`, `CPE_BAND_SCAN_PASSWORD`, or the prompt only. |
