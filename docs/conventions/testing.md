# Testing

Rule IDs: `tst-`. Tests are the executable half of the conventions: whatever a rule file says a
slice must have, a test asserts every slice has it.

## tst-01 — Every slice has a `<Slice>Tests` class

A coverage assertion finds every slice in a module (every type with the entry-point shape) and
fails if no `<Slice>Tests` exists in the matching test project. Each `<Slice>Tests` covers the happy
path and at least one denial or validation path. A test file is named after the slice, next to its
siblings, never grouped by layer.

## tst-02 — Real infrastructure, never in-memory fakes of it

Retired for this repo: no database, queue or cache exists; the router is faked at the library seam (`py-05`).

## tst-03 — Per-test reset, order-independent, serial per assembly

Retired for this repo: no shared infrastructure to reset; every test gets its own temp home (`py-04`).

## tst-04 — Tests reference the slice's route const, never a literal path

The slice's `Route` const (`vs-01`) is the only spelling of its path. A test that hard-codes
`"/identity/login"` is a review defect: renaming the route would leave a green test hitting a 404
that the assertion never checks.

Enforced by: Oxlint `llmfw/no-literal-route-in-test`; analyzer or grep gate in other stacks.

## tst-05 — Tests deserialize with the host's serializer configuration

Retired for this repo: the server and its tests share `json` from the stdlib; there is no serializer config.

## tst-06 — A schema conventions test per module

Retired for this repo: no schema, no ORM, no module boundary to assert over.

## tst-07 — One end-to-end spec per UI feature folder

Retired for this repo: no UI feature folders and no browser driver; the page is checked by `tests/test_parity.py` and `tests/test_page_quality.py`.

## tst-08 — Architecture tests are tests

Module boundaries (`vs-04`), slice shape (`vs-01`), explicit registration (`llm-04`), instant types
in domain code, authorization declared (`vs-07`) — each is an assertion in an architecture test
project that runs with the unit tests. A boundary rule that lives only in prose is not a rule
(`conventions/README.md` escalation ladder).

## tst-09 — Assert on behavior, not on collaborators

`con-11`. Assert on the response, the rows, the emitted events. Never on "method X was called with
Y". A test that needs one mock per internal dependency is testing the implementation; rewrite it as
an integration test one level up.

## tst-10 — A flaky test is a bug, not a retry policy

No `retries: 3`, no `[Retry]` attribute, no `--rerun-failed` as the fix. A flaky test gets a
handoff (`workflow/handoffs.md`) with the failure output and either a root-cause fix or deletion
with a stated reason.
