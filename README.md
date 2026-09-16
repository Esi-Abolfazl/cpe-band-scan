# CPE Band Scan

Find the mobile band that gives you the steadiest connection, and lock your Huawei router to it.

CPE Band Scan talks to the router's own web interface over your local network. Nothing is flashed, and
one click puts the router back on automatic.

## Install

CPE Band Scan isn't on PyPI yet, so it installs from this folder. You need Python 3.10 or newer.

**Double-click** `run-cpe-band-scan.command` (macOS) or `run-cpe-band-scan.bat` (Windows). The
first run builds a private Python environment next to the app, which takes about a minute; after
that it opens straight away.

Or, from a terminal in this folder:

```bash
pipx install .
```

No pipx? `python3 -m pip install --user .` works too.

## Use it

```bash
cpe-band-scan ui
```

Your browser opens on the app. Enter:

- **Router address** — `192.168.8.1` for most Huawei routers. Some use `192.168.1.1`. CPE Band Scan
  remembers whichever one works.
- **Admin password** — the password for the router's admin page, not the Wi-Fi password.

Then press **Scan all bands** and leave it running. It measures each band for about a minute and
ranks them, then locks the best one. Expect 20 to 30 minutes, and a drop of about half a minute
each time a band changes.

When two bands score close, **Start the test** watches a band for 1 to 10 minutes: your connection
as it is, or a 4G and a 5G pick from the results, locked for the test and put back afterwards. That
compares their worst moments rather than their best.

Save a run under a name and it stays on this computer, ready to compare with the next place or the
next provider.

### Using a VPN

Keep it on. CPE Band Scan reads the numbers from the router itself, so a VPN doesn't change them. Stay
on one server for the whole scan, and if CPE Band Scan can't reach the router while the VPN is up,
switch on your VPN's local network access setting.

## From the terminal instead

```bash
cpe-band-scan status              # what you're connected to right now
cpe-band-scan scan                # every band, both 4G and 5G
cpe-band-scan scan 4g             # 4G only
cpe-band-scan test                # watch the current band for 2 minutes
cpe-band-scan apply 7 --scell 3   # lock to B7, keep B3 as a secondary carrier
cpe-band-scan clear               # back to automatic
cpe-band-scan runs                # saved results
```

The password comes from `CPE_BAND_SCAN_PASSWORD`, a `PASSWORD=` line in a `.env` file in the current
folder, or a prompt. The router address comes from `--url`.

## Which routers work

Huawei CPE routers on firmware 4 (H155-381, H155-181, H153, H158 and relatives). CPE Band Scan checks
the firmware before it writes anything and tells you if it can't help. Older firmware uses a
different interface, which CPE Band Scan doesn't speak yet.

## What it stores

Saved runs and the router address live in `~/.cpe-band-scan`. The password never leaves memory.

## Using it with an assistant

This repository also ships a Claude Code skill in `skills/bandscan`. Point your assistant at it and
it will find your router, run the scan, read the table for you and suggest which runner-up is worth
a two-minute test. It drives this same app, so both routes do exactly the same thing.

```bash
ln -s "$PWD/skills/bandscan" ~/.claude/skills/bandscan
```

## Known limits

- **Anyone who can run a program on this computer can reach the scan.** The page is served on
  127.0.0.1 and every request carries a token, but a program on the same machine can ask for the
  page and read that token out of it. Nothing on your network can. If you share the computer with
  people you would not hand the router password to, run the scan only while they are logged out.
- **The scan interrupts your connection, repeatedly.** Each band takes about a minute and the
  connection drops at every change. A full scan is twenty to thirty minutes of unusable internet.
- **It only reads 5G as your router reports it.** On a non-standalone network the 5G carrier
  follows the 4G one, so CPE Band Scan locks 5G only when two or more 5G bands answer.
- **A band lock survives a reboot.** If you forget you set one and the tower changes, your router
  will keep using a band that no longer suits it. Switch back to automatic when you move house or
  change provider.
