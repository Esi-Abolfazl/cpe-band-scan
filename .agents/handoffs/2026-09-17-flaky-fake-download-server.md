---
status: open
area: tests
date: 2026-09-17
origin: none — found during the baseline burn-down (chore/burn-down-baseline)
---

# Handoff: the fake download server in `tests/test_speed.py` races the client that hangs up

## Context

`tst-10`: a flaky test is a bug. The full suite passes, but about one run in three prints a
traceback to stderr from the test's own fake HTTP server. It is noise today; it hides the next
real traceback tomorrow.

## Problem

- `tests/test_speed.py:74` — the fake's `do_GET` keeps writing the download body after the
  client under test has closed its socket at the five-second mark.
- Verbatim, from `.venv/bin/python -m pytest -q -s`:

```
Exception occurred during processing of request from ('127.0.0.1', 50626)
  File ".../tests/test_speed.py", line 74, in do_GET
    self.wfile.write(body)
BrokenPipeError: [Errno 32] Broken pipe
```

## Contract

- The fake's `do_GET` treats `BrokenPipeError` / `ConnectionResetError` as the client's normal
  end of a timed download and returns (a `# boundary:` comment on the `except` line, `err-06`),
  or writes only as many bytes as the test needs and stops.
- No `retries`, no rerun: the fix is in the fake, not in pytest flags.

## Acceptance

- [ ] `for i in 1 2 3 4 5; do .venv/bin/python -m pytest -q -s tests/test_speed.py 2>&1 | grep -c "Exception occurred"; done` → five lines of `0`
- [ ] `.venv/bin/python -m pytest -q tests/test_speed.py` → all passed
