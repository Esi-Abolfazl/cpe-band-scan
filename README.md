# CPE Band Scan

Find the mobile band that gives you the steadiest connection, and lock your Huawei router to it.

It talks to the router's own admin page over your local network. Nothing is flashed. One click puts
the router back on automatic.

## Install

Not on PyPI yet, so it installs from this folder. You need Python 3.10 or newer.

Two files in this folder are named for you: double-click **Run on Mac** or **Run on Windows**.
The first run builds a private Python environment next to the app, which takes about a minute.
After that it opens straight away.

From a terminal in this folder instead:

```bash
pipx install .
```

No pipx? `python3 -m pip install --user .` does the same. Both give you two commands,
`cpe-band-scan` and its short alias `cpescan`.

## Open the page

```bash
cpe-band-scan ui
```

Your browser opens on the app. If you want a different port or no browser window, say so:

```bash
cpe-band-scan ui --port 9000 --no-browser
```

### Connect

Two fields:

- **Router address**: `192.168.8.1` for most Huawei routers, `192.168.1.1` for some. The app
  remembers the one that worked.
- **Admin password**: the router's admin page password, not the Wi-Fi password. By default it stays
  in memory while the app runs and is never written anywhere. Tick **Remember the password on this
  computer** and you won't type it next time: it goes into the app's settings file, readable by
  your user account only. **Forget the password** on the connect screen removes it again.

Connecting reads the router's model and firmware and checks it can lock bands. Nothing on the
router changes.

### Read your connection

The top card shows what the router is doing right now, one row per network.

- **4G**: each carrier as a chip, like `B7 20 MHz`, the anchor first. Under them, Quality (SINR),
  Channel (RSRQ) and Strength (RSRP), each with its unit.
- **5G**: the 5G carrier and its Quality and Strength.

Next to it, **Band lock** says in words what is locked, for example "Locked to B3 with B1 as
secondary carriers", or that the router is choosing by itself. **Refresh** reads the router again.
**Switch back to automatic** removes every lock.

Hover any underlined word on the page to read what it means.

### Scan

Pick what to scan, then press **Start the scan**.

| Choice | What it measures | Takes about |
|---|---|---|
| All bands | every 4G band, then every 5G band | 20 to 30 min |
| 4G bands only | the 4G bands. On a 5G NSA network this is the scan that matters, because the 5G carrier follows the 4G band the router is anchored to | 10 to 15 min |
| 5G bands only | which 5G bands are on air here | 5 to 10 min |

The scan locks each band in turn, waits for the router to re-attach, measures for about a minute,
then moves on. Your connection drops for about half a minute at every change. You can keep working
between the drops.

**Measure speed and ping on each band** is ticked by default. After the radio samples of each band the
app pings the internet five times and downloads for five seconds through the router, from this computer,
and adds two columns to the results. It costs about 10 seconds and up to 50 MB per band, so a full
scan of every band can use up to about 1.4 GB on a fast link; slow links use far less because the
window closes at five seconds. Untick it on a metered plan you are close to using up.

While it runs you see both networks at once: a bar and a time left for each, so "4G: 2 of 8, about
6 min left" sits next to "5G: waiting" and you know what is coming. The 4G and 5G logs sit side by
side. Each follows its newest line until you scroll up to read; tick **Follow** to catch up again.
When a side finishes its bar becomes a green check and its log stands still.

**Stop the scan** stops after the band being measured and puts back the lock you arrived with.
Everything measured so far is kept.

### Read the results

One table per network, best first. Columns:

| Column | Meaning |
|---|---|
| # | rank, by rating first, then by the lowest quality. The auto row is the router's own choice, measured the same way, and competes like any band |
| Band | the band that was locked. **Best** marks the top of the ranking |
| Rating | Excellent, Good, Fair, Poor, or No 5G |
| 5G | whether the 5G carrier stayed up on this band. Bands that lose it are never recommended |
| Speed | download in Mbit/s over five seconds, straight through the router. One moment's reading: cell load changes it hour to hour. Shown, never used to rank |
| Ping | time to reach the internet in ms, the middle of five tries. Under 50 feels instant, over 150 you notice |
| Lowest | the lowest SINR seen, in dB. This is what makes a call or a stream stutter. Above 0 is usable, above 5 is comfortable |
| Typical | the middle SINR reading, in dB |
| Channel | RSRQ in dB. Better than -12 is healthy |
| Strength | RSRP in dBm. Above -90 it barely affects speed |
| 5G quality | SINR of the 5G carrier, when one was connected |
| Carriers | the carriers the router combined on this band |

When the scan ends, the app locks the best band itself, with the other working bands as secondary
carriers so carrier aggregation survives. If automatic held up better than any single band, or no
band beat what you already had, it says so and changes nothing.

Speed and ping never move a band up or down the ranking. The rating is the radio; the two columns are
what that radio delivered at that moment. Under each table one sentence says what they mean: measured
past your VPN, measured through it, measured with no VPN active, or not measured because the VPN blocked
it.

To lock a different row, press its **Apply**. Apply on the auto row puts that side back on automatic. Every Apply button waits while the router takes the
lock, then the row the router actually reports shows **In use**. Best and In use are two different
marks: one is the measurement, the other is the fact.

### Test a band without scanning

When two bands score close, test them for longer. The form asks two things:

- **Band to test**: your connection as it is, or a 4G band and a 5G band picked from the results.
  A pick is locked for the length of the test and your own lock is put back afterwards, whatever
  happens. The line under the pickers tells you exactly what will be locked.
- **How long**: 1, 2, 5 or 10 minutes. Two minutes shows whether a band is steady. Ten is the one
  to trust before you settle on it.

