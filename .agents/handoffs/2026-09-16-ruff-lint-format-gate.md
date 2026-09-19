---
status: open
area: tooling
date: 2026-09-16
origin: none — found during llmfw adoption Phase 1 (docs/adoption-scorecard.md)
---

# Handoff: add `ruff` as the lint and format gate — ask first

## Context

The framework's gate ladder (layers 2 and 3) wants a formatter and a linter in CI. The repo has
neither. `ruff` is one dev dependency that does both, but adding any dependency is ask-first
(`con-10`, `AGENTS.md` § Ask first), so Phase 1 stopped here.

## Problem

- No `ruff.toml`, `.editorconfig`, `setup.cfg` or `pyproject.toml [tool.ruff]` exists.
- Whitespace and import order are decided by hand in every change, and `err-06`-style smells
  (`except Exception: pass`) are caught only by the regex in `llmfw.config.json`.

## Contract

On a yes from the owner:

- `pyproject.toml`: `dev = ["pytest>=8", "ruff>=0.6"]` in the existing `[project.optional-dependencies]`, then `uv lock` — not `uv add --dev`, which opens a second bucket also called `dev` under `[dependency-groups]` that `uv sync --extra dev` does not install, plus `[tool.ruff]` with `line-length = 100`
  (the code's current width) and `select = ["E", "F", "B", "BLE"]` (`BLE001` is `err-06` at the
  linter layer). Start every rule the code violates today at `ignore`; list each in
  `docs/adoption-scorecard.md` with its count.
- `AGENTS.md` § Gates gains two lines, in this order, above pytest:
  `uv run ruff format --check .` and `uv run ruff check .`; `.github/workflows/ci.yml` runs
  the same two lines.
- `docs/conventions/python.md` § Gate mapping points `err-06` at `BLE001`.

## Acceptance

- [ ] `uv run ruff format --check .` → `N files already formatted`
- [ ] `uv run ruff check .` → `All checks passed!`
- [ ] `grep -c "ruff" AGENTS.md .github/workflows/ci.yml` → `2` on each line
- [ ] `uv run pytest -q` → `339 passed`
