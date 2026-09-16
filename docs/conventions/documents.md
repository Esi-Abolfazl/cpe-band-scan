# Documents — one home per fact

Rule IDs: `doc-`. Every durable fact in a repo has exactly one owning document; everything else
points at it. This file is the map. Before writing anything down, find the owner — writing it
anywhere else creates the drift the next session implements against.

**Trust hierarchy: code > tests > docs.** A statement without a `file:line` pointer is a hint, not a
source. When a doc contradicts the code, the code is truth — fix the doc.

## doc-01 — The document map

| Document                            | Owns                                                                                                         | Update when                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| `AGENTS.md` (root)                  | Agent contract: gates (literal commands), Always / Ask-first / Never, routing table, session rules           | A standing rule for agents changes. Pointers, not prose                   |
| `CLAUDE.md`, other vendor files     | Exactly one line: `@AGENTS.md` (or the vendor's import syntax / a symlink)                                   | Never — `check-repo.mjs` `agents-link` enforces                           |
| `<scope>/AGENTS.md` (nested)        | One scope's agent card: slices, contracts door, binding ADRs, rules a compiler won't catch, gate. ≤ 40 lines | That scope's surface, boundary or binding ADR changes                     |
| `README.md`                         | For humans: what the product is, why, how to run it                                                          | Setup or run steps change. No agent rules here                            |
| `<module>/README.md`                | What one module owns, exposes and deliberately lacks (`vs-03`)                                               | The module gains/loses a table, a contract type, or a deferred item ships |
| `CONTEXT.md`                        | Domain glossary: canonical term + definition + `_Avoid_` synonyms (`llm-09`)                                 | **Same change** that introduces, renames or retires a term                |
| `ARCHITECTURE.md`                   | What exists and how pieces fit; ends with "What we deliberately don't have yet"                              | A cross-cutting shape changes or a deferred item ships                    |
| `docs/CONSTITUTION.md`              | Principles `con-NN` — override every rule file                                                               | Append next free `con-NN`; never renumber                                 |
| `docs/conventions/*.md`             | Every code rule with stable IDs; routing table + version in its README                                       | Self-update protocol                                                      |
| `docs/adr/NNNN-*.md`                | Invariants an agent could **not** infer from code — not a history                                            | ADR trigger test passes. `< 45 lines`. Number from `ls`, never memory     |
| `docs/tech-debts.md`                | Index only: `#N — label — path` per line                                                                     | A `DEBT #N` comment is added or retired. Body lives at the code           |
| `.agents/handoffs/<date>-<slug>.md` | Out-of-scope work found mid-task, self-contained                                                             | Per `workflow/handoffs.md`. `status: open → planned → done`               |
| `.agents/plans/*.md`                | Execution plans                                                                                              | Status flips, in the main checkout never a worktree                       |
| Generated contract + clients        | **Never hand-edited**                                                                                        | Only via the gen script, same commit as the cause (`vc-05`)               |

A project may rename `.agents/` to its agent vendor's folder (`.claude/`); the map, not the path, is
the rule.

## doc-02 — No prose restatements of code

No API shapes, field lists or flow steps retold in markdown. Pointers (`file:line`, test names) and
intent only. Behavior belongs in tests, invariants in ADRs, rules in conventions. A prose copy of a
type is stale the moment the type changes, and an agent will implement against the stale copy.

## doc-03 — Moving or deleting a doc fixes every pointer in the same change

Grep the repo for the filename; fix every live link — `AGENTS.md`, ADRs, conventions, agent folders
included. `check-repo.mjs` `md-links` fails on a dangling relative link.

## doc-04 — Definition of Done

Before claiming anything done, with **pasted output tails** as evidence:

1. **Gates** — every command in `AGENTS.md` § Gates run in full. A filtered gate is not a gate.
2. **Every acceptance criterion carries its proof** — a test name (`file: "test title"`) or
   `manual §N` with the reason automation cannot judge it.
3. **Manual QA script** — a Setup line (which user, seed state, flags), then 5–10 numbered steps
   with exact expected results. Only what automation cannot judge: feel, copy, layout, locale.
4. **Known limits named** — every deliberate cut is a `DEBT #N` at the code + ledger line.
5. **Sibling docs current** — `CONTEXT.md`, `ARCHITECTURE.md` "don't have yet", ADR if a new
   invariant, the scope's `AGENTS.md` card if its surface changed.
6. **Handoffs listed** — every out-of-scope item found became a handoff file; paths in the final
   report.

## doc-05 — Docs render for humans too

Readable sentences, no filler, formatted by the repo's markdown formatter in the pre-commit hook.
Tables for maps, bullets for parallel items, prose for argument. A doc an agent can parse but a
human cannot read will not be maintained by the humans.