**Start the test** samples every 10 seconds and ends with the lowest, typical and best quality it
saw. **Stop the test** ends it early and still puts your lock back.

### Lock profiles

Once the router holds a lock you like, give it a name and press **Save current lock**. One profile
per carrier or per place: "MCI, living room", "Irancell, office". Each row shows the carrier, the
bands in the lock and when it was saved. **Apply** puts that lock back on the router, and the row
the router really holds shows **In use**. **Rename** edits the name in the row. **Delete** asks for a
second press. Profiles live on this computer, so they follow you when you move the router or swap the SIM.

### Using a VPN

Keep it on. The signal numbers come from the router itself, so a VPN doesn't change them. Stay on one
server for the whole scan, because switching servers mid-run changes what you feel while the
measurements stay the same.

The speed and ping probe is different: measured through the VPN, every band would look like the VPN
server. So the probe goes around it. Each probe connection is pinned to the network interface that
reaches the router, and the probe host's address is looked up through the router too, because some
VPNs answer every name lookup with an address only the tunnel can route. Before the first band the app
checks that the address the internet sees through the router differs from the one it sees through the
VPN, and tells you which of these you are in:

- no VPN was active: the numbers are your plain connection;
- measured straight through the router, past your VPN: the numbers are the band's own;
- the VPN couldn't be bypassed: the numbers include it, so compare rows with each other only;
- the VPN blocks everything outside its tunnel: speed and ping weren't measured. Allow local network
  access in the VPN's settings, or scan with the speed test unticked.

If the app can't reach the router at all while the VPN is up, turn on your VPN's local network access
setting.

## From the terminal instead

Every command is `cpe-band-scan <command>`, or `cpescan <command>`.

```bash
cpe-band-scan status                 # model, firmware, carrier, lock and signal right now
cpe-band-scan scan                   # every band, 4G then 5G
cpe-band-scan scan 4g                # 4G bands only
cpe-band-scan scan 5g                # 5G bands only
cpe-band-scan scan 7 40              # only B7 and B40, each measured on its own
cpe-band-scan scan --save "Office"   # save the finished run under a name
cpe-band-scan scan --no-speed        # skip the per-band speed and ping probe
cpe-band-scan test                   # watch the current lock for 2 minutes
cpe-band-scan apply 7                # lock 4G to B7
cpe-band-scan apply 7 --scell 3,40   # lock to B7, keep B3 and B40 as secondary carriers
cpe-band-scan apply 7 --nr 78        # lock to B7 and lock 5G to N78 in the same call
cpe-band-scan clear                  # back to automatic on both sides
cpe-band-scan runs                   # saved results, newest first
cpe-band-scan show <id>              # reopen a saved run's table
cpe-band-scan help                   # this list
```

Bare band numbers in `scan` are 4G bands. The 5G side is scanned only when you ask for `5g`.

The password comes from, in this order: the `CPE_BAND_SCAN_PASSWORD` environment variable, a
`PASSWORD=` line in a `.env` file in the current folder, or a prompt. Never put it on the command
line.

Other settings: `--url` or `CPE_BAND_SCAN_URL` for the router address, `--user` or
`CPE_BAND_SCAN_USER` for an admin user other than `admin`, and `CPE_BAND_SCAN_HOME` to move the
folder the app stores things in.

## Which routers work

Huawei CPE routers on firmware 4: H155-381, H155-181, H153, H158 and relatives. The app checks the
firmware before it writes anything and tells you in words if it can't help. Older firmware uses a
different interface, which the app doesn't speak yet.

## What it stores

Lock profiles, terminal runs and the router address live in `~/.cpe-band-scan`. The password is
stored there only if you tick Remember, and only until you press Forget.

## Try it without a router

```bash
python tools/demo_server.py
```

Opens the page on port 8766 against a fake router with a short band list, so you can see a scan,
an apply and a test end to end in about a minute.

## Using it with an assistant

The repository ships a Claude Code skill in `skills/bandscan`. Point your assistant at it and it
finds your router, runs the scan in the background, relays progress, reads the table for you and
suggests which runner-up is worth a longer test. It drives this same app, so both routes do exactly
the same thing.

```bash
ln -s "$PWD/skills/bandscan" ~/.claude/skills/bandscan
```

## Known limits

- **Anyone who can run a program on this computer can reach the scan.** The page is served on
  127.0.0.1 and every request carries a token, but a program on the same machine can ask for the
  page and read that token out of it. Nothing else on your network can. If you share the computer
  with people you would not hand the router password to, run the scan only while they are logged
  out.
- **The scan interrupts your connection, repeatedly.** Each band takes about a minute and the
  connection drops at every change. A full scan is 20 to 30 minutes of patchy internet.
- **It reads 5G as your router reports it.** On a non-standalone network the 5G carrier follows
  the 4G one, so the app locks 5G only when two or more 5G bands answer.
- **A band lock survives a reboot.** If you forget you set one and the tower changes, the router
  keeps using a band that no longer suits it. Switch back to automatic when you move house or change
  provider.
- **The results table is the last finished scan.** After a test and a page reload it is gone until
  the next scan. Terminal scans are saved under `runs` and can be reopened with `show`.
- **The speed test costs data and reads one moment.** Up to 50 MB per band, so a full scan of every band can use
  up to about 1.4 GB on a fast link; slow links use far less because the window closes at five
  seconds. Cell load changes hour to hour. It is shown next to the rating and never decides it.
  Untick **Measure speed and ping on each band** on a plan you are close to using up.
- **A remembered password is a file.** It is readable only by your user account, but anyone who can
  sign in as you can read it. Use Forget the password when the computer is shared.
