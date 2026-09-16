---
status: open # open -> planned -> done
area: <module | package | docs | tooling>
date: YYYY-MM-DD
origin: <plan path, or "none — found during <task>">
---

# Handoff: <one-line title>

<!--
A handoff is a PLANNING artifact for out-of-scope work found mid-task (con-19). It replaces native
task proposals and "want me to also…?" offers. Self-contained: a fresh session with no memory of
yours must be able to execute it. Short bullets, payload examples in fenced blocks. Delete this.
-->

## Context

<What task surfaced this, and why it was out of scope there. Reference the origin plan path — do
not restate its content.>

## Problem

<What is wrong or missing. Evidence as `file:line` pointers, error text verbatim, failing command +
its output. A claim without a pointer is a hint, not a finding.>

## Contract

<Expected behavior / fix shape the origin side depends on. Endpoints, DTOs, error keys, rule IDs —
verbatim, with before/after examples if a contract changes. If the fix lives in another repo, name
the repo and the consuming version.>

## Acceptance

<Each criterion is a command with checkable output — never "works correctly".>

- [ ] `<command>` → `<expected output>`
- [ ] `<command>` → `<expected output>`
