# Vertical slices and module boundaries

Code is organized by **use case** (a slice), slices are grouped into **modules** that own a
bounded context, and a module reaches another only through its **contracts door**. Rule IDs:
`vs-`. Stack mappings in `gates/stacks/`.

Why this shape for agents: an agent asked to "add cancel-order" needs to open one folder, copy one
sibling file, and register one line. Layered architectures (controllers/, services/, repositories/)
scatter a use case across five folders and force the agent to hold all five in context.

## vs-01 — One file per use case, fixed section order

A slice is one file (or one folder for a slice with a UI) named after the use case in the
imperative: `CancelOrder`, `switch-company`. Section order is fixed so a reader hits the contract
before the logic (`llm-05`):

1. **Route / trigger** — the literal path, command name or event type as a `const`.
2. **Entry point** — the handler registration (endpoint class, router entry, command def).
3. **Request** and **Response** types, then the **Validator**.
4. **Handle** — the business logic. Last.
5. Private helpers used only by this slice — below `Handle`, never in a shared file.

A project names one reference slice in its stack convention file (`be-01`, `fe-01`) and every new
slice copies it. Enforced by: an architecture test asserting the route const and entry-point shape
exist for every slice (see `gates/stacks/`).

## vs-02 — No mediator, no generic pipeline

The entry point calls `Handle` directly. Cross-cutting concerns (validation, auth, transaction,
logging) are named filters/middleware attached at the entry point, not pipeline behaviors dispatched
by type. A mediator adds a hop grep cannot follow and makes "what runs when I POST here"
unanswerable from the file.

## vs-03 — A module needs its three justifications, written down

A module is its own project/package + its own persistence namespace (schema, table prefix, key
prefix) + a `README.md` answering: **what product question it answers**, **what it owns**
(tables, error keys, events), **what it exposes** (its contracts door). A module you cannot justify
in those three lines is a folder, not a module. Adding a module is an **ask-first** action.

## vs-04 — A module reaches another module only through its contracts door

Each module publishes exactly one contracts surface — a `<Module>.Contracts` project, a
`contracts/` package, a `contracts.py` — containing only interfaces, DTOs and constants. The
contracts surface depends on nothing but the runtime (no ORM, no HTTP framework, no other module).
Reading another module's tables, importing its internals, or reaching its DI registrations directly
is a boundary violation.

Enforced by: a dependency-boundary rule (dependency-cruiser / Oxlint `import/no-restricted-paths` /
ArchUnit-style test / `go vet` import restriction) listing the allowed module → contracts edges.
The allowed edges live in **one** file (`vs-06`).

## vs-05 — Synchronous in-process calls are the default

Inter-module calls are direct typed calls through the contracts interface in the same request and
transaction scope. Events, outboxes and message buses are adopted at the first concrete need for an
**asynchronous** cross-module effect, recorded as an ADR — not before (`con-09`).

## vs-06 — The module list lives in one file

Every module is one line in one bootstrap file that the host, the migrator, the test harness and
the architecture tests all read: register, map, add persistence, list assemblies, list allowed
dependencies. A module cannot be registered in one and forgotten in another. Nothing scans for
modules (`llm-04`).

## vs-07 — Every entry point declares its authorization

Anonymous or a named requirement — no third state. A slice with neither fails at startup or in an
architecture test (`con-12`), never at request time in production.

## vs-08 — Slice-local first, promote on the second use

A helper, a mapper, a query lives inside the slice file until a second slice needs it. On the second
use it moves to the module's own `Shared/` (still inside the module, never a repo-wide grab-bag —
`llm-02`). It crosses into a kernel/platform package only when a third **module** needs it and it
has no domain meaning.

## vs-09 — Persistence is module-private

Retired for this repo: persistence is a folder of JSON files owned by `store.py`; there is no second module to keep it private from.

## vs-10 — A slice ships with its test and its registration

A slice is done when: the file exists in the fixed order (`vs-01`), it is registered in the explicit
list (`vs-06`), it has a `<Slice>Tests` covering the happy path and one denial/validation path
(`tst-01`), and generated clients are regenerated (`llm-08`). A coverage test asserts every slice
has a test class; a slice not in the registration list is dead code (`con-08`).

## vs-11 — Frontend features mirror backend modules

A UI feature folder (`features/<name>/`) owns its routes, components, forms and server calls for
one bounded context, and imports other features only through their declared public files (a
feature-level contracts door). Cross-feature imports of internals are a dependency-boundary
violation like `vs-04`. One Playwright/e2e spec per feature folder (`tst-07`).
