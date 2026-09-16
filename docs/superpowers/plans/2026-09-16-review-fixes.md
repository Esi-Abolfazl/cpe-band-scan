# CPE Band Scan Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the thirteen findings of the 2026-09-16 whole-repo review of CPE Band Scan, each with a test that fails before the fix; then give the page one scan control (choose the scope, press Start) and bring it up to the `ui-ux-pro-max` quality bar.

**Architecture:** No new modules. Each fix lands in the layer that owns the rule: ranking in `metrics.py`, the one-job-at-a-time rule and request validation in `server.py`, band-list validation in `lockfreq.py` (the single write path), error translation in `router.py`, saved-run ids in `store.py`, terminal behaviour in `cli.py`, words in `copy.py`, the page in `app.js`, and install in the launchers and README. The two UI tasks (11, 12) change `copy.py`, `app.js`, `index.html` and `style.css` only, and record their design rulings in `docs/design-system.md`.

**Tech Stack:** Python 3.10+, `huawei-lte-api` (the only runtime dependency), stdlib `http.server`, vanilla JS, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-16-cpe-band-scan-spec.md` for the product rules. The findings this plan closes are listed under **Findings** below; each task names the finding it closes.

## Global Constraints

- Python 3.10 or newer. Exactly one runtime dependency: `huawei-lte-api>=1.7`. Dev dependency: `pytest`.
- Every module under `src/cpe_band_scan/`. Tests under `tests/`. No test may touch a real router.
- The server binds `127.0.0.1` only, never `0.0.0.0`. Every `/api/*` request requires the header `X-CPE-Band-Scan-Token` and a `Host` header of `127.0.0.1` or `localhost`.
- The router password is never written to disk, never placed in a URL or query string, and never logged.
- All user-facing text lives in `src/cpe_band_scan/copy.py`. No string literal shown to a user may appear in `server.py`, `cli.py`, `app.js` or `index.html`.
- Text follows the `ux-writing` skill, English rules: sentence case, contractions allowed, buttons are `[verb] [object]`, errors are `[what happened]. [why]. [what to do]`.
- Every band change restores the lock the router arrived with on the way out, including cancel and crash, via `finally`.
- Defaults: router `http://192.168.8.1/`, username `admin`, port `8765`.
- Band-lock writes go to `api/net/lock-freq` only. Writing `LTEBand` to `api/net/net-mode` is forbidden anywhere in this codebase.
- Work on a branch in the main checkout at `/Users/esi/Work/Other/cpe-band-scan`, not in a worktree: the test interpreter is `.venv/bin/python` inside that checkout. Every test command below is run from that directory.
- Commit messages follow the existing log: lowercase `fix:` / `test:` / `docs:` prefix, then a sentence that states the behaviour.

---

## Findings

| # | Severity | Finding | Task |
|---|---|---|---|
| 1 | High | `metrics.rank()` sorts every side by the LTE SINR floor, so a 5G scan is ranked by a number that doesn't move between NR bands | 1 |
| 2 | High | `/api/apply`, `/api/clear`, `/api/connect` are not refused while a job runs; only the page greys the buttons out | 2 |
| 3 | High | README says `pipx install cpe-band-scan` (not on PyPI) and the launchers call a system `python3` that has no such module | 10 |
| 4 | Medium | Cancelling a test before its first sample raises `IndexError` in `summarise([])` | 5 |
| 5 | Medium | A router that drops mid-session surfaces as `crash`, not `unreachable`: `Router.get/post` map only `ResponseErrorException` | 4 |
| 6 | Medium | `store.save()` trusts a caller-supplied `id`, so `../escaped` writes outside the runs folder | 6 |
| 7 | Medium | `/api/apply` passes a string band through; `band_info("78")` locks B7 and B8 | 3 |
| 8 | Low | `--password` on the command line lands in shell history and `ps`; the skill recommends it | 7 |
| 9 | Low | `scan 7 40` with no side also tries N7 and N40 on the 5G side | 7 |
| 10 | Low | `cpe-band-scan apply` prints "Your connection is back" before the 35 s re-attach | 7 |
| 11 | Low | `ERRORS["no_results"]` and `ERRORS["band_refused"]` are never raised | 8 |
| 12 | Low | The save-name box resets to the suggestion on every re-render | 9 |
| 13 | Low | `/api/events?since=abc` returns a 500 | 3 |
| U1 | Request | The page shows three scan buttons; the person should choose a scope (all / 4G / 5G) and press one Start button | 11 |
| U2 | Request | Apply the `ui-ux-pro-max` skill to the page: accessibility, touch targets, focus, motion, one primary action per screen | 12 |

## Design rulings for Tasks 11 and 12 (from the `ui-ux-pro-max` skill)

The skill's `--design-system` generator was run twice (`"local network utility tool router diagnostics ..."` and `"developer tool network monitoring dashboard ..."`). It proposed Neumorphism with orange and Lora/Raleway, then OLED-dark-only with Fira. Neither fits: the page already supports light and dark, neumorphism is flagged low-contrast, and a wellness or code font pairing says the wrong thing about a router tool. Rulings, recorded so nobody re-derives them:

- **Pattern:** the generator's "Real-Time / Operations" pattern — neutral surface, status colours (green / amber / red) carrying meaning with a word beside them, data-dense but scannable, one primary action.
- **Colour:** keep the existing neutral light/dark tokens in `style.css`; they already pass 4.5:1 (checked: muted `#5d6470` on `#f7f8fa` ≈ 5.4:1, `#9aa3b0` on `#1d2128` ≈ 6.5:1, amber `#9a6700` on white ≈ 4.6:1).
- **Type:** `system-ui` stays. The app is a local privacy tool that must work with the router as the only network; a Google Fonts stylesheet would be its first third-party request. Base 16px, line-height 1.5, weights 400 / 500 / 600.
- **Motion:** 150–200 ms on colour and shadow only, `prefers-reduced-motion` turns it off. No decorative motion.
- **Primary action:** exactly one per screen. Connect screen: Connect. Main screen before results: Start the scan. Main screen with results: the best row's "Use this band"; Start drops to secondary. Save is never primary.
- **Icons:** none needed; the `?` is text inside a labelled button, not an emoji icon.
- **Touch targets:** every control ≥ 44 px on its shortest side, including the `?` buttons (visual 1.75rem, hit area extended with a pseudo-element).
- **Native controls:** the scope selector is a `fieldset` of native radio inputs with visible labels — no custom segmented control.

## File Structure

| File | Change |
|---|---|
| `src/cpe_band_scan/metrics.py` | `rank()` learns which side it ranks |
| `src/cpe_band_scan/scanner.py` | passes the side to `rank()`; `trace()` ends cleanly with no samples |
| `src/cpe_band_scan/lockfreq.py` | `bands_of()` validates every band list on the one write path |
| `src/cpe_band_scan/router.py` | per-request `OSError` becomes `unreachable` |
| `src/cpe_band_scan/server.py` | `require_idle()`, `bad_request` for bad input, url in job error messages |
| `src/cpe_band_scan/store.py` | a saved run's id is always one the store minted |
| `src/cpe_band_scan/cli.py` | `scan_target()`, no `--password`, honest apply sentence |
| `src/cpe_band_scan/copy.py` | `+bad_request`, `+lock_written`, `-no_results`, `-band_refused` |
| `src/cpe_band_scan/web/app.js` | the typed run name survives a re-render; scope radios + one Start button; a11y and primary-action rules |
| `src/cpe_band_scan/web/style.css` | focus rings, 44 px targets, motion tokens, reduced motion, danger button |
| `src/cpe_band_scan/web/index.html` | the banner announces errors to screen readers |
| `docs/design-system.md` | the design rulings above, as the page's source of truth |
| `skills/bandscan/SKILL.md` | no longer recommends `--password` |
| `run-cpe-band-scan.command`, `run-cpe-band-scan.bat` | create a private venv on first run |
| `README.md` | install from the folder, launchers documented |
| `tests/*` | one new failing test per finding, plus adjustments named in each task |

---

### Task 1: Rank the 5G side by the 5G carrier

Closes finding 1.

**Files:**
- Modify: `src/cpe_band_scan/metrics.py` (`rank`)
- Modify: `src/cpe_band_scan/scanner.py` (`_scan_side`, the `side_done` event)
- Test: `tests/test_metrics.py`, `tests/test_scanner.py`

**Interfaces:**
- Consumes: `metrics.rank(results: dict, expect_5g: bool = True) -> list[str]`.
- Produces: `metrics.rank(results: dict, expect_5g: bool = True, side: str = "lte") -> list[str]`. `side="nr"` sorts by `(-nrsinr, -nrrsrp)`; any other side keeps `(-floor, -sinr)`. Nothing else changes shape.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_metrics.py`:

```python
def test_the_5g_side_is_ranked_by_the_5g_carrier():
    """During a 5G scan the 4G anchor stays on automatic, so the LTE floor is the same noise
    for every NR band. Only the NR carrier's own numbers tell the bands apart."""
    results = {
        "N78": {"floor": 8, "sinr": 8, "nrsinr": 2, "nrrsrp": -80, "has5g": True},
        "N1": {"floor": 8, "sinr": 8, "nrsinr": 20, "nrrsrp": -90, "has5g": True},
        "N28": {"floor": 8, "sinr": 8, "nrsinr": 20, "nrrsrp": -70, "has5g": True},
        "auto": {"floor": 8, "sinr": 8, "nrsinr": 30, "nrrsrp": -60, "has5g": True},
    }
    assert metrics.rank(results, side="nr") == ["N28", "N1", "N78"]


def test_the_4g_side_is_still_ranked_by_the_floor():
    results = {
        "B7": {"floor": 7, "sinr": 8, "nrsinr": 2, "nrrsrp": -80, "has5g": True},
        "B1": {"floor": 2, "sinr": 9, "nrsinr": 20, "nrrsrp": -70, "has5g": True},
    }
    assert metrics.rank(results, side="lte") == ["B7", "B1"]
```

Append to `tests/test_scanner.py` (after the existing `run_scan` helper; `Seq`, `FakeSession`, `factory`, `Router`, `DEVICE` are already imported there):

```python
def nr_signal(nrsinr, band="B7(N78)"):
    return {"band": band, "sinr": "8", "rsrq": "-10", "rsrp": "-85",
            "nrsinr": f"{nrsinr}", "nrrsrp": "-80"}


def test_a_5g_scan_orders_the_bands_by_their_own_carrier():
    """One baseline read, then six reads per set (one attach check, five samples): N78 at 2 dB,
    N79 at 20 dB, then the auto row. The LTE floor is 8 dB in every read, so if N79 is not first
    the ranking is reading the anchor instead of the NR carrier."""
    session = FakeSession({
        "device/signal": Seq([nr_signal(2)] * 7 + [nr_signal(20)] * 6 + [nr_signal(5)] * 6),
        "net/lock-freq": {"lte_info": {}, "nr_info": {}},
        "config/network/bandfreqlist.xml": {"config": {"lte_support_band_list": "7",
                                                       "nr_support_band_list": "78,79"}},
        "device/nbrcellinfo": {}, "device/seccellinfo": {},
    })
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    events = run_scan(router=router, device=DEVICE, sides=("nr",))
    done = next(event for event in events if event["type"] == "side_done")
    assert done["order"] == ["N79", "N78"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_metrics.py::test_the_5g_side_is_ranked_by_the_5g_carrier tests/test_scanner.py::test_a_5g_scan_orders_the_bands_by_their_own_carrier -v`
Expected: both FAIL. The first with `TypeError: rank() got an unexpected keyword argument 'side'`, the second with `['N78', 'N79'] != ['N79', 'N78']`.

- [ ] **Step 3: Make `rank()` side-aware**

In `src/cpe_band_scan/metrics.py`, replace the whole `rank` function with:

```python
RANK_KEYS = {"lte": ("floor", "sinr"), "nr": ("nrsinr", "nrrsrp")}


def rank(results: dict, expect_5g: bool = True, side: str = "lte") -> list[str]:
    """Best first. 'auto' is a reference row, never a candidate. The 4G side ranks by the LTE
    SINR floor; the 5G side by the NR carrier, because during a 5G scan the LTE anchor is on
    automatic and its numbers say nothing about the NR band under test."""
    first, second = RANK_KEYS.get(side, RANK_KEYS["lte"])
    live = {name: row for name, row in results.items()
            if name != "auto" and (row.get("has5g") or not expect_5g)}
    return sorted(live, key=lambda name: (-live[name][first], -live[name][second]))
```

In `src/cpe_band_scan/scanner.py`, in `_scan_side`, change the `side_done` yield's last field from

```python
           "skipped": skipped, "order": metrics.rank(results, expect_5g)}
```

to

```python
           "skipped": skipped, "order": metrics.rank(results, expect_5g, side)}
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/cpe_band_scan/metrics.py src/cpe_band_scan/scanner.py tests/test_metrics.py tests/test_scanner.py
```
```bash
git commit -m "fix: the 5G side is ranked by the 5G carrier, not the 4G anchor"
```

---

### Task 2: One job at a time is the server's rule, not the page's

Closes finding 2.

**Files:**
- Modify: `src/cpe_band_scan/server.py` (`Session.start`, new `Session.require_idle`, `do_POST`)
- Test: `tests/test_server_jobs.py`

**Interfaces:**
- Produces: `Session.require_idle() -> None`, raises `RouterError("busy")` when `running()` is true. `start()` calls it; `/api/connect`, `/api/apply`, `/api/clear` call it before touching the router.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_server_jobs.py`:

```python
@pytest.mark.parametrize("path,body", [
    ("/api/apply", {"lte": ["7"]}),
    ("/api/clear", {}),
    ("/api/connect", {"url": "192.168.8.1", "password": "pw"}),
])
def test_nothing_touches_the_router_while_a_job_runs(live, path, body):
    """The page greys these buttons out, but the page is a mirror. A write that lands mid-scan
    pollutes the measurement in progress and is then overwritten by the scan's own lock."""
    session, port = live
    connect(port, session)
    session.thread = type("Alive", (), {"is_alive": lambda self: True})()
    status, answer = call(port, "POST", path, body, token=session.token)
    assert (status, answer["error"]) == (409, "busy")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_server_jobs.py::test_nothing_touches_the_router_while_a_job_runs -v`
Expected: three FAILs, each `(200, ...) != (409, 'busy')` (the answer has no `"error"` key, so `KeyError: 'error'` also counts as failing).

- [ ] **Step 3: Add `require_idle` and call it**

In `src/cpe_band_scan/server.py`, inside `class Session`, replace `start`'s guard so the rule lives in one method:

```python
    def require_idle(self) -> None:
        if self.running():
            raise RouterError("busy")

    def start(self, kind: str, make_events):
        """Run an event generator on a worker thread. One job at a time, always."""
        with self._lock:
            self.require_idle()
            self.events, self.kind, self.cancelled = [], kind, False
            self.thread = threading.Thread(target=self._drive, args=(make_events,), daemon=True)
            self.thread.start()
```

In `do_POST`, add `self.session.require_idle()` as the first line inside each of these three branches:

```python
            if path == "/api/connect":
                self.session.require_idle()
                device = self.session.connect(...
```
```python
            if path == "/api/apply":
                self.session.require_idle()
                router = self.session.require_router()
```
```python
            if path == "/api/clear":
                self.session.require_idle()
                lockfreq.lock(self.session.require_router())
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/cpe_band_scan/server.py tests/test_server_jobs.py
```
```bash
git commit -m "fix: apply, clear and connect are refused while a scan or test runs"
```

---

### Task 3: The API validates what it is given

Closes findings 7 and 13.

**Files:**
- Modify: `src/cpe_band_scan/lockfreq.py` (new `bands_of`, `band_info`)
- Modify: `src/cpe_band_scan/copy.py` (`ERRORS`)
- Modify: `src/cpe_band_scan/server.py` (`do_GET`, `do_POST`)
- Modify: `src/cpe_band_scan/cli.py` (`main`)
- Test: `tests/test_lockfreq.py`, `tests/test_server_jobs.py`, `tests/test_server.py`, `tests/test_copy.py`

**Interfaces:**
- Produces: `lockfreq.bands_of(value) -> list[str]`, raising `ValueError` for anything that is not an iterable of band numbers (a bare string is refused). `band_info` calls it for both arguments, so every lock write in the codebase is covered.
- Produces: `copy.ERRORS["bad_request"]` with a `{detail}` placeholder; the server answers `400 {"error": "bad_request"}` on any `ValueError` raised while handling a request.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lockfreq.py`:

```python
import pytest


@pytest.mark.parametrize("given", ["78", b"78", 78, None, ["7x"], [""], [{"band": "7"}]])
def test_anything_but_a_list_of_band_numbers_is_refused(given):
    """`"78"` iterates to "7" and "8", which would lock two bands nobody asked for. The
    write path is the one place every caller passes through, so it is where this is checked."""
    with pytest.raises(ValueError):
        band_info(given)


def test_band_numbers_may_arrive_as_ints_or_strings():
    assert band_info([7, "40"])["all_bands"] == "7,40"
```

Append to `tests/test_server_jobs.py`:

```python
@pytest.mark.parametrize("live", [_APPLY_FACTORY], indirect=True)
def test_a_string_band_is_refused_before_it_reaches_the_router(live):
    session, port = live
    connect(port, session)
    before = len(_APPLY_FAKE.posts)
    status, answer = call(port, "POST", "/api/apply", {"lte": "78"}, token=session.token)
    assert (status, answer["error"]) == (400, "bad_request")
    assert len(_APPLY_FAKE.posts) == before, "the router must not have been written to"


def test_an_unknown_side_is_refused_before_a_scan_starts(live):
    session, port = live
    connect(port, session)
    status, answer = call(port, "POST", "/api/scan", {"sides": ["wifi"]}, token=session.token)
    assert (status, answer["error"]) == (400, "bad_request")
    assert not session.running()


@pytest.mark.parametrize("body", [{"seconds": 0}, {"gap": 0}, {"seconds": 10, "gap": 20},
                                  {"seconds": "soon"}])
def test_a_test_with_impossible_timing_is_refused(live, body):
    session, port = live
    connect(port, session)
    status, answer = call(port, "POST", "/api/test", body, token=session.token)
    assert (status, answer["error"]) == (400, "bad_request")
```

Append to `tests/test_server.py`:

```python
def test_a_non_numeric_since_is_a_bad_request_not_a_crash(live):
    session, port = live
    status, answer = call(port, "GET", "/api/events?since=abc", token=session.token)
    assert (status, answer["error"]) == (400, "bad_request")
```

In `tests/test_copy.py`, add `"bad_request"` to the parametrize list of `test_every_failure_the_engine_can_raise_has_a_message` (it currently ends `"busy", "not_connected", "no_results", "crash"]`; make it `"busy", "not_connected", "no_results", "crash", "bad_request"]`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_lockfreq.py tests/test_server_jobs.py tests/test_server.py tests/test_copy.py -q`
Expected: the new tests FAIL (`DID NOT RAISE`, `(200, ...)`, `KeyError: 'bad_request'`); everything else passes.

- [ ] **Step 3: Validate on the write path**

In `src/cpe_band_scan/lockfreq.py`, add above `band_info` and change `band_info`'s first lines:

```python
def bands_of(value) -> list[str]:
    """Band numbers as strings. A bare string is refused rather than iterated: "78" would
    otherwise become bands 7 and 8."""
    if isinstance(value, (str, bytes)) or not hasattr(value, "__iter__"):
        raise ValueError(f"bands must be a list of numbers, got {value!r}")
    bands = [str(band).strip() for band in value]
    if not all(band.isdigit() for band in bands):
        raise ValueError(f"not band numbers: {value!r}")
    return bands


def band_info(bands, scell=()) -> OrderedDict:
    bands, scell = bands_of(bands), bands_of(scell)
    if not bands:
        return OrderedDict(lock_mode="0", freq_infos={}, all_bands="")
    every = sorted({*bands, *scell}, key=int)
    return OrderedDict(lock_mode="3",
                       freq_infos={"freq_info": [{"band": b} for b in bands]},
                       all_bands=",".join(every))
```

- [ ] **Step 4: Give the refusal a sentence**

In `src/cpe_band_scan/copy.py`, add to `ERRORS`, after `"not_connected"`:

```python
    "bad_request": "CPE Band Scan got a request it can't act on ({detail}). Reload the page and "
                   "try again.",
```

- [ ] **Step 5: Turn `ValueError` into a 400 and check sides and timing**

In `src/cpe_band_scan/server.py`:

In `do_GET`, replace the `/api/events` branch's first line

```python
                since = int(parse_qs(urlparse(self.path).query).get("since", ["0"])[0])
```

with

```python
                since = max(0, int(parse_qs(urlparse(self.path).query).get("since", ["0"])[0]))
```

and add, after `do_GET`'s `except RouterError as error:` clause and before the closing `self._json({"error": "not_found"}, 404)`:

```python
        except ValueError as error:
            return self._fail("bad_request", 400, detail=str(error))
```

In `do_POST`, replace the `/api/scan` branch's two lines

```python
                sides = tuple(body.get("sides") or ("lte", "nr"))
                bands = body.get("bands") or None
```

with

```python
                sides = tuple(body.get("sides") or ("lte", "nr"))
                if any(side not in scanner.OTHER for side in sides):
                    raise ValueError(f"sides {sides!r}")
                bands = lockfreq.bands_of(body.get("bands") or []) or None
```

Replace the `/api/test` branch's timing line

```python
                seconds, gap = int(body.get("seconds") or 120), int(body.get("gap") or 10)
```

with

```python
                seconds = int(body["seconds"]) if "seconds" in body else 120
                gap = int(body["gap"]) if "gap" in body else 10
                if not 0 < gap <= seconds:
                    raise ValueError(f"seconds={seconds} gap={gap}")
```

(`or 120` would turn a sent `0` into the default and hide it; `int("soon")` raises `ValueError` on its own.)

Add, after `do_POST`'s `except RouterError as error:` clause and before its closing `self._json({"error": "not_found"}, 404)`:

```python
        except ValueError as error:
            return self._fail("bad_request", 400, detail=str(error))
```

- [ ] **Step 6: The terminal gets the same sentence**

In `src/cpe_band_scan/cli.py`, in `main`, add before the `except KeyboardInterrupt:` clause:

```python
    except ValueError as error:
        print(copy.text("ERRORS", "bad_request", detail=str(error)), file=sys.stderr)
        return 2
```

- [ ] **Step 7: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/cpe_band_scan/lockfreq.py src/cpe_band_scan/copy.py src/cpe_band_scan/server.py src/cpe_band_scan/cli.py tests/test_lockfreq.py tests/test_server_jobs.py tests/test_server.py tests/test_copy.py
```
```bash
git commit -m "fix: band lists, sides and timings are checked before anything reaches the router"
```

---

### Task 4: A router that disappears mid-session is "unreachable", not a crash

Closes finding 5.

**Files:**
- Modify: `src/cpe_band_scan/router.py` (`_session`, `get`, `post`, new `_unreachable`)
- Modify: `src/cpe_band_scan/server.py` (`Session._drive`)
- Test: `tests/test_router.py`, `tests/test_server_jobs.py`

**Interfaces:**
- Produces: `Router.get` and `Router.post` raise `RouterError("unreachable", detail)` on any `OSError` during the request, the same code login already uses. The job thread's error event fills `{url}` with the router's url.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_router.py`:

```python
def test_a_timeout_mid_session_is_reported_as_unreachable():
    """Login worked minutes ago; now the router is off. requests raises an OSError subclass
    from inside get(), and the person should read the same sentence as for a wrong address."""
    session = FakeSession({"device/signal": OSError("timed out")})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "unreachable"


def test_a_write_to_a_router_that_went_away_is_reported_as_unreachable():
    session = FakeSession({"POST net/lock-freq": OSError("connection reset")})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    with pytest.raises(RouterError) as caught:
        router.post("net/lock-freq", OrderedDict())
    assert caught.value.code == "unreachable"
```

Append to `tests/test_server_jobs.py`:

```python
@pytest.mark.parametrize("live", [fake_router_factory({"device/signal": OSError("timed out")})],
                         indirect=True)
def test_a_router_lost_mid_scan_reads_as_unreachable_with_its_address(live, monkeypatch):
    """Signing in worked; the first signal read times out. The person should read the same
    sentence as for a wrong address, and it must name the router rather than end in 'at .'."""
    monkeypatch.setattr(server, "SLEEP", lambda seconds: None)
    session, port = live
    connect(port, session)
    call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["7"]}, token=session.token)
    events = drain(port, session)
    error = next(event for event in events if event["type"] == "error")
    assert error["code"] == "unreachable"
    assert "192.168.8.1" in error["message"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_router.py tests/test_server_jobs.py::test_a_router_lost_mid_scan_reads_as_unreachable_with_its_address -q`
Expected: the two router tests FAIL with `OSError` escaping (`DID NOT RAISE RouterError`); the server test FAILS with `'crash' == 'unreachable'`.

- [ ] **Step 3: One translation for `OSError`, used three times**

In `src/cpe_band_scan/router.py`, add above `class Router`:

```python
def _unreachable(error: OSError) -> RouterError:
    # requests' errors subclass OSError: refused, timed out, no route, connection reset
    return RouterError("unreachable", f"{type(error).__name__}: {error}")
```

In `_session`, replace

```python
        except OSError as error:  # requests' errors subclass OSError: refused, timed out, no route
            raise RouterError("unreachable", f"{type(error).__name__}: {error}") from error
```

with

```python
        except OSError as error:
            raise _unreachable(error) from error
```

In `get` and in `post`, add after each `except hx.ResponseErrorException as error:` clause:

```python
            except OSError as error:
                raise _unreachable(error) from error
```

- [ ] **Step 4: The job thread fills in the url**

In `src/cpe_band_scan/server.py`, in `Session._drive`, the `RouterError` branch becomes:

```python
        except RouterError as error:
            self.events.append({"type": "error", "code": error.code, "detail": error.detail,
                                "message": copy.text("ERRORS", error.code, detail=error.detail,
                                                     url=getattr(self.router, "url", ""))})
```

The crash branch is unchanged: with step 3 in place every `OSError` from the router already arrives here as `RouterError("unreachable")`.

- [ ] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/cpe_band_scan/router.py src/cpe_band_scan/server.py tests/test_router.py tests/test_server_jobs.py
```
```bash
git commit -m "fix: a router that goes away mid-session reads as unreachable, with its address"
```

---

### Task 5: A test stopped before its first sample ends quietly

Closes finding 4.

**Files:**
- Modify: `src/cpe_band_scan/scanner.py` (`trace`)
- Test: `tests/test_scanner.py`

**Interfaces:**
- Produces: `trace()` yields `trace_start`, `cancelled` and then returns when no sample was taken. `trace_done` is only yielded with at least one sample. The server's `finished` event still follows either way.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scanner.py`:

```python
def test_a_test_stopped_before_its_first_sample_ends_without_a_summary():
    """summarise([]) used to raise IndexError here, which the page showed as 'an unexpected
    problem' for the most ordinary thing a person can do: press Stop straight away."""
    router, _ = build([signal(8)])
    events = list(scanner.trace(router, seconds=20, gap=10,
                                cancelled=lambda: True, sleep=lambda s: None))
    assert [event["type"] for event in events] == ["trace_start", "cancelled"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scanner.py::test_a_test_stopped_before_its_first_sample_ends_without_a_summary -v`
Expected: FAIL with `IndexError: list index out of range`.

- [ ] **Step 3: Return before summarising nothing**

In `src/cpe_band_scan/scanner.py`, in `trace`, insert after the `for` loop and before `summary = metrics.summarise(rows)`:

```python
    if not rows:
        return
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/cpe_band_scan/scanner.py tests/test_scanner.py
```
```bash
git commit -m "fix: stopping a test before its first sample no longer crashes it"
```

---

### Task 6: A saved run's id is always one the store minted

Closes finding 6.

**Files:**
- Modify: `src/cpe_band_scan/store.py` (`save`)
- Test: `tests/test_store.py`

**Interfaces:**
- Produces: `store.save(run, name)` keeps a supplied `id` only when it matches `RUN_ID`; otherwise it mints a new one. The file always lands in `runs_dir()`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_store.py`:

```python
def test_a_run_with_a_made_up_id_is_saved_under_a_minted_one(home):
    """load, rename and delete already refuse an id that is not ours; save must too, or a
    request with id "../x" writes outside the runs folder."""
    saved = store.save(dict(RUN, id="../escaped"))
    assert store.RUN_ID.match(saved["id"])
    assert not (home / "escaped.json").exists()
    assert [path.parent for path in home.rglob("*.json")] == [home / "runs"]


def test_a_run_saved_again_keeps_its_own_id(home):
    first = store.save(RUN)
    assert store.save(first)["id"] == first["id"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_store.py -q`
Expected: the first new test FAILS (`escaped.json` exists in `home`); the second passes already and stays as the guard that re-saving is still allowed.

- [ ] **Step 3: Keep only ids that match**

In `src/cpe_band_scan/store.py`, in `save`, replace

```python
    stored["id"] = stored.get("id") or _unique_id(when)
```

with

```python
    given = str(stored.get("id") or "")
    stored["id"] = given if RUN_ID.match(given) else _unique_id(when)
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/cpe_band_scan/store.py tests/test_store.py
```
```bash
git commit -m "fix: a saved run can only land in the runs folder"
```

---

### Task 7: The terminal: no `--password`, bare bands are 4G, apply says what is true

Closes findings 8, 9 and 10.

**Files:**
- Modify: `src/cpe_band_scan/cli.py` (`parse`, `read_password`, new `scan_target`, `main`)
- Modify: `src/cpe_band_scan/copy.py` (`PROGRESS`)
- Modify: `skills/bandscan/SKILL.md` (the "Password in the URL" row of Common mistakes)
- Test: `tests/test_cli.py`, `tests/test_packaging.py`

**Interfaces:**
- Produces: `cli.scan_target(args) -> tuple[tuple[str, ...], list[str]]`. `scan` → `(("lte", "nr"), [])`; `scan 4g` → `(("lte",), [])`; `scan 5g 78` → `(("nr",), ["78"])`; `scan 7 40` → `(("lte",), ["7", "40"])`.
- Produces: `copy.PROGRESS["lock_written"]` with a `{bands}` placeholder. The CLI `apply` command prints it instead of `PROGRESS["applied"]`.
- Removes: the `--password` argument. `read_password` reads `CPE_BAND_SCAN_PASSWORD`, then `.env`, then prompts.

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli.py`, delete the helper `_scan_sides_and_bands` and the four tests that use it (`test_scan_with_no_arguments_covers_both_sides_and_every_band`, `test_scan_with_a_side_alone_covers_only_that_side`, `test_scan_with_bare_band_numbers_covers_both_sides_with_those_bands`, `test_scan_with_a_side_and_band_numbers_covers_that_side_with_those_bands`). They re-implemented the CLI's own logic, which is exactly how a wrong rule got a passing test. Replace them with:

```python
@pytest.mark.parametrize("argv,expected", [
    (["scan"], (("lte", "nr"), [])),
    (["scan", "4g"], (("lte",), [])),
    (["scan", "5g"], (("nr",), [])),
    (["scan", "5g", "78"], (("nr",), ["78"])),
    (["scan", "4g", "7", "40"], (("lte",), ["7", "40"])),
    (["scan", "7", "40"], (("lte",), ["7", "40"])),
])
def test_scan_target_reads_the_side_and_the_bands(argv, expected):
    """Bare band numbers are 4G bands. Sending them to the 5G side as well meant N7 and N40,
    two minutes of refusals nobody asked for."""
    assert cli.scan_target(cli.parse(argv)) == expected


def test_the_password_cannot_be_passed_on_the_command_line():
    """argv is visible in ps and lands in shell history, which is disk."""
    with pytest.raises(SystemExit):
        cli.parse(["--password", "x", "status"])


def test_apply_tells_the_truth_about_the_next_30_seconds(monkeypatch, capsys):
    from cpe_band_scan.router import Router
    from tests.fakes import FakeSession, factory
    from tests.test_scanner import DEVICE
    router = Router("192.168.8.1", "pw", connection_factory=factory(FakeSession()))
    monkeypatch.setattr(cli, "connect", lambda args: (router, DEVICE))
    assert cli.main(["apply", "7", "--scell", "3"]) == 0
    out = capsys.readouterr().out
    assert copy.text("PROGRESS", "lock_written", bands="7") in out
    assert "connection is back" not in out
```

Append to `tests/test_packaging.py`:

```python
def test_the_skill_never_recommends_the_password_on_the_command_line():
    skill = (ROOT / "skills" / "bandscan" / "SKILL.md").read_text(encoding="utf-8")
    assert "--password" not in skill
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py tests/test_packaging.py -q`
Expected: `scan_target` tests FAIL with `AttributeError`; the password test FAILS with `DID NOT RAISE`; the apply test FAILS with `KeyError: 'lock_written'` or a missing sentence; the skill test FAILS.

- [ ] **Step 3: Remove the flag, add `scan_target`, use it**

In `src/cpe_band_scan/cli.py`:

Delete the line `parser.add_argument("--password", default=None)` from `parse`.

In `read_password`, delete the two lines

```python
    if getattr(args, "password", None):
        return args.password
```

Add after `connect`:

```python
def scan_target(args) -> tuple[tuple[str, ...], list[str]]:
    """Which sides to scan and which bands. Bare band numbers are 4G bands; the 5G side is
    scanned only when asked for with `5g`, because N7 for B7 is never what was meant."""
    words = list(args.args)
    side = words.pop(0) if words and words[0] in ("4g", "5g") else None
    if side:
        return {"4g": ("lte",), "5g": ("nr",)}[side], words
    return (("lte",) if words else ("lte", "nr")), words
```

In `main`, replace the three lines at the top of the `elif command == "scan":` branch

```python
            side = args.args[0] if args.args and args.args[0] in ("4g", "5g") else None
            bands = args.args[1:] if side else args.args
            sides = {"4g": ("lte",), "5g": ("nr",)}.get(side, ("lte", "nr"))
```

with

```python
            sides, bands = scan_target(args)
```

In the `elif command == "apply":` branch, replace

```python
            print(copy.text("PROGRESS", "applied", bands=args.bands))
```

with

```python
            print(copy.text("PROGRESS", "lock_written", bands=args.bands))
```

- [ ] **Step 4: The sentence**

In `src/cpe_band_scan/copy.py`, add to `PROGRESS` directly after `"applied"`:

```python
    "lock_written": "Locked to {bands}. The connection drops for about 30 seconds while the router "
                    "re-attaches, then comes back.",
```

- [ ] **Step 5: The skill stops recommending the flag**

In `skills/bandscan/SKILL.md`, in the Common mistakes table, change the row

```
| Password in the URL (`http://admin:p@ss@ip/`) | Symbols break URL parsing. `.env` or `--password` only. |
```

to

```
| Password in the URL (`http://admin:p@ss@ip/`) or on the command line | Symbols break URL parsing, and argv lands in shell history. `.env`, `CPE_BAND_SCAN_PASSWORD`, or the prompt only. |
```

- [ ] **Step 6: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/cpe_band_scan/cli.py src/cpe_band_scan/copy.py skills/bandscan/SKILL.md tests/test_cli.py tests/test_packaging.py
```
```bash
git commit -m "fix: the terminal takes no password flag, scans bare bands on 4G only, and says what apply does"
```

---

### Task 8: Every error sentence has a caller

Closes finding 11.

**Files:**
- Modify: `src/cpe_band_scan/copy.py` (`ERRORS`)
- Test: `tests/test_copy.py`

**Interfaces:**
- Removes: `copy.ERRORS["no_results"]`, `copy.ERRORS["band_refused"]`. Nothing in `src/` raises or renders them (verified: `grep -rn 'no_results\|band_refused' src tests` finds them only in `copy.py` and `test_copy.py`).

- [ ] **Step 1: Write the failing test and drop the two codes from the old tests**

Append to `tests/test_copy.py`:

```python
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "cpe_band_scan"
CALLERS = "".join(path.read_text(encoding="utf-8") for path in SRC.rglob("*")
                  if path.suffix in (".py", ".js") and path.name != "copy.py")


def test_every_error_sentence_is_raised_somewhere():
    """A sentence nobody raises is a sentence nobody maintains; two of them still claimed the
    router was back on automatic long after that stopped being true."""
    for code in copy.ERRORS:
        assert f'"{code}"' in CALLERS, f"ERRORS[{code!r}] has no caller"
```

In the same file:
- delete the line `NO_ACTION_NEEDED = {"band_refused"}   # the scan handles this itself; the person does nothing`;
- in `test_every_error_ends_with_something_the_person_can_do`, delete the two lines `if code in NO_ACTION_NEEDED:` / `continue`;
- in the parametrize list of `test_every_failure_the_engine_can_raise_has_a_message`, remove `"band_refused"` and `"no_results"`;
- in `test_no_message_claims_a_crash_or_a_dead_scan_leaves_the_router_on_automatic`, change `for code in ("crash", "no_results"):` to `for code in ("crash",):`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_copy.py -q`
Expected: `test_every_error_sentence_is_raised_somewhere` FAILS naming `no_results` (or `band_refused`); the rest pass.

- [ ] **Step 3: Delete the two entries**

In `src/cpe_band_scan/copy.py`, delete the `"band_refused"` entry and the `"no_results"` entry from `ERRORS`.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/cpe_band_scan/copy.py tests/test_copy.py
```
```bash
git commit -m "fix: drop the two error sentences nothing raises, and guard against a third"
```

---

### Task 9: The name you typed survives a re-render

Closes finding 12.

**Files:**
- Modify: `src/cpe_band_scan/web/app.js` (`state`, `saveCard`, `onScan`, `onTest`)
- Test: `tests/test_parity.py`

**Interfaces:**
- Produces: `state.runName` (string or `null`). `saveCard()` shows `state.runName ?? state.suggestedName`, updates `state.runName` on every `input` event, and a new scan or test resets it to `null`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_parity.py`:

```python
def test_the_typed_run_name_is_kept_in_state_not_only_in_the_input():
    """render() rebuilds every element, so an input's value lives only as long as the next
    render. Refresh, apply and the poll all render; the typed name must be in state."""
    body = re.search(r"function saveCard\(\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert "state.runName" in body, "saveCard() does not read the typed name back"
    assert re.search(r'addEventListener\(\s*"input"', body), "saveCard() never records typing"
    for name in ("onScan", "onTest"):
        start = re.search(rf"async function {name}\([^)]*\)\s*\{{(.*?)\n\}}", APP_JS, re.S).group(1)
        assert re.search(r"state\.runName\s*=\s*null", start), f"{name}() keeps a stale name"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_parity.py::test_the_typed_run_name_is_kept_in_state_not_only_in_the_input -v`
Expected: FAIL on the first assertion.

- [ ] **Step 3: Keep the name in state**

In `src/cpe_band_scan/web/app.js`:

In `state`, change `viewing: null, suggestedName: "",` to `viewing: null, suggestedName: "", runName: null,`.

In `onScan`, after `state.run = null;` add a line `state.runName = null;`. In `onTest`, change `state.events = []; state.since = 0; state.run = null; state.pollFailures = 0;` to `state.events = []; state.since = 0; state.run = null; state.runName = null; state.pollFailures = 0;`.

Replace the `input` construction in `saveCard` with:

```js
  const input = el("input", { type: "text", id: "run_name",
                              value: state.runName ?? state.suggestedName ?? "",
                              placeholder: copy.FIELDS.run_name.placeholder });
  input.addEventListener("input", () => { state.runName = input.value; });
```

- [ ] **Step 4: Check it in the browser**

Run: `.venv/bin/cpe-band-scan ui --no-browser --port 8799` from the repo root, open `http://127.0.0.1:8799/` in the built-in browser, and confirm the page loads with no console error (the connect screen is enough: `saveCard` is parsed at load). Stop the server with Ctrl-C. Then run the suite:

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/cpe_band_scan/web/app.js tests/test_parity.py
```
```bash
git commit -m "fix: the run name you typed is still there after the page redraws"
```

---

### Task 10: Anyone can install and start it

Closes finding 3.

**Files:**
- Modify: `run-cpe-band-scan.command`, `run-cpe-band-scan.bat`
- Modify: `README.md` (Install section)
- Test: `tests/test_packaging.py`

**Interfaces:**
- Produces: launchers that create `.venv` beside themselves on first run, install the app into it, and start `cpe-band-scan ui` from it. A README that never names a PyPI package.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_packaging.py`:

```python
import os


def test_the_mac_launcher_runs_from_its_own_venv_and_is_executable():
    """The system python3 has no cpe_band_scan module; the launcher must make its own."""
    launcher = ROOT / "run-cpe-band-scan.command"
    text = launcher.read_text(encoding="utf-8")
    assert "python3 -m venv .venv" in text
    assert ".venv/bin/cpe-band-scan ui" in text
    assert "python3 -m cpe_band_scan" not in text
    assert os.access(launcher, os.X_OK), "double-clicking needs the executable bit"


def test_the_windows_launcher_runs_from_its_own_venv():
    text = (ROOT / "run-cpe-band-scan.bat").read_text(encoding="utf-8")
    assert "python -m venv .venv" in text
    assert ".venv\\Scripts\\cpe-band-scan ui" in text
    assert "python -m cpe_band_scan" not in text


def test_the_readme_never_promises_a_package_that_is_not_published():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pipx install cpe-band-scan" not in readme
    assert "pip install --user cpe-band-scan" not in readme
    assert "run-cpe-band-scan.command" in readme and "run-cpe-band-scan.bat" in readme
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_packaging.py -q`
Expected: the three new tests FAIL.

- [ ] **Step 3: Rewrite the launchers**

Replace the whole of `run-cpe-band-scan.command` with:

```sh
#!/bin/sh
# First run: make a private Python environment next to the app and install into it.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/cpe-band-scan ]; then
  python3 -m venv .venv && .venv/bin/pip install -q . || exit 1
fi
exec .venv/bin/cpe-band-scan ui
```

Then: `chmod +x run-cpe-band-scan.command` (git records the mode).

Replace the whole of `run-cpe-band-scan.bat` with:

```bat
@echo off
rem First run: make a private Python environment next to the app and install into it.
cd /d "%~dp0"
if not exist .venv\Scripts\cpe-band-scan.exe (
  python -m venv .venv && .venv\Scripts\pip install -q . || exit /b 1
)
.venv\Scripts\cpe-band-scan ui
pause
```

- [ ] **Step 4: Rewrite the README's Install section**

In `README.md`, replace everything from `## Install` up to (not including) `## Use it` with:

````markdown
## Install

CPE Band Scan isn't on PyPI yet, so it installs from this folder. You need Python 3.10 or newer.

**Double-click** `run-cpe-band-scan.command` (macOS) or `run-cpe-band-scan.bat` (Windows). The
first run builds a private Python environment next to the app, which takes about a minute; after
that it opens straight away.

Or, from a terminal in this folder:

```bash
pipx install .
```

No pipx? `python3 -m pip install --user .` works too.

````

Also in the "From the terminal instead" section, the sentence `The password comes from ...` already lists the environment variable, `.env` and the prompt; leave it. Under "Using it with an assistant", the skill's own text (Task 7) no longer names `--password`; nothing to change here.

- [ ] **Step 5: Prove the install path works with only the system Python**

One Bash call, no `cd`, run from the repo root. It copies the tracked tree to a fresh folder and does exactly what the launcher's `if` block does, using `/usr/bin/env python3` (the interpreter a double-click gets), then runs `help` instead of `ui` so it exits:

```bash
tmp=$(mktemp -d); git archive HEAD | tar -x -C "$tmp"; /usr/bin/env python3 -m venv "$tmp/.venv" && "$tmp/.venv/bin/pip" install -q "$tmp" && "$tmp/.venv/bin/cpe-band-scan" help | head -3; rm -rf "$tmp"
```

Expected: the first three lines of `cpe-band-scan help` (`CPE Band Scan — Find the band ...`). If `python3 -m venv` fails, the machine has no usable system Python and the README's "Python 3.10 or newer" line is the answer, not a code change.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add run-cpe-band-scan.command run-cpe-band-scan.bat README.md tests/test_packaging.py
```
```bash
git commit -m "fix: the launchers build their own environment, and the README installs from the folder"
```

---

### Task 11: Choose what to scan, then press Start

Closes U1.

**Files:**
- Modify: `src/cpe_band_scan/copy.py` (`FIELDS`, `ACTIONS`)
- Modify: `src/cpe_band_scan/cli.py` (`_print_help`)
- Modify: `src/cpe_band_scan/web/app.js` (`state`, `el`, `help`, `scanControls`, new `SCOPES`)
- Test: `tests/test_copy.py`, `tests/test_parity.py`, `tests/test_cli.py`

**Interfaces:**
- Produces: `copy.FIELDS["scan_scope"]` = `{"label", "placeholder", "help", "options": {"all": {"label", "help"}, "lte": {...}, "nr": {...}}}`. The option keys are the scope keys the page maps to sides.
- Produces: `copy.ACTIONS["scan"]` (label "Start the scan"). Removes `ACTIONS["scan_all"]`, `["scan_4g"]`, `["scan_5g"]`.
- Produces in `app.js`: `state.scope` (one of `"all" | "lte" | "nr"`, default `"all"`), `SCOPES = { all: ["lte", "nr"], lte: ["lte"], nr: ["nr"] }`, `helpFor(entry, label)` (the `?` button for any catalogue entry; `help(group, key)` calls it), and `el()` binds any attribute starting with `on` as a listener.

- [ ] **Step 1: Write the failing tests**

In `tests/test_copy.py`, add `"start"` to `BUTTON_VERBS` (it currently reads `("connect", "scan", "test", "use", "switch", "stop", "save", "open", "rename", "delete", "refresh")`; append `"start"`). Then append:

```python
def test_the_scan_scope_offers_all_4g_and_5g_and_each_explains_itself():
    options = copy.FIELDS["scan_scope"]["options"]
    assert list(options) == ["all", "lte", "nr"]
    for key, option in options.items():
        assert option["label"].strip() and option["help"].strip(), f"scan_scope.{key} is unexplained"


def test_there_is_one_scan_button_not_three():
    assert "scan" in copy.ACTIONS
    assert not {"scan_all", "scan_4g", "scan_5g"} & set(copy.ACTIONS)
```

Append to `tests/test_parity.py`:

```python
def test_the_scope_is_chosen_with_native_radios_and_one_start_button():
    """One primary action per screen: the person picks all / 4G / 5G, then presses Start.
    Native radios inside a fieldset keep the keyboard and screen-reader behaviour for free."""
    body = re.search(r"function scanControls\(\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'type: "radio"' in body and 'name: "scan_scope"' in body
    assert '"fieldset"' in body and '"legend"' in body
    assert 'action("scan"' in body
    assert not re.search(r"scan_(all|4g|5g)", APP_JS), "the three old scan buttons are back"


def test_every_scope_option_label_comes_from_the_catalogue():
    for key, option in copy.FIELDS["scan_scope"]["options"].items():
        assert option["label"] not in LITERALS, f"scan_scope.{key} is hardcoded in app.js"
```

Append to `tests/test_cli.py`:

```python
def test_help_explains_each_scan_scope_in_the_catalogue_s_words(capsys):
    cli.main(["help"])
    out = capsys.readouterr().out
    for option in copy.FIELDS["scan_scope"]["options"].values():
        assert option["help"] in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_copy.py tests/test_parity.py tests/test_cli.py -q`
Expected: the five new tests FAIL (`KeyError: 'scan_scope'`, missing `"radio"`, and so on). Everything else passes.

- [ ] **Step 3: The words**

In `src/cpe_band_scan/copy.py`, add to `FIELDS` after `"run_name"`:

```python
    "scan_scope": {
        "label": "What to scan",
        "placeholder": "",
        "help": "Which bands the scan measures. All bands is the full picture. On a 5G NSA network "
                "the 4G bands decide most, because the 5G carrier follows the 4G band the router is "
                "anchored to.",
        "options": {
            "all": {"label": "All bands",
                    "help": "Every 4G band, then every 5G band. Takes 20 to 30 minutes."},
            "lte": {"label": "4G bands only",
                    "help": "The 4G bands. On a 5G NSA network this is the scan that matters, because "
                            "the 5G carrier follows whichever 4G band the router is anchored to. "
                            "Takes 10 to 15 minutes."},
            "nr": {"label": "5G bands only",
                   "help": "The 5G bands. Useful to see which 5G bands are on air here. Takes 5 to "
                           "10 minutes."},
        },
    },
```

In `ACTIONS`, delete the `"scan_all"`, `"scan_4g"` and `"scan_5g"` entries and put in their place:

```python
    "scan": {
        "label": "Start the scan",
        "help": "Locks each band you chose in turn and measures it for about a minute, then ranks "
                "them. Your connection drops for about half a minute every time the band changes.",
    },
```

- [ ] **Step 4: The terminal's help table reads the same words**

In `src/cpe_band_scan/cli.py`, in `_print_help`, replace the three rows

```python
            ("scan", copy.ACTIONS["scan_all"]["help"]),
            ("scan 4g", copy.ACTIONS["scan_4g"]["help"]),
            ("scan 5g", copy.ACTIONS["scan_5g"]["help"]),
```

with

```python
            ("scan", copy.FIELDS["scan_scope"]["options"]["all"]["help"]),
            ("scan 4g", copy.FIELDS["scan_scope"]["options"]["lte"]["help"]),
            ("scan 5g", copy.FIELDS["scan_scope"]["options"]["nr"]["help"]),
```

- [ ] **Step 5: The page**

In `src/cpe_band_scan/web/app.js`:

In `state`, add `scope: "all",` after `runName: null,`.

In `el`, replace the line `if (key === "onclick") node.addEventListener("click", value);` with
`if (key.startsWith("on")) node.addEventListener(key.slice(2), value);`.

Replace the whole `help` function with:

```js
function helpFor(entry, label) {
  const button = el("button", {
    class: "help", type: "button", "aria-label": `What is ${label}?`,
  }, "?");
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    showHelp(entry.help, button);
  });
  return button;
}

function help(group, key) {
  const button = helpFor(copy[group][key], labelFor(group, key) || key);
  button.setAttribute("data-help", `${group}.${key}`);
  return button;
}
```

Replace `const SIDES = { all: ["lte", "nr"], "4g": ["lte"], "5g": ["nr"] };` and the whole `scanControls` function with:

```js
const SCOPES = { all: ["lte", "nr"], lte: ["lte"], nr: ["nr"] };

function scanControls() {
  const disabled = state.running || state.busy;
  const scope = copy.FIELDS.scan_scope;
  const choices = Object.entries(scope.options).map(([key, option]) =>
    el("label", { class: "choice" },
      el("input", { type: "radio", name: "scan_scope", value: key, disabled,
                    checked: state.scope === key ? "" : null,
                    onchange: () => { state.scope = key; } }),
      option.label, helpFor(option, option.label)));
  return el("div", { class: "card" },
    el("h2", {}, copy.APP.results_heading),
    el("p", { class: "note" }, copy.NOTES.before_scan),
    el("p", { class: "note" }, copy.NOTES.vpn),
    el("fieldset", {},
      el("legend", {}, scope.label, help("FIELDS", "scan_scope")),
      ...choices),
    el("div", { class: "row" },
      action("scan", () => onScan(SCOPES[state.scope]), { class: "primary", disabled })));
}
```

- [ ] **Step 6: A little CSS for the choices**

Append to `src/cpe_band_scan/web/style.css`:

```css
fieldset { border: 0; padding: 0; margin: 0 0 1rem; }
legend { font-weight: 600; padding: 0; margin-bottom: .5rem; }
.choice { display: flex; align-items: center; gap: .5rem; min-height: 2.75rem; font-weight: 400; }
.choice input { width: 1.25rem; height: 1.25rem; margin: 0; accent-color: var(--accent); }
```

- [ ] **Step 7: Look at it**

Start the demo: `.venv/bin/python tools/demo_server.py` (it serves on `http://127.0.0.1:8766/` against a fake router; connect with any password). In the built-in browser: confirm the three radios render with a `?` each, the legend has a `?`, the Start button is disabled while a demo scan runs and re-enabled after, and that picking "5G bands only" then Start yields a 5G table only. Stop the demo with Ctrl-C. Then:

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/cpe_band_scan/copy.py src/cpe_band_scan/cli.py src/cpe_band_scan/web/app.js src/cpe_band_scan/web/style.css tests/test_copy.py tests/test_parity.py tests/test_cli.py
```
```bash
git commit -m "feat: choose what to scan, then press one Start button"
```

---

### Task 12: The page meets the ui-ux-pro-max bar

Closes U2. The rulings under **Design rulings for Tasks 11 and 12** are the spec for this task.

**Files:**
- Create: `docs/design-system.md`
- Modify: `src/cpe_band_scan/web/style.css`
- Modify: `src/cpe_band_scan/web/app.js` (`renderConnect`, `onConnect`, `scanControls`, `resultsTable`, `savedRuns`, `saveCard`)
- Modify: `src/cpe_band_scan/web/index.html` (the banner)
- Create: `tests/test_page_quality.py`

**Interfaces:**
- Consumes: `state.run`, `state.scope`, `helpFor`, `action` from Task 11.
- Produces: CSS custom properties `--motion` (`150ms`) and `--target` (`2.75rem`); class `danger` on the delete button; the connect button has `id="connect"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_page_quality.py`:

```python
"""The rules the page must keep: the ones from the ui-ux-pro-max checklist that a regex can
hold. What a regex cannot hold (contrast, the look at 375px) is checked by eye in Task 12."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src" / "cpe_band_scan" / "web"
CSS = (WEB / "style.css").read_text(encoding="utf-8")
JS = (WEB / "app.js").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")


def test_keyboard_focus_is_visible():
    assert ":focus-visible" in CSS
    assert "outline: none" not in CSS and "outline: 0" not in CSS


def test_motion_is_short_and_can_be_switched_off():
    assert "--motion: 150ms" in CSS
    assert "prefers-reduced-motion" in CSS
    assert not re.search(r"transition:[^;]*(width|height|top|left)", CSS), "animate transform/opacity/colour only"


def test_every_control_meets_the_44px_target():
    assert "--target: 2.75rem" in CSS
    for selector in ("button {", "input[type=text], input[type=password] {", ".choice {"):
        block = CSS[CSS.index(selector):]
        block = block[:block.index("}")]
        assert "min-height: var(--target)" in block, f"{selector} is shorter than 44px"
    assert "button.help::after" in CSS, "the ? button needs its hit area extended"


def test_disabled_controls_are_dimmed_within_the_material_range():
    match = re.search(r"button:disabled\s*\{[^}]*opacity:\s*(\.\d+|0\.\d+)", CSS)
    assert match and 0.38 <= float(match.group(1)) <= 0.5


def test_the_error_banner_is_announced():
    assert re.search(r'<div id="banner" role="alert"', HTML)


def test_table_headers_declare_their_scope():
    assert 'scope: "col"' in JS


def test_delete_is_visually_separated_as_destructive():
    assert re.search(r'class:\s*"quiet danger"', JS)
    assert ".danger" in CSS


def test_only_one_primary_action_on_the_main_screen():
    """Start is primary until there are results; then the best row's Use this band is."""
    controls = re.search(r"function scanControls\(\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert re.search(r'class:\s*state\.run\s*\?\s*""\s*:\s*"primary"', controls)
    save = re.search(r"function saveCard\(\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert "primary" not in save


def test_connect_shows_it_is_working_without_losing_what_was_typed():
    connect = re.search(r"async function onConnect\([^)]*\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert 'getElementById("connect")' in connect and ".disabled = true" in connect
    assert "render()" not in connect.split("finally")[0], "a render mid-connect wipes the password field"


def test_the_design_rulings_are_written_down():
    doc = (WEB.parents[2] / "docs" / "design-system.md").read_text(encoding="utf-8")
    for word in ("system-ui", "one primary", "44", "prefers-reduced-motion"):
        assert word in doc
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_page_quality.py -q`
Expected: most FAIL; `test_disabled_controls_are_dimmed_within_the_material_range` may already pass (`.5`).

- [ ] **Step 3: The stylesheet**

Replace the whole of `src/cpe_band_scan/web/style.css` with:

```css
:root {
  color-scheme: light dark;
  --bg: #ffffff; --fg: #16181d; --muted: #5d6470; --line: #e3e6ea;
  --accent: #1f6feb; --good: #1a7f37; --warn: #9a6700; --bad: #b42318; --card: #f7f8fa;
  --motion: 150ms;            /* colour and shadow only; never width, height or position */
  --target: 2.75rem;          /* 44px: the smallest side of anything you can press */
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #16181d; --fg: #e9ecf1; --muted: #9aa3b0; --line: #2a2f38;
          --accent: #6ea8fe; --good: #4ac26b; --warn: #d4a72c; --bad: #ff7b72; --card: #1d2128; }
}
@media (prefers-reduced-motion: reduce) {
  :root { --motion: 0ms; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); line-height: 1.5; font-size: 1rem; }
