# Principles

Non-negotiable principles for every change in a repo that adopts this framework. Rule files in
`conventions/` implement these; when a rule file and a principle conflict, the principle wins.

Each principle has a stable ID `con-NN`. A project copies this file to `docs/CONSTITUTION.md`,
keeps the IDs, and appends its own principles from `con-20` upward (`con-01`–`con-19` are reserved
for the framework so an upgrade never collides).

## con-01 — Correct by design, not merely working

Default to the solution that is correct by design. Minimal code is good; minimal correctness is
not. No silent technical debt: a deliberate shortcut is named at the code (`// DEBT #N: what —
ceiling`) and indexed in the debt ledger (`llm-10`). A workaround presented as the solution is a lie
the next reader has to discover.

## con-02 — Root cause over symptom

When the clean fix lives in another layer — the schema, a module's contracts surface, the API
contract, an upstream library — propose that change as the primary path instead of patching around
it at the call site. Upstream first: check the tracker, the changelog and the published artifact
before writing a local workaround.

## con-03 — One source of truth per rule

A business rule (authorization, eligibility, pricing, validation, naming) lives in exactly one
place; everything else calls or references it. Never re-derive it, never branch on a proxy (an id
range, a name pattern, a kind string) that only correlates with it. If two sides must agree (UI and
API, cache and store), add a test that they agree or redesign so one implementation exists.

## con-04 — Conventions are captured, not remembered

When a convention is appointed ("from now on…", "always…", "we use X not Y"): a cross-cutting
principle is appended here with the next free `con-NN`; a code-level rule goes to `conventions/`
per the self-update protocol. Chat memory is not a rule store. A rule that is not written down does
not exist for the next session.

## con-05 — Comments address the next reader

A comment states what the code cannot: an invariant, an external constraint, a deliberate ceiling —
at most 3 lines. Banned: narrating the next line, addressing the reviewer, commented-out code, a
bare `TODO` with no `DEBT #N`.

## con-06 — Make invalid states unrepresentable

If a value can hold a combination that must never exist, the type is wrong. Use sum types, enums,
records and database constraints so wrong states cannot be constructed. ✓ a discriminated
`Result` type ✗ two nullable booleans that can both be true.

## con-07 — Name things after the question they answer

A name states intent, not a technical approximation. ✓ `eligible-approvers`
✗ `users-with-capability` used to mean the same thing. When the honest name does not match what the
code does, fix the code or the name — the mismatch is the design bug.

## con-08 — Delete, don't comment out

Dead code is a claim the next reader must disprove. Unused code, flags and stale comments are
deleted, not kept "in case" — version control remembers.

## con-09 — No speculative code

Code exists only when a caller needs it today. No interface with one implementation, no config for
a value that never changes, no message bus before the first asynchronous need is real. YAGNI stops
at correctness: never simplify away validation at a trust boundary, error handling that prevents
data loss, security, or accessibility.

## con-10 — Dependencies are debt

Before adding a package: can the platform, the standard library, or an already-installed dependency
do it? Adding one needs a stated reason and is an **ask-first** action in `AGENTS.md`. Never add one
to save ten lines.

## con-11 — Tests check behavior, not implementation

Refactoring internals without changing behavior must not break tests; if it does, the tests test
the wrong thing. Assert on inputs, outputs and observable effects (rows, responses, emitted events),
never on call order or a mock of every internal collaborator.

## con-12 — Deny by default

Every entry point declares its access explicitly — anonymous or a named requirement — with no
third state. An entry point with neither fails at startup or at build, never at request time in
production.

## con-13 — Validate at the boundary, trust inside

Untrusted data is validated once, completely, where it enters. Inside, code works with clean typed
data. Defensive null-checks sprinkled through internal code mean nobody knows where validation
happened — that is the defect, not the safety.

## con-14 — Fail loudly, never silently

A failure discovered in three months is worse than one that stops the request today. Errors are
typed and carry a stable, greppable key the client branches on. An empty `catch`, a swallowed
rejected promise, or a log-and-continue on a write path is a bug scheduled for later.

## con-15 — Culture is never ambient

Data at rest is UTC instants, ASCII digits, and typed money (amount + currency, or a unit-suffixed
column). Locale-aware formatting happens only at the display edge. No code path reads or sets a
process-global culture.

## con-16 — Automate mechanics, surface decisions

A line that could only ever be written one way is **machinery**: it lives in one named place and
runs automatically. A line where a competent developer could reasonably choose differently is a
**decision**: it stays at the call site, greppable. Test: delete the line — did you break the
machine (automate it) or change what the system means (show it)?

Automatic is not invisible. An automated mechanic owes the reader: one named implementation, one
line in the owning convention file saying it happens and where, and one test that fails when it
stops happening. Magic whose absence you cannot detect is the actual problem.

## con-17 — Boundaries before code

Before touching a module, name the boundary you are inside and the contract you cross. A change
that crosses a module boundary any way other than the documented door (contracts surface, event,
public API) is a design change — stop and surface it before writing it.

## con-18 — Verify before "done"

Run the gate, paste the real output tail. A filtered gate (`… | grep -v`) is a passing grep, not a
passing check. Never report an earlier green run as current if code changed since. Evidence means
command output, not an assertion that it passed.

## con-19 — Scope stays clean

Out-of-scope work found mid-task becomes a handoff file, never an inline fix and never a "want me
to also…?" offer. A trivial fix on a line already being edited is the only exception.

---

This file is append-only: a principle is added with the next free `con-NN`, never renumbered or
reused. Projects append from `con-20`.
