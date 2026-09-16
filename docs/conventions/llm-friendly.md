# LLM-friendly code

An agent works through grep, file paths and a limited context window. These rules keep code
discoverable, self-explaining and safely editable under those constraints. Rule IDs: `llm-`.
Stack mappings (which lint/analyzer enforces each rule) live in `gates/stacks/<stack>.md`.

## llm-01 — Identifiers are grep-complete

A route, an error key, a claim name, a feature flag, an event type — each exists somewhere as one
literal, unbroken string, never assembled from fragments.

✓ `export const ROUTE = "/identity/login";` — grep `"/identity/login"` finds the slice, its tests,
and every client.
✗ `` `/identity/${action}` `` — invisible to search, exists only at runtime.

Enforced by: Oxlint `llmfw/no-composed-identifier` (`gates/stacks/typescript/oxlint/`), or the stack's
equivalent (`gates/stacks/`).

## llm-02 — File path predicts content

One use case, one file, named after the use case (`features/login.ts`, `Features/Login.cs`) — not
`identity-helpers.ts`. No `utils`, `helpers`, `misc`, `common`, `shared` grab-bag files or folders.
A project may grandfather **one** named single-purpose exception and lists it in its `AGENTS.md`.

Enforced by: Oxlint `llmfw/no-grab-bag-file`; `check-repo.mjs` `forbidden-paths`.

## llm-03 — No barrels; generated code exempt

No `export *`, no `index.ts` re-export hubs, no `__init__.py` that re-exports a package's internals,
no static "facade" class that forwards to real implementations. A barrel hides the real source
behind an extra hop and makes "who uses this" ungreppable. Generated output may do whatever the
generator emits; nothing hand-written re-exports it.

Enforced by: Oxlint `llmfw/no-barrel`; dependency-boundary rule that only allows the generated
folder to be imported from its declared consumers.

## llm-04 — No dynamic dispatch, no reflection scans

Every registration — modules, endpoints, handlers, validators, entity configurations, DI bindings
— is an explicit greppable list, never an assembly scan, a glob import, a decorator registry
discovered at runtime, or a convention-based auto-wire.

One exception: a set that is **closed by a compiler-checked base type and whose missing member
fails a gate** may be enumerated by the machine (an error catalog where every subclass without a
message fails a test qualifies). Validators, endpoints and mappings do not — a scan there changes
behavior silently.

The hand-written list is the map a reader navigates by (`con-16`): omitting an entry fails loudly.

Enforced by: `check-repo.mjs` `forbidden-patterns` (per-stack regex list in the project config).

## llm-05 — Declare, then reference

Within a file, the reader hits the contract before the logic: route/const, then public types
(request, response, validator), then the handler. A type is never referenced above its declaration
in the same file. See `vs-01` for the slice shape.

## llm-06 — Files fit a context window

~300 lines is the point to stop and ask whether a file has grown a second responsibility. A full
slice — route, endpoint, request, response, validator, handler — fits in ~120 lines in most stacks.

Enforced by: Oxlint `llmfw/max-file-lines` (default 300, warn at 250); `check-repo.mjs`
`file-size` for non-JS stacks.

## llm-07 — Errors and logs are literal and unique

One typed error per distinct failure, named after the failure (`SelfInquiry`, `ListingNotFound`),
never a shared `throw new Error("operation failed")` that collapses distinct failures into one
ungreppable string. The error's name **is** its wire key (`err-01`), so renaming it is a breaking
change and an ask-first action. Log messages are literal template strings with structured
parameters, never concatenated prose.

## llm-08 — Generated output is marked and never hand-edited

Generated files carry a `.gen.` infix (`types.gen.ts`, `Client.gen.cs`) or live under a folder
named `gen/` / `generated/`. They are produced by one named script (`pnpm gen:api`, `make gen`),
committed in the same commit as the change that caused them (`vc-05`), and never edited by hand.
A new codegen follows the same marker; it never invents a new one.

Enforced by: CI step `gen && git diff --exit-code <generated paths>`.

## llm-09 — One name per domain concept

`CONTEXT.md` is the closed vocabulary: canonical term, one-line definition, `_Avoid_` synonyms.
Code, i18n keys and docs use only those terms. Introducing, renaming or retiring a concept updates
`CONTEXT.md` in the same change. A term that exists only in code is a term the next session
re-invents differently.

## llm-10 — A known cut is a `DEBT #N` comment, not a TODO

A deliberate shortcut gets `// DEBT #N: what — ceiling` at the code and a `#N — label — path` line
in `docs/tech-debts.md`. The ledger is an index; the explanation lives at the code (`con-01`). A
bare `TODO`/`FIXME`/`HACK` is a lint failure.

Enforced by: `check-repo.mjs` `debt-ledger` (two-way parity); Oxlint `llmfw/no-bare-todo`.

## llm-11 — Public surface is typed at the edge

Every entry point (HTTP handler, CLI command, queue consumer, exported function of a package) has
an explicit request type and response type — no `any`, no `object`, no untyped dictionary, no
positional bag of primitives beyond two. An agent reads the types to learn the contract; it should
never have to read the body.

## llm-12 — Configuration is a typed, validated object read in one place

Environment variables and config files are read in exactly one module (`env.ts`, `Settings.cs`,
`config.py`) that validates and types them at startup. Nothing else touches `process.env`,
`os.environ`, `Environment.GetEnvironmentVariable`. A missing or malformed value fails at startup
(`con-14`), never at first use.

Enforced by: Oxlint `no-process-env` scoped by `overrides`; stack equivalents in `gates/stacks/`.
