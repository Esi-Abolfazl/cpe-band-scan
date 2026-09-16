# Version control

Rule IDs: `vc-`.

## vc-01 — Conventional commits, enforced by a hook

Every commit message passes commitlint (or equivalent) against `config-conventional` plus the
repo's `scope-enum`: one scope per module/package/feature plus `docs`, `ci`, `deploy`, `deps`,
`tooling`, `agents`. Subject ≤ 100 chars, lower-case start, imperative.

✓ `feat(identity): add switch-company slice` ✗ `Fixed the login bug`

Enforced by: `commit-msg` hook via lefthook/husky/pre-commit.

## vc-02 — Body explains why, not what

The diff already shows what changed. A body is bullets on **why** — the constraint, the bug, the
decision, the rule ID it implements or fixes (`fixes vs-04 violation in Trade`).

## vc-03 — Linear history, rebase only

No merge commits. Bring `main` into a branch with `git rebase main`, land with `--ff-only`,
`git pull --rebase` never a plain `git pull`. Rewriting already-pushed history needs the user's
sign-off first; local-only history rebases freely.

## vc-04 — Branch naming

`<type>/<slug>` matching the commit type: `feat/switch-company`, `fix/audit-pagination`,
`routine/dead-code-trade`. No personal-name or ticket-only branch names.

## vc-05 — Generated output ships with the change that caused it

Codegen output (OpenAPI document, generated clients, generated migrations) is committed in the
**same commit** as the change that produced it — never a follow-up commit, never left for CI. CI
runs `gen && git diff --exit-code <generated paths>` and fails on drift; it does not fix it.

## vc-06 — Never edit an applied migration

A migration that has shipped is immutable. A fix is a new migration.

## vc-07 — PR template is filled, not deleted

What / Why / How verified (gate output pasted, not asserted) / Out of scope / Debt added (`DEBT #N`
or "None") / Handoffs created (paths) / Screens for any UI change in each supported locale.

## vc-08 — An agent session reaches `main` only through a PR

An agent never pushes `main`. It branches, opens a PR, enables auto-merge with rebase; `main`
moves when CI is green and not before. This is not taste: a direct push is a commit no gate ever
saw, and it makes every green check on every other PR a statement about a tree that no longer
exists.

## vc-09 — Never commit machine-specific paths

No file that names a home directory (`/Users/…`, `~/.config`) or runs a gitignored script. It works
here and fails in every other clone. Machine-specific config goes in the gitignored sibling
(`.claude/settings.local.json`, `.env`), never in the committed file.

Enforced by: `check-repo.mjs` `forbidden-patterns` (`/Users/`, `/home/`, `C:\\Users`).

## vc-10 — One SDK/toolchain version, pinned everywhere

`global.json`, `.nvmrc`/`package.json#engines`, `.python-version`, `go.mod` toolchain, every
Dockerfile base image and every CI runner pin the **same** version, with roll-forward disabled.
Analyzers ship with the toolchain; a drifting patch makes warnings-as-errors disagree between
machines. Enforced by: `check-repo.mjs` `toolchain-version`.