#app { max-width: 60rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
h1 { font-size: 1.5rem; font-weight: 600; margin: 0; }
h2 { font-size: 1.125rem; font-weight: 600; margin: 2rem 0 .5rem; }
p.lede { color: var(--muted); margin: .25rem 0 1.5rem; max-width: 46rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: .75rem; padding: 1rem; margin-bottom: 1rem; }
.row { display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; }
label { display: block; font-weight: 600; margin-bottom: .25rem; }
input[type=text], input[type=password] {
  width: 100%; min-height: var(--target); padding: .5rem .75rem; border: 1px solid var(--line);
  border-radius: .5rem; background: var(--bg); color: var(--fg); font-size: 1rem; }
.field { margin-bottom: 1rem; max-width: 26rem; }
button { font: inherit; min-height: var(--target); padding: .5rem 1rem; border-radius: .5rem;
         border: 1px solid var(--line); background: var(--bg); color: var(--fg); cursor: pointer;
         touch-action: manipulation;
         transition: background-color var(--motion) ease-out, border-color var(--motion) ease-out,
                     box-shadow var(--motion) ease-out; }
button:hover { border-color: var(--muted); }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.primary:hover { box-shadow: 0 2px 8px color-mix(in srgb, var(--accent) 40%, transparent); }
button.quiet { border: none; background: none; color: var(--accent); padding: .5rem .5rem; }
button.quiet.danger { color: var(--bad); }
button:disabled { opacity: .45; cursor: not-allowed; }
button.help { position: relative; border-radius: 50%; width: 1.75rem; height: 1.75rem; min-height: 0;
              padding: 0; line-height: 1; font-size: .85rem; color: var(--muted); margin-left: .35rem; }
