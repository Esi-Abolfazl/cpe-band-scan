---
status: open # open -> planned -> done
area: scanner, api, cli, server
date: 2026-10-02
origin: none — found during the bandscan skill review (skills/bandscan/SKILL.md step 7)
---

# Handoff: one router lock across processes, not only inside one `ui` server

## Context

The skill promised that a second scan "is refused with 'a scan is already running'". That holds
only inside one `ui` process, so the skill now says nothing enforces it across processes and asks
the agent to check by hand. This handoff retires that manual check.

## Problem

- The only guard is `Session.require_idle` (`src/cpe_band_scan/server.py:84-86`), an in-process
  `self.thread.is_alive()` check.
- The CLI `scan` path (`src/cpe_band_scan/cli.py`, `command == "scan"`) calls `scanner.scan`
  with no guard; `scanner.scan` (`src/cpe_band_scan/scanner.py:134`) takes no lock.
- `serve()` walks to the next free port (`server.py:233-240`), so a second `ui` process gets its
  own `Session` and is not guarded either.
- Effect: two scans (CLI + CLI, CLI + page) both write `net/lock-freq`. The second reads the
  first one's test band as `original` (`scanner.py:136`) and puts it back when it finishes, so
  both measurements are corrupt and the router can be left on the wrong lock. A one-shot
  `apply` / `clear` / `test` / profile Apply from another process can also write mid-scan.

## Contract

- One OS-released lock file at `config.home() / "router.lock"`: `fcntl.flock(LOCK_EX | LOCK_NB)`
  on POSIX, `msvcrt.locking(LK_NBLCK)` on Windows. Not `O_EXCL`: a crash or `kill -9` must not
  leave a stale lock.
- Held for the whole of `scanner.scan` and `scanner.trace`.
- Taken non-blocking around every one-shot `lockfreq.lock` writer (CLI `apply` / `clear` /
  `test`, api apply / clear / profile apply); a held lock raises `RouterError("busy")`.
- Re-entrancy: a scan's own `lockfreq.lock` calls run while it holds the lock (flock is per open
  file description, so a second open + flock in the same process conflicts) — design for that.
- `Session.require_idle` shrinks to the in-process start race only.
- Then restore the skill's claim in `skills/bandscan/SKILL.md` step 7.

## Acceptance

- [ ] `uv run pytest -q -k busy` → a test where a second process starting a scan while the first
      holds the lock exits 1 with `copy.ERRORS["busy"]` on stderr, passing.
- [ ] `uv run pytest -q` → all pass.
- [ ] `grep -n "Nothing enforces this across processes" skills/bandscan/SKILL.md` → no match.
