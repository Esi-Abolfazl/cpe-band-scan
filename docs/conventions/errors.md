# Errors

Rule IDs: `err-`. An error is a contract between the code that detects a failure and the code (often
in another repo, often generated) that branches on it. These rules make that contract typed,
greppable and translatable.

## err-01 — One typed error per failure; its name is its wire key

Each distinct failure is one sealed/final class or one tagged variant, named after the failure
(`ListingNotFound`, `SelfInquiry`), extending one of a small set of **abstract status bases**
(`NotFound`, `Conflict`, `Forbidden`, `Unauthorized`, `BusinessRule`). The wire key is derived from
the type — `<Module>.<ClassName>` — never written by hand at the throw site. Renaming the class is a
breaking wire change and an **ask-first** action.

✓ `throw new SelfInquiry()` ✗ `throw new ConflictException("cannot inquire on own listing")`

## err-02 — No message at the throw site

The sentence a user reads lives in the owning module's message catalog
(`Errors/messages.<locale>.json`), keyed by the wire key. A key with no message in every supported
locale fails a test. This is what lets a client render `detail` without shipping its own catalog.

## err-03 — Problem responses carry `errorKey` and a non-empty `detail`

Retired for this repo: the API answers `{"error": code, "message": sentence}` to its own page only; no RFC 9457 client exists.

## err-04 — The key set reaches the client as a type

Retired for this repo: no generated client; the page reads the same `copy.ERRORS` the server does.

## err-05 — Errors are exceptions to flow, not to values

Use the language's idiom for expected failures: a `Result`/`Either` type or typed exception is
fine, but never a `null`/`-1`/`false` that means "failed" and a boolean that means "which way".
`con-06`: the failure is a distinct variant the compiler makes the caller handle.

## err-06 — No swallowed failures

An empty `catch`, a `catch` that only logs on a write path, a fire-and-forget promise, or a
`try/except: pass` is a `con-14` violation. If losing the work is acceptable, the code says so by
using the named at-most-once mechanism (a deferred-work interface), never by catching and
continuing.

Enforced by: Oxlint `no-empty` + `no-floating-promises` (type-aware); stack analyzers in
`gates/stacks/`.

## err-07 — Logs are structured and literal

`log.warn("inquiry rejected: {Reason}", reason)`, never
`log.warn("inquiry rejected: " + reason)`. The template is a literal that grep finds; the parameters
are structured fields a log query filters on. Log at the boundary where the failure is mapped, not
at every layer it passes through.
