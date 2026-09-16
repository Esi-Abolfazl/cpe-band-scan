# cpe-band-scan — agent contract

A local tool that finds and locks the steadiest LTE/NR band on a Huawei CPE router. Python 3.14
stdlib server + vanilla JS page + a terminal front end, one runtime dependency (`huawei-lte-api`),
single repo. Gates, routing, Always / Ask-first / Never for anyone — human or agent — changing code
here.

Framework: llm-friendly-framework `0.2.0`. Root `CLAUDE.md` holds only `@AGENTS.md` and imports this
file; edit `AGENTS.md` only (`agents-link` check).

**Nearest card wins.** Before editing a file, read every `AGENTS.md` from the repo root down to the
file's directory. There are no scope cards yet; this file is the whole contract.

## Routing table — need → file

| Need | Read |
| --- | --- |
| Domain vocabulary | `CONTEXT.md` |
| What exists, request path, "don't have yet" | `ARCHITECTURE.md` |
| Principles that override every rule file | `docs/CONSTITUTION.md` |
| Slice shape, module boundaries, contracts door | `docs/conventions/vertical-slices.md` |
| Naming, comments, barrels, generated output — any change | `docs/conventions/llm-friendly.md` |
| Errors, wire keys, messages | `docs/conventions/errors.md` |
| Tests | `docs/conventions/testing.md` |
| Commits, branches, PRs | `docs/conventions/version-control.md` |
| Which doc owns which fact, Definition of Done | `docs/conventions/documents.md` |
| Python-specific rules, the reference slice | `docs/conventions/python.md` |
| Invariants a compiler can't check | `docs/adr/` |
| Where the repo stands against the rules, what is exempt and why | `docs/adoption-scorecard.md` |
| Handoffs, plans, parallel sessions | `## Agent sessions` below |

With the `llmfw` Claude Code plugin installed, each row is also a skill (`llmfw:<name>`) that loads
on demand; the table stays for other agents.

## Gates

Run in full before claiming done. Every one also runs in CI on the same command.

```
.venv/bin/python -m pytest -q
node scripts/check-repo.mjs
.venv/bin/python scripts/check_baseline.py
```

The venv is `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`; the interpreter is pinned
in `.python-version`, Node (the `check-repo` runner only) in `.nvmrc`.

## Baseline

Adopted on 2026-09-16 with these rules violated; counts in `gates-baseline.json`, rows in
`docs/adoption-scorecard.md`. **New code follows the rule; existing violations burn down per the
scorecard.** A gate at baseline may not gain a new hit: `scripts/check_baseline.py` fails the PR
that adds one. When a count reaches zero, remove its exemption from `llmfw.config.json` in the same
change.

| Rule | Count | Where |
| --- | --- | --- |
| `tst-04`, `llm-01` literal routes | 71 in tests, 16 in the page | `tests/test_server*.py`, `tests/test_end_to_end.py`, `web/app.js` |
| `llm-06` files over 300 lines | 3 | `server.py`, `web/app.js`, `tests/test_scanner.py` |
| `llm-12` env reads outside one module | 4 | `store.py`, `cli.py` |
| `err-06` swallowed failures | 3 | `metrics.py:106`, `speed.py:95`, `speed.py:129` |
| `llm-03` barrel | 1 | `src/cpe_band_scan/__init__.py` |
| `vc-09` machine paths | 2 files | `docs/superpowers/plans/` |

## Always

- Load `docs/CONSTITUTION.md` plus the routed rule files before touching code.
- A new use case copies `src/cpe_band_scan/device.py` (`py-01`); its test is `tests/test_<module>.py`.
- Every user-facing word goes through `copy.py` (`py-03`); every failure is a `RouterError(code)`
  with a catalogue line (`py-02`).
- A term new to the product lands in `CONTEXT.md` in the same change (`llm-09`).
- Out-of-scope bug or debt found mid-task → a handoff file (`## Agent sessions`), never an inline
  fix and never a native task proposal.
- Assume parallel agent sessions: the server already walks ports `8765..8774`
  (`server.py:341`); tests use `port=0`.

## Ask first

- A new dependency, including a dev tool (`con-10`). `ruff` is proposed in
  `.agents/handoffs/2026-09-16-ruff-lint-format-gate.md` and not yet approved.
- A new top-level module in `src/cpe_band_scan/` or a new contracts door (`vs-03`, `vs-04`).
- A new ADR.
- Renaming a `RouterError` code, an `/api/*` route or a copy key — all three are wire contracts
  between server, page and terminal (`py-02`, `tst-04`).
- Rewriting already-pushed history (`vc-03`).
- Anything that writes to the router outside `lockfreq.lock` and `Router.post`.

## Never

- Edit generated output by hand (`llm-08`) — there is none yet; a codegen adds `generatedPaths`
  to `llmfw.config.json` first.
- Barrels, grab-bag files, reflection scans (`llm-02`, `llm-03`, `llm-04`).
- A new literal route string in a test (`tst-04`) — the baseline count may only fall.
- Read config/env outside `store.py`/`cli.py` today, outside `config.py` once it exists (`llm-12`).
- Swallow a failure (`err-06`).
- Put the router password on a command line, in a log line or in a test fixture committed to git.
- Push `main` directly from an agent session (`vc-08`).
- Commit a machine-specific path (`vc-09`).
- A test that touches the real `~/.cpe-band-scan` (`py-04`) or patches an app module to test its
  sibling (`py-05`).

## Agent sessions

**Handoffs replace native task proposals.** Out-of-scope work → `.agents/handoffs/YYYY-MM-DD-<slug>.md`
from `.agents/handoffs/_TEMPLATE.md`, `status: open|planned|done`. Self-contained: Context ·
Problem (`file:line` evidence) · Contract · Acceptance (each criterion a command with checkable
output). Mention every handoff created in the final response.

**Parallel sessions.** Other sessions run in their own worktrees. Never assume a port is free. An
edit to a gitignored file inside a worktree is lost when the worktree is removed — make such edits
in the main checkout. Personal instructions go in a gitignored `CLAUDE.local.md`, never a committed
file. The `.venv` lives only in the main checkout; a worktree makes its own.

## Versions that differ from training data

- `huawei-lte-api >= 1.7` — `Connection` is a context manager and `post_set` returns `"OK"`;
  see `src/cpe_band_scan/router.py:53-84` and `tests/fakes.py:1`.
- Python 3.14 — `tomllib` is stdlib (`tests/test_packaging.py:2`); no `tomli`.

## ADRs

None yet. The trigger test is in `docs/conventions/README.md`.

---

When a doc contradicts the code, the code is truth — fix the doc.