button.help::after { content: ""; position: absolute; inset: -.5rem; }   /* 1.75rem + 2 × .5rem = 44px */
:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
fieldset { border: 0; padding: 0; margin: 0 0 1rem; }
legend { font-weight: 600; padding: 0; margin-bottom: .5rem; }
.choice { display: flex; align-items: center; gap: .5rem; min-height: var(--target); font-weight: 400; }
.choice input { width: 1.25rem; height: 1.25rem; margin: 0; accent-color: var(--accent); }
.table-scroll { overflow-x: auto; }
.table-scroll th:last-child, .table-scroll td:last-child {
  position: sticky; right: 0; background: var(--card);   /* the primary action stays reachable */
}
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: .5rem; border-bottom: 1px solid var(--line); }
th { font-size: .875rem; color: var(--muted); font-weight: 600; white-space: nowrap; }
tr.best td { background: color-mix(in srgb, var(--accent) 8%, transparent); }
tr.best td:last-child { background: color-mix(in srgb, var(--accent) 8%, transparent); }
.grade-excellent { color: var(--good); font-weight: 600; }
.grade-good { color: var(--good); }
.grade-fair { color: var(--warn); }
.grade-poor, .grade-no5g { color: var(--bad); }
.badge { font-size: .75rem; border: 1px solid var(--line); border-radius: 1rem; padding: .05rem .5rem;
         color: var(--muted); margin-left: .5rem; }
