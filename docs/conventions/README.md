# Conventions

The source of truth for every code rule in an adopting repo — read by humans and agents alike when
writing, reviewing or refactoring. `PRINCIPLES.md` (copied to `docs/CONSTITUTION.md`) holds the
principles above these; when a rule here conflicts with a principle, the principle wins.

A project copies this folder to `docs/conventions/`, keeps the framework rule files verbatim (so an
upgrade is a diff), and adds its own stack-specific files (`backend.md`, `frontend.md`, `i18n.md`…)
with their own prefixes.

## Routing — load by impact, read only what you need

| Impact   | Task type                                                                 | Read                 |
| -------- | ------------------------------------------------------------------------- | -------------------- |
| CRITICAL | Slice shape, module boundaries, contracts door, registration lists        | `vertical-slices.md` |
| CRITICAL | Throwing, mapping or branching on an error                                | `errors.md`          |
| HIGH     | Naming, file placement, comments, barrels, generated output — any change  | `llm-friendly.md`    |
| HIGH     | Creating, editing, moving or deleting any `.md`; declaring a feature done | `documents.md`       |
| MEDIUM   | Tests, fixtures, coverage gates                                           | `testing.md`         |
| MEDIUM   | Commits, branches, PRs, codegen commit rule                               | `version-control.md` |
| HIGH     | Python: reference slice, `RouterError` codes, copy catalogue, test seams  | `python.md`          |

A project appends its stack rows here (`backend.md`, `frontend.md`, …). Multiple areas → load
multiple files. This table is the **only** copy — `AGENTS.md` points here; never duplicate it.

## Loading — always-on vs on-demand

`AGENTS.md` (and `CLAUDE.md` → `@AGENTS.md`) is always loaded — it's the contract. `PRINCIPLES.md`
and every rule file here load **per task**, not always-on: for most agents, via the routing table
above; for Claude Code with the `llmfw` plugin installed, each row is also a skill
(`llmfw:principles`, `llmfw:vertical-slices`, …) that Claude loads on demand when the description
matches the task. Either path reads the same file — `docs/conventions/<file>.md` in the adopting
repo, verbatim from the framework.

## Rule IDs

Every rule heading carries a stable ID `<prefix>-NN`:

| Prefix                          | File                   | Owner                            |
| ------------------------------- | ---------------------- | -------------------------------- |
| `con-`                          | `docs/CONSTITUTION.md` | framework (01–19), project (20+) |
| `llm-`                          | `llm-friendly.md`      | framework                        |
| `vs-`                           | `vertical-slices.md`   | framework                        |
| `err-`                          | `errors.md`            | framework                        |
| `tst-`                          | `testing.md`           | framework                        |
| `vc-`                           | `version-control.md`   | framework                        |
| `doc-`                          | `documents.md`         | framework                        |
| `be-`, `fe-`, `i18n-`, `db-`, … | project files          | project                          |

Cite IDs in reviews, commit bodies and handoffs ("violates vs-04").

- IDs are append-only: a new rule gets the next free number in its file.
- Never renumber or reuse an ID — a removed rule's number retires with it: keep the heading, body
  becomes `Retired: superseded by <id>` in one line.
- Framework files reserve `01–19` per prefix; a project appends from `20` in the same file so
  framework upgrades never collide.
- `check-repo.mjs` (`rule-ids` check) fails the build if an ID is defined twice.

## Self-update protocol — keep this folder the source of truth

When a rule is appointed — _"from now on…"_, _"always/never…"_, _"we use X not Y"_, or a pattern
gets corrected in review — treat it as a candidate rule:

1. **Apply it** to the code at hand first.
2. **Offer to persist it** in one line: _"Add this to docs/conventions?"_ Skip the question only if
   already told "remember this" / "update the conventions".
3. **On yes**, find the next free `<prefix>-NN` in the matching file (or open a new file + routing
   row only if none fits), add the rule, bump `Version:` in this README (patch for a tweak, minor
   for a new rule or file).
4. **Keep it tight:** one rule = an ID'd heading + a short imperative + a `✓/✗` example or a
   `file:line` reference. Don't restate what a compiler, analyzer or lint rule already enforces —
   link to it. Replace a superseded rule in place (keep the ID); never stack contradictions.

## Escalation ladder — prose does not fail a build

A rule violated twice stops being a paragraph someone must remember and becomes something a machine
checks:

1. **First violation:** fix it; if it is a real convention, write it down here.
2. **Second violation** (same rule, different PR or session): turn it into whichever layer can
   actually catch it — a compiler setting, an analyzer/lint rule (Oxlint custom rule, `.editorconfig`
   severity), an architecture test, a dependency-boundary rule, or a `check-repo.mjs` check. The
   convention stays as the human-readable explanation and gains a line: _"Enforced by: `<gate>`"_.
3. **Third violation** after a gate exists means the gate has a hole. Fix the gate, not the code.

See `gates/README.md` for which layer catches what.

## ADR trigger test — write one only when all four are true

1. Not already a `conventions/` rule ID.
2. Not caught by a machine — compiler, lint, arch test, dependency rule, `check-repo.mjs`.
3. Not a comment's job at one call site.
4. An agent writing ordinary code would actually violate it, **and** reversing the decision later is
   expensive (a migration, a rewrite, or it touches more than one module).

A "no" to (4), or a "yes" to (1)–(3), means no ADR — fix the rule in its real home instead.
Template: `agents/templates/adr.md`.

Version: 0.3.0
