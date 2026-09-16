# Version control

Rule IDs: `vc-`.

## vc-01 — Conventional commit subjects, by habit

`type(scope): subject`, lower-case, imperative, ≤ 72 chars; scope optional in a repo this size.
No commit hook: one person writes these and reads them back.

✓ `feat(speed): per-band speed and ping probe` ✗ `Fixed the login bug`

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

Retired for this repo: there is no pull request to template. `doc-04` is the Definition of Done.

## vc-08 — An agent session reaches `main` only through a PR

Retired for this repo: pull requests are a reviewer's tool; this is one person's app. `vc-20` says how work lands.

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

## vc-20 — Work lands on `main` directly

One person's app: commit to `main`, run the `AGENTS.md` gates, push fast-forward. No branches or
pull requests unless the owner asks for one. CI repeats the gates on every push to `main` as the
record. `vc-03` still holds: rewriting pushed history is ask-first.