#banner { padding: .75rem 1rem; border-radius: .5rem; margin-bottom: 1rem;
          border: 1px solid var(--line); background: var(--card); }
#banner.bad { border-color: var(--bad); color: var(--bad); }
#popover { position: absolute; max-width: 22rem; background: var(--bg); color: var(--fg);
           border: 1px solid var(--line); border-radius: .5rem; padding: .75rem 1rem;
           box-shadow: 0 8px 24px rgba(0,0,0,.18); font-size: .9rem; z-index: 10; }
.note { color: var(--muted); font-size: .9rem; margin: .5rem 0; }
.log { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85rem;
       max-height: 12rem; overflow: auto; border: 1px solid var(--line); border-radius: .5rem;
       padding: .5rem; background: var(--card); }
progress { width: 100%; height: .5rem; }
```

(The `fieldset`, `legend` and `.choice` rules appended in Task 11 are folded in here; there must be one copy of each.)

- [ ] **Step 4: The page**

In `src/cpe_band_scan/web/index.html`, change `<div id="banner" role="status" hidden></div>` to `<div id="banner" role="alert" hidden></div>`.

In `src/cpe_band_scan/web/app.js`:

In `renderConnect`, change `action("connect", onConnect, { class: "primary" })` to `action("connect", onConnect, { class: "primary", id: "connect" })`.

Replace `onConnect` with:

```js
async function onConnect() {
  showError(null);
  state.busy = true;
  const button = document.getElementById("connect");
  if (button) button.disabled = true;               // in place: a render here would wipe the password
  try {
    const answer = await api("POST", "/api/connect", {
      url: document.getElementById("router_url").value,
      password: document.getElementById("password").value,
    });
    state.device = answer.device;
    state.suggestedName = answer.suggested_name;
    await refreshStatus();
    await refreshRuns();
  } catch (failure) {
    showError(failure.message);
  } finally {
    state.busy = false;
    if (button) button.disabled = false;
    render();
  }
}
```

In `scanControls` (from Task 11), change the Start button's attributes from `{ class: "primary", disabled }` to `{ class: state.run ? "" : "primary", disabled }`.

In `resultsTable`, change the header cells: `COLUMN_KEYS.map((key) => el("th", {}, ...` becomes `COLUMN_KEYS.map((key) => el("th", { scope: "col" }, ...` and `el("th", {}, help("ACTIONS", "apply"))` becomes `el("th", { scope: "col" }, help("ACTIONS", "apply"))`.

In `saveCard`, change `action("save", onSave, { class: "primary" })` to `action("save", onSave, {})`.

In `savedRuns`, change the delete button's `{ class: "quiet", onclick: () => onDeleteRun(row) }` to `{ class: "quiet danger", onclick: () => onDeleteRun(row) }`.

- [ ] **Step 5: Write the rulings down**

Create `docs/design-system.md`:

```markdown
# CPE Band Scan — page design rules

The page's look is decided here, once. `style.css` implements it; `tests/test_page_quality.py`
holds the parts a test can hold.

## Rulings

- **Pattern:** operations tool. Neutral surface, status colours (green / amber / red) always paired
  with a word, data-dense but scannable, one primary action per screen.
- **Typeface:** `system-ui`. The app must work with the router as its only network, so it makes no
  third-party request — no web fonts. Base 16px, line-height 1.5, weights 400 / 500 / 600.
- **Colour:** semantic tokens in `:root` (`--bg --fg --muted --line --accent --good --warn --bad --card`),
  one light set and one dark set, each checked to 4.5:1 for body text.
- **Primary action:** exactly one per screen. Connect screen: Connect. Main screen without results:
  Start the scan. Main screen with results: the best row's "Use this band"; Start becomes secondary.
  Save is never primary. Delete is `.danger`.
- **Touch targets:** 44 px (`--target: 2.75rem`) on the shortest side of anything pressable. The `?`
  button is 1.75rem visually and reaches 44 px through `::after`.
- **Focus:** `:focus-visible` draws a 3 px ring in `--accent`; nothing removes an outline.
- **Motion:** `--motion: 150ms`, ease-out, on colour and shadow only; `prefers-reduced-motion` sets
  it to 0. No decorative motion.
- **Controls:** native. The scope selector is a `fieldset` of radios; the popover closes on Escape
  and on a click outside.
- **Feedback:** the error banner is `role="alert"`; buttons are disabled while their request runs;
  destructive actions confirm first.

## Checked by eye (not by test)

At 375 px and at desktop, light and dark: no horizontal scroll, the sticky "Use this band"
column reachable, contrast of every grade colour against the card.
```

- [ ] **Step 6: Look at it, both sizes, both themes**

Start the demo: `.venv/bin/python tools/demo_server.py`. In the built-in browser at `http://127.0.0.1:8766/`:
1. Desktop, light: connect, start an "All bands" demo scan, wait for the table. Confirm the best row's button is the only blue button on the screen and Start has gone grey.
2. `resize_window` preset `mobile` (375 px): reload; run `document.documentElement.scrollWidth <= window.innerWidth` in the console — must be `true`; scroll the results table sideways and confirm the last column stays put.
3. `resize_window` with `colorScheme: "dark"`: take a screenshot; every grade colour must be readable against the card.
4. Tab through the connect screen from the address field: the focus ring must be visible on the field, the `?`, and the button.
Reset with preset `desktop`. Stop the demo with Ctrl-C. Then:

Run: `.venv/bin/python -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add docs/design-system.md src/cpe_band_scan/web/style.css src/cpe_band_scan/web/app.js src/cpe_band_scan/web/index.html tests/test_page_quality.py
```
```bash
git commit -m "feat: the page keeps focus visible, 44px targets, one primary action and no forced motion"
```

---

## Self-review

**Coverage:** findings 1→T1, 2→T2, 3→T10, 4→T5, 5→T4, 6→T6, 7→T3, 8/9/10→T7, 11→T8, 12→T9, 13→T3, U1→T11, U2→T12. All have a task; each task has a test that fails first.

**UI task interaction:** T9, T11 and T12 all edit `app.js` and run in that order. T11's `scanControls` is what T12 changes the primary class on; T12's regex expects exactly `class: state.run ? "" : "primary"`. T11 appends `fieldset/legend/.choice` CSS; T12 replaces the whole stylesheet and includes them once. T11 removes `ACTIONS.scan_all/4g/5g`; `test_parity.test_every_entry_is_actually_rendered_by_the_page` then requires `"scan"` and `"scan_scope"` in `app.js`, which T11's `action("scan", ...)` and `help("FIELDS", "scan_scope")` supply. T11's `el()` change (`on*` → listener) also covers T9's `input` listener had it used an attribute; T9 uses `addEventListener` directly, so no conflict. T7's `_print_help` edit and T11's `_print_help` edit touch different rows.

**Type consistency:** `rank(results, expect_5g, side)` is positional in `scanner.py` (T1) and keyword in the metrics test — same signature. `bands_of` (T3) is called from `server.py` for `/api/scan` bands and from `band_info` for both arguments. `require_idle` (T2) is a method on `Session`, called from `Handler.do_POST` as `self.session.require_idle()`. `scan_target(args)` (T7) takes the parsed namespace, matching how `main` holds it. `copy.PROGRESS["lock_written"]` (T7) uses `{bands}`, which is in `test_error_placeholders_are_only_the_ones_callers_pass`'s allowed set.

**Task interaction:** T3's `bands_of` must not reject what T1's scanner sends: `_sets_for` builds `[str(band)]` from the router's comma list, which are digit strings. T3 changes `/api/scan` to run `bands_of(body.get("bands") or [])`, and `[] or None` is `None`, so the default "all bands" path is unchanged. T4 translates `OSError` inside `Router`, so `_drive`'s branches are untouched; T3 adds `except ValueError` to the request handlers, not to `_drive`, so the two do not overlap. T7 removes `--password` and T10's README already lists no flag. T8's caller test scans `.js` too, so `bad_request` added in T3 (used in `server.py`) and the codes used only in `app.js` (none today) are both covered.

**Placeholder scan:** no TBDs; every code step carries its code.
