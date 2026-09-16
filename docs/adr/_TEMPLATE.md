# NNNN. <Title stated as the assertion, not the topic>

Status: accepted · Date: YYYY-MM-DD

<!--
Before writing this file, pass all four gates (conventions/README.md § ADR trigger test):
1. Not already a conventions rule ID.
2. Not caught by a machine — compiler, lint, arch test, dependency rule, check-repo.mjs.
3. Not a comment's job at one call site.
4. An agent writing ordinary code would actually violate it, AND reversing it later is expensive.
A "yes" to 1–3 means no ADR: fix the rule in its real home instead.
Take the number from `ls docs/adr/`, never from memory. Under 45 lines. Delete this comment.
-->

## Invariants

- **<the rule, imperative>** — <the wrong code an agent would write, and where the rule is
  enforced or visible: `file:line`, an arch test name, a convention rule ID. If the rule
  contradicts a convention on purpose, say so and name the rule ID, so a later agent does not
  "fix" it.>

## Where it lives

- `path/to/file` — <one line on what it owns>

## Known gaps

- <Only if real — a claim the code does not yet keep, or a contradicting doc. Omit otherwise.>
