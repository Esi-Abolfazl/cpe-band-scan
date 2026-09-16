---
status: open
area: docs
date: 2026-09-16
origin: none — found during llmfw adoption Phase 0 (docs/adoption-scorecard.md, vc-09 and doc-01 rows)
---

# Handoff: plans move to `.agents/plans/` and lose their machine paths

## Context

`doc-01` gives plans one home, `.agents/plans/`; `vc-09` forbids committed home-directory paths.
`docs/superpowers/` predates adoption and holds both. Phase 4 work; exempted under `vc-09` in
`llmfw.config.json` until then.

## Problem

- `docs/superpowers/plans/2026-09-16-cpe-band-scan.md:62` and ~35 more lines — every command
  starts with `cd <the author's absolute home checkout path> && …`
- `docs/superpowers/plans/2026-09-16-review-fixes.md:24` — the same absolute path in prose.
- `docs/superpowers/specs/2026-09-16-cpe-band-scan-spec.md` and `docs/design/2026-09-16-page-redesign.md`
  are history, not current truth: the spec's password rule and the design's layout are now
  in `README.md` and the code.

## Contract

- `git mv docs/superpowers/plans/*.md .agents/plans/` with frontmatter
  `status: done` per `workflow/plans.md`; replace every absolute path with a repo-relative
  command (`cd "$(git rev-parse --show-toplevel)"` or nothing).
- The spec and the design doc: either delete (`con-08`, version control remembers) or move to
  `docs/design/` as history with a first line saying which `README.md` section supersedes them.
- Remove `docs/superpowers/**` from the `vc-09` exemption; delete the `.superpowers/` line from
  `.gitignore` if the folder is gone.
- Fix every link that pointed at the moved files (`doc-03`); `check-repo md-links` proves it.

## Acceptance

- [ ] `node scripts/check-repo.mjs --only forbidden-patterns` → `check-repo: ok` after the `docs/superpowers/**` exemption is gone (the `vc-09` regex is the one grep)
- [ ] `ls docs/superpowers` → `No such file or directory`
- [ ] `node scripts/check-repo.mjs` → `check-repo: ok` with no `docs/superpowers/**` exemption
