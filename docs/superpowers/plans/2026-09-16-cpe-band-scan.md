# CPE Band Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a local app that scans every band a Huawei CPE router supports, ranks them by connection steadiness, lets the user apply any of them, and saves named results — with no LLM involved.

**Architecture:** One Python package. A pure engine (`router` → `device` → `lockfreq` → `metrics` → `scanner` → `store`) that knows nothing about presentation, and two thin front ends over it: a `cli` and a `server` that serves one vanilla-JS page on `127.0.0.1`. Every user-facing string, including every `?` help text, lives in `copy.py` so the CLI, the page and the tests read the same words.

**Tech Stack:** Python 3.10+, `huawei-lte-api` (the only runtime dependency), stdlib `http.server`, vanilla HTML/CSS/JS, `pytest`.

**Spec:** `docs/superpowers/specs/2026-09-16-cpe-band-scan-spec.md`

## Global Constraints

- Python 3.10 or newer. Exactly one runtime dependency: `huawei-lte-api>=1.7`. Dev dependency: `pytest`.
- Every module under `src/cpe_band_scan/`. Tests under `tests/`. No test may touch a real router.
- The server binds `127.0.0.1` only, never `0.0.0.0`. Every `/api/*` request requires the header `X-CPE-Band-Scan-Token` and a `Host` header of `127.0.0.1` or `localhost`.
- The router password is never written to disk, never placed in a URL or query string, and never logged.
- All user-facing text lives in `src/cpe_band_scan/copy.py`. No string literal shown to a user may appear in `server.py`, `cli.py`, `app.js` or `index.html`.
- Text follows the `ux-writing` skill, English rules: sentence case, contractions allowed, buttons are `[verb] [object]`, errors are `[what happened]. [why]. [what to do]`.
- Every band change restores automatic mode on the way out, including cancel and crash, via `finally`.
- Defaults: router `http://192.168.8.1/`, username `admin`, port `8765`.
- Band-lock writes go to `api/net/lock-freq` only. Writing `LTEBand` to `api/net/net-mode` is forbidden anywhere in this codebase.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependency, the two console scripts |
| `src/cpe_band_scan/router.py` | Authenticated session to the router. Turns library and network failures into `RouterError(code)`. The only file that imports `huawei_lte_api` |
| `src/cpe_band_scan/device.py` | Probes firmware and feature switches, picks the driver, reads the carrier name. Raises `RouterError` with the reason the device is unsupported |
| `src/cpe_band_scan/lockfreq.py` | The firmware-4.x driver: read and write `net/lock-freq` |
| `src/cpe_band_scan/metrics.py` | Signal sampling, medians, grading, ranking, band inventory |
| `src/cpe_band_scan/scanner.py` | Scan and trace as generators of events. No printing, no HTTP |
| `src/cpe_band_scan/store.py` | Saved runs on disk: save, list, load, delete, default name |
| `src/cpe_band_scan/copy.py` | Every user-facing string: labels, `?` help, errors, progress |
| `src/cpe_band_scan/cli.py` | Terminal front end |
| `src/cpe_band_scan/server.py` | Local HTTP server: static page, JSON API, background job |
| `src/cpe_band_scan/web/index.html` | The page skeleton |
| `src/cpe_band_scan/web/app.js` | Views, polling, table rendering, `?` popovers |
| `src/cpe_band_scan/web/style.css` | Styling |
| `tests/fakes.py` | Fake router session shared by every test |
| `skills/bandscan/` | The assistant skill that drives the app, shipped with it (Task 18) |

---

## Task 1: Repository, packaging, and the router session

**Files:**
- Create: `pyproject.toml`, `src/cpe_band_scan/__init__.py`, `src/cpe_band_scan/router.py`, `tests/fakes.py`, `.gitignore`
- Test: `tests/test_router.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RouterError(code: str, detail: str = "")`, `normalise_url(str) -> str`, `Router(url, password, username="admin", connection_factory=Connection)` with `.get(endpoint) -> dict` and `.post(endpoint, OrderedDict) -> str`.

- [ ] **Step 1: Create the repo skeleton**

```bash
mkdir -p /Users/esi/Work/Other/cpe-band-scan/src/cpe_band_scan/web /Users/esi/Work/Other/cpe-band-scan/tests
cd /Users/esi/Work/Other/cpe-band-scan && git init && touch src/cpe_band_scan/__init__.py tests/__init__.py
printf '__pycache__/\n*.pyc\n.venv/\n.pytest_cache/\n' > .gitignore
```

`pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "cpe-band-scan"
version = "0.1.0"
description = "Find and lock the steadiest LTE/NR band on a Huawei CPE router"
requires-python = ">=3.10"
dependencies = ["huawei-lte-api>=1.7"]

[project.scripts]
cpe-band-scan = "cpe_band_scan.cli:main"

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools.package-data]
cpe_band_scan = ["web/*"]
```

- [ ] **Step 2: Write the fake session every test uses**

`tests/fakes.py`:

```python
"""A stand-in for huawei_lte_api's Connection. Tests never touch a real router."""


class FakeSession:
    def __init__(self, data=None):
        self.data = dict(data or {})
        self.posts = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, endpoint, prefix=None):
        key = f"config/{endpoint}" if prefix == "config" else endpoint
        value = self.data[key]
        if isinstance(value, Exception):
            raise value
        return value

    def post_set(self, endpoint, data):
        value = self.data.get(f"POST {endpoint}")
        if isinstance(value, Exception):
            raise value
        self.posts.append((endpoint, data))
        return "OK"


def factory(session=None, connect_error=None):
    """Build a connection_factory for Router. `connect_error` fires at login time."""

    def make(url, username=None, password=None):
        if connect_error is not None:
            raise connect_error
        return session if session is not None else FakeSession()

    return make
```

- [ ] **Step 3: Write the failing tests**

`tests/test_router.py`:

```python
import pytest
from collections import OrderedDict
from huawei_lte_api import exceptions as hx

from cpe_band_scan.router import Router, RouterError, normalise_url
from tests.fakes import FakeSession, factory


@pytest.mark.parametrize("given,expected", [
    ("192.168.8.1", "http://192.168.8.1/"),
    ("  192.168.8.1  ", "http://192.168.8.1/"),
    ("http://192.168.1.1", "http://192.168.1.1/"),
    ("http://192.168.1.1/", "http://192.168.1.1/"),
    ("https://router.local/", "https://router.local/"),
])
def test_normalise_url(given, expected):
    assert normalise_url(given) == expected


def test_get_returns_payload():
    session = FakeSession({"device/signal": {"band": "7"}})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    assert router.get("device/signal") == {"band": "7"}


def test_config_endpoints_use_the_config_prefix():
    session = FakeSession({"config/network/bandfreqlist.xml": {"config": {"lte_support_band_list": "1,3"}}})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    assert router.get("config/network/bandfreqlist.xml")["config"]["lte_support_band_list"] == "1,3"


def test_wrong_password_is_reported_as_bad_password():
    router = Router("192.168.8.1", "pw",
                    connection_factory=factory(connect_error=hx.LoginErrorUsernamePasswordWrongException("no", 108001)))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "bad_password"


def test_too_many_attempts_is_reported_as_locked_out():
    router = Router("192.168.8.1", "pw",
                    connection_factory=factory(connect_error=hx.LoginErrorUsernamePasswordOverrunException("no", 108002)))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "locked_out"


def test_no_route_to_host_is_reported_as_unreachable():
    router = Router("192.168.8.1", "pw",
                    connection_factory=factory(connect_error=OSError("No route to host")))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "unreachable"


def test_a_non_huawei_answer_is_reported_as_not_huawei_api():
    """Seen in the field: the box answers 200 with an HTML redirect, the library dies on KeyError('token')."""
    router = Router("192.168.8.1", "pw", connection_factory=factory(connect_error=KeyError("token")))
    with pytest.raises(RouterError) as caught:
        router.get("device/signal")
    assert caught.value.code == "not_huawei_api"


def test_a_refused_api_call_keeps_the_endpoint_in_the_detail():
    session = FakeSession({"net/lock-freq": hx.ResponseErrorException("100006", 100006)})
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    with pytest.raises(RouterError) as caught:
        router.get("net/lock-freq")
    assert caught.value.code == "api_refused"
    assert "net/lock-freq" in caught.value.detail


def test_post_reaches_the_session():
    session = FakeSession()
    router = Router("192.168.8.1", "pw", connection_factory=factory(session))
    router.post("net/lock-freq", OrderedDict(lte_info={}))
    assert session.posts == [("net/lock-freq", OrderedDict(lte_info={}))]
```

- [ ] **Step 4: Run the tests and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.router'`.

- [ ] **Step 5: Write `src/cpe_band_scan/router.py`**

```python
"""The only door to the router. Every failure leaves here as a RouterError with a code
that copy.py can turn into a sentence."""
from __future__ import annotations

from collections import OrderedDict

from huawei_lte_api import exceptions as hx
from huawei_lte_api.Connection import Connection

LOGIN_WRONG = (
    hx.LoginErrorUsernamePasswordWrongException,
    hx.LoginErrorPasswordWrongException,
    hx.LoginErrorUsernameWrongException,
    hx.LoginErrorInvalidCredentialsException,
)


class RouterError(Exception):
    """`code` selects the message; `detail` carries the technical remainder for the small print."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def normalise_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    return url.rstrip("/") + "/"


class Router:
    def __init__(self, url: str, password: str, username: str = "admin", connection_factory=Connection):
        self.url = normalise_url(url)
        self.username = username
        self._password = password
        self._factory = connection_factory

    def _session(self):
        try:
            return self._factory(self.url, username=self.username, password=self._password)
        except LOGIN_WRONG as error:
            raise RouterError("bad_password", type(error).__name__) from error
        except hx.LoginErrorUsernamePasswordOverrunException as error:
            raise RouterError("locked_out", type(error).__name__) from error
        except OSError as error:  # requests' errors subclass OSError: refused, timed out, no route
            raise RouterError("unreachable", f"{type(error).__name__}: {error}") from error
        except Exception as error:
            raise RouterError("not_huawei_api", f"{type(error).__name__}: {error}") from error

    def get(self, endpoint: str) -> dict:
        with self._session() as session:
            try:
                if endpoint.startswith("config/"):
                    return session.get(endpoint.removeprefix("config/"), prefix="config")
                return session.get(endpoint)
            except hx.ResponseErrorException as error:
                raise RouterError("api_refused", f"{endpoint}: {error}") from error

    def post(self, endpoint: str, data: OrderedDict) -> str:
        with self._session() as session:
            try:
                return session.post_set(endpoint, data)
            except hx.ResponseErrorException as error:
                raise RouterError("api_refused", f"{endpoint}: {error}") from error
```

- [ ] **Step 6: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: 13 passed.

- [ ] **Step 7: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: router session with explainable failures"
```

---

## Task 2: Device probe, driver gate, and carrier name

**Files:**
- Create: `src/cpe_band_scan/device.py`
- Test: `tests/test_device.py`

**Interfaces:**
- Consumes: `Router`, `RouterError` from Task 1.
- Produces: `Device` dataclass with fields `model: str`, `firmware: str`, `driver: str`, `carrier: str`, `plmn: str`, and `as_dict() -> dict`; plus `probe(router) -> Device` and `read_carrier(router) -> tuple[str, str]`.

Reason codes this task can raise: `firmware_not_supported`, `no_band_lock`.

- [ ] **Step 1: Write the failing tests**

`tests/test_device.py`:

```python
import pytest
from huawei_lte_api import exceptions as hx

from cpe_band_scan.device import Device, probe, read_carrier
from cpe_band_scan.router import Router, RouterError
from tests.fakes import FakeSession, factory

SUPPORTED = {
    "device/information": {"DeviceName": "H155-381", "SoftwareVersion": "4.0.0.5", "SerialNumber": "ABC123"},
    "net/net-feature-switch": {"lock_freq_switch": "3"},
    "net/lock-freq": {"lte_info": {"lock_mode": "0"}, "nr_info": {"lock_mode": "0"}},
    "net/current-plmn": {"FullName": "MCI", "ShortName": "MCI", "Numeric": "43211", "State": "0"},
}


def router_for(overrides=None):
    data = dict(SUPPORTED, **(overrides or {}))
    return Router("192.168.8.1", "pw", connection_factory=factory(FakeSession(data)))


def test_a_supported_router_reports_its_driver_and_carrier():
    device = probe(router_for())
    assert device == Device(model="H155-381", firmware="4.0.0.5", driver="lockfreq",
                            carrier="MCI", plmn="43211")


def test_old_firmware_is_refused_with_the_version_in_the_detail():
    with pytest.raises(RouterError) as caught:
        probe(router_for({"device/information": {"DeviceName": "B525", "SoftwareVersion": "3.11.1"}}))
    assert caught.value.code == "firmware_not_supported"
    assert "3.11.1" in caught.value.detail


def test_a_router_without_the_band_lock_switch_is_refused():
    with pytest.raises(RouterError) as caught:
        probe(router_for({"net/net-feature-switch": {"lock_freq_switch": "0"}}))
    assert caught.value.code == "no_band_lock"


def test_a_router_whose_lock_page_cannot_be_read_is_refused():
    with pytest.raises(RouterError) as caught:
        probe(router_for({"net/lock-freq": hx.ResponseErrorException("not here", 100002)}))
    assert caught.value.code == "no_band_lock"


def test_a_missing_carrier_name_never_fails_the_probe():
    device = probe(router_for({"net/current-plmn": hx.ResponseErrorException("nope", 100002)}))
    assert device.carrier == ""
    assert device.driver == "lockfreq"


def test_the_carrier_falls_back_to_the_network_code():
    assert read_carrier(router_for({"net/current-plmn": {"Numeric": "43211"}})) == ("43211", "43211")


def test_as_dict_is_json_safe():
    assert probe(router_for()).as_dict()["model"] == "H155-381"
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_device.py -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.device'`.

- [ ] **Step 3: Write `src/cpe_band_scan/device.py`**

```python
"""Which driver may write to this router. The firmware answers, never the model name:
the same box ships with 3.x and 4.x, and the two speak different band-lock APIs."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .router import Router, RouterError


@dataclass(frozen=True)
class Device:
    model: str
    firmware: str
    driver: str
    carrier: str
    plmn: str

    def as_dict(self) -> dict:
        return asdict(self)


def read_carrier(router: Router) -> tuple[str, str]:
    """(name, plmn). Never raises: a nameless carrier is cosmetic, not a failure."""
    try:
        plmn = router.get("net/current-plmn") or {}
    except RouterError:
        return "", ""
    numeric = (plmn.get("Numeric") or "").strip()
    name = (plmn.get("ShortName") or plmn.get("FullName") or numeric or "").strip()
    return name, numeric


def probe(router: Router) -> Device:
    info = router.get("device/information") or {}
    firmware = (info.get("SoftwareVersion") or "").strip()
    if not firmware.startswith("4."):
        raise RouterError("firmware_not_supported", firmware or "unknown")

    switches = router.get("net/net-feature-switch") or {}
    if str(switches.get("lock_freq_switch") or "") != "3":
        raise RouterError("no_band_lock", f"lock_freq_switch={switches.get('lock_freq_switch')!r}")

    try:
        router.get("net/lock-freq")
    except RouterError as error:
        raise RouterError("no_band_lock", error.detail) from error

    carrier, plmn = read_carrier(router)
    return Device(model=(info.get("DeviceName") or "").strip(), firmware=firmware,
                  driver="lockfreq", carrier=carrier, plmn=plmn)
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: probe firmware, driver and carrier before any write"
```

---

## Task 3: The firmware-4.x band lock driver

**Files:**
- Create: `src/cpe_band_scan/lockfreq.py`
- Test: `tests/test_lockfreq.py`

**Interfaces:**
- Consumes: `Router` from Task 1.
- Produces: `band_info(bands, scell=()) -> OrderedDict`, `lock(router, lte=(), nr=(), lte_scell=()) -> str`, `read_lock(router) -> dict` shaped `{"lte": (anchors, scell), "nr": (bands, [])}`.

Band values are strings everywhere ("7", not 7), because the API returns strings and mixing the two breaks set comparisons.

- [ ] **Step 1: Write the failing tests**

`tests/test_lockfreq.py`:

```python
from cpe_band_scan.lockfreq import band_info, lock, read_lock
from cpe_band_scan.router import Router
from tests.fakes import FakeSession, factory


def router_for(data=None):
    session = FakeSession(data or {})
    return Router("192.168.8.1", "pw", connection_factory=factory(session)), session


def test_no_bands_means_lock_mode_zero():
    assert band_info([]) == {"lock_mode": "0", "freq_infos": {}, "all_bands": ""}


def test_anchor_bands_become_freq_infos():
    assert band_info(["7"]) == {"lock_mode": "3",
                                "freq_infos": {"freq_info": [{"band": "7"}]},
                                "all_bands": "7"}


def test_secondary_bands_only_appear_in_all_bands():
    info = band_info(["7"], ["3"])
    assert info["freq_infos"] == {"freq_info": [{"band": "7"}]}
    assert info["all_bands"] == "3,7"


def test_all_bands_is_sorted_numerically_and_deduplicated():
    assert band_info(["7", "3"], ["3", "40"])["all_bands"] == "3,7,40"


def test_lock_posts_both_sides_in_one_request():
    router, session = router_for()
    lock(router, lte=["7"], lte_scell=["3"], nr=["78"])
    endpoint, payload = session.posts[0]
    assert endpoint == "net/lock-freq"
    assert list(payload) == ["lte_info", "nr_info"]
    assert payload["lte_info"]["all_bands"] == "3,7"
    assert payload["nr_info"]["freq_infos"] == {"freq_info": [{"band": "78"}]}


def test_clearing_both_sides_sends_lock_mode_zero_twice():
    router, session = router_for()
    lock(router)
    _, payload = session.posts[0]
    assert payload["lte_info"]["lock_mode"] == payload["nr_info"]["lock_mode"] == "0"


def test_read_lock_separates_anchors_from_secondaries():
    router, _ = router_for({"net/lock-freq": {
        "lte_info": {"freq_infos": {"freq_info": [{"band": "7"}]}, "all_bands": "3,7"},
        "nr_info": {"freq_infos": {}, "all_bands": ""},
    }})
    assert read_lock(router) == {"lte": (["7"], ["3"]), "nr": ([], [])}


def test_read_lock_accepts_a_single_freq_info_that_is_not_a_list():
    router, _ = router_for({"net/lock-freq": {
        "lte_info": {"freq_infos": {"freq_info": {"band": "40"}}, "all_bands": "40"},
        "nr_info": {},
    }})
    assert read_lock(router)["lte"] == (["40"], [])
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_lockfreq.py -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.lockfreq'`.

- [ ] **Step 3: Write `src/cpe_band_scan/lockfreq.py`**

```python
"""api/net/lock-freq, the only band-lock endpoint that firmware 4.x honours.

lock_mode: 0 none, 3 band, 1 frequency, 2 cell. Bands inside <freq_infos> may serve as the
primary carrier; bands that appear only in <all_bands> are allowed as secondary carriers,
which is how a lock keeps carrier aggregation alive.
"""
from __future__ import annotations

from collections import OrderedDict

from .router import Router

ENDPOINT = "net/lock-freq"


def band_info(bands, scell=()) -> OrderedDict:
    bands = [str(b) for b in bands]
    if not bands:
        return OrderedDict(lock_mode="0", freq_infos={}, all_bands="")
    every = sorted({*bands, *(str(b) for b in scell)}, key=int)
    return OrderedDict(lock_mode="3",
                       freq_infos={"freq_info": [{"band": b} for b in bands]},
                       all_bands=",".join(every))


def lock(router: Router, lte=(), nr=(), lte_scell=()) -> str:
    return router.post(ENDPOINT, OrderedDict(lte_info=band_info(lte, lte_scell),
                                             nr_info=band_info(nr)))


def read_lock(router: Router) -> dict:
    current = router.get(ENDPOINT) or {}
    out = {}
    for side in ("lte", "nr"):
        info = current.get(f"{side}_info") or {}
        raw = (info.get("freq_infos") or {}).get("freq_info") or []
        entries = raw if isinstance(raw, list) else [raw]
        anchors = [str(entry["band"]) for entry in entries if entry.get("band")]
        every = [b for b in (info.get("all_bands") or "").split(",") if b]
        out[side] = (anchors, [b for b in every if b not in anchors])
    return out
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: read and write the lock-freq band lock"
```

---

## Task 4: Signal metrics, grading, ranking, band inventory

**Files:**
- Create: `src/cpe_band_scan/metrics.py`
- Modify: `tests/fakes.py` (add the `Seq` helper so one endpoint can return changing values)
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `Router` from Task 1.
- Produces: `number(value) -> float`, `sample(router) -> dict`, `measure(router, samples=5, gap=5, sleep=time.sleep) -> dict`, `summarise(rows) -> dict`, `grade(measurement, expect_5g=True) -> str`, `rank(results, expect_5g=True) -> list[str]`, `supported_bands(router, side) -> list[str]`, `visible_bands(router) -> dict`.
- A sample dict is `{"band", "has5g", "sinr", "rsrq", "rsrp", "nrsinr", "nrrsrp"}`. A measurement adds `{"floor", "peak", "samples"}`. Grades are the keys `excellent`, `good`, `fair`, `poor`, `no5g`; their labels live in `copy.py` (Task 7).

**Why `expect_5g`:** a router on a 4G-only plan never reports an `N` carrier. Judging every band as "loses 5G" would leave nothing recommendable, so the scanner decides once, from the baseline, whether 5G is expected at all, and passes it down.

- [ ] **Step 1: Add the changing-value helper to `tests/fakes.py`**

```python
class Seq:
    """A value that advances on each read, for sampling tests. The last value repeats."""

    def __init__(self, values):
        self.values = list(values)

    def next(self):
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]
```

And inside `FakeSession.get`, **before** the `isinstance(value, Exception)` check, so a sequence can
stage an exception as one of its readings:

```python
        if isinstance(value, Seq):
            value = value.next()
```

Order matters here. Unwrapping after the exception check would hand a staged exception back as data
instead of raising it, which quietly disarms every test that stages a mid-scan failure.

- [ ] **Step 2: Write the failing tests**

`tests/test_metrics.py`:

```python
import math
import pytest

from cpe_band_scan import metrics
from cpe_band_scan.router import Router
from tests.fakes import FakeSession, Seq, factory


def signal(sinr="8", rsrq="-10", rsrp="-85", band="B7(N78)", nrsinr="12", nrrsrp="-80"):
    return {"band": band, "sinr": f"{sinr}dB", "rsrq": f"{rsrq}dB", "rsrp": f"{rsrp}dBm",
            "nrsinr": nrsinr, "nrrsrp": nrrsrp}


def router_for(data):
    return Router("192.168.8.1", "pw", connection_factory=factory(FakeSession(data)))


@pytest.mark.parametrize("given,expected", [("-95dBm", -95.0), ("8dB", 8.0), ("0", 0.0), ("1.5", 1.5)])
def test_number_strips_units(given, expected):
    assert metrics.number(given) == expected


@pytest.mark.parametrize("given", ["", None, ">=-140"])
def test_number_is_nan_when_there_is_nothing_to_read(given):
    assert math.isnan(metrics.number(given)) or metrics.number(given) == -140.0


def test_sample_reads_the_signal_line():
    taken = metrics.sample(router_for({"device/signal": signal()}))
    assert (taken["sinr"], taken["rsrq"], taken["rsrp"]) == (8.0, -10.0, -85.0)
    assert taken["has5g"] is True


def test_a_band_string_without_an_nr_carrier_means_no_5g():
    assert metrics.sample(router_for({"device/signal": signal(band="B1")}))["has5g"] is False


def test_measure_reports_the_floor_and_the_median_without_waiting():
    data = {"device/signal": Seq([signal(sinr="10"), signal(sinr="2"), signal(sinr="8")])}
    taken = metrics.measure(router_for(data), samples=3, sleep=lambda seconds: None)
    assert taken["floor"] == 2.0
    assert taken["sinr"] == 8.0
    assert taken["peak"] == 10.0
    assert taken["samples"] == 3


def test_measure_waits_between_samples_but_not_before_the_first():
    waits = []
    data = {"device/signal": Seq([signal(), signal(), signal()])}
    metrics.measure(router_for(data), samples=3, gap=5, sleep=waits.append)
    assert waits == [5, 5]


def test_5g_counts_as_kept_only_when_every_sample_had_it():
    data = {"device/signal": Seq([signal(), signal(band="B7"), signal()])}
    assert metrics.measure(router_for(data), samples=3, sleep=lambda s: None)["has5g"] is False


@pytest.mark.parametrize("floor,rsrq,expected", [
    (9, -8, "excellent"), (5, -10, "excellent"),
    (4, -8, "good"), (0, -13, "good"),
    (-1, -14, "fair"), (-5, -16, "fair"),
    (-6, -8, "poor"), (2, -20, "poor"),
])
def test_grades_follow_the_floor_and_the_channel_quality(floor, rsrq, expected):
    assert metrics.grade({"floor": floor, "rsrq": rsrq, "has5g": True}) == expected


def test_a_band_that_drops_5g_is_graded_no5g():
    assert metrics.grade({"floor": 12, "rsrq": -8, "has5g": False}) == "no5g"


def test_losing_5g_is_not_held_against_a_4g_only_connection():
    assert metrics.grade({"floor": 12, "rsrq": -8, "has5g": False}, expect_5g=False) == "excellent"


def test_rank_orders_by_floor_then_by_typical_signal():
    results = {
        "B1": {"floor": 2, "sinr": 9, "has5g": True},
        "B7": {"floor": 7, "sinr": 8, "has5g": True},
        "B40": {"floor": 2, "sinr": 11, "has5g": True},
        "B3": {"floor": 20, "sinr": 20, "has5g": False},
        "auto": {"floor": 30, "sinr": 30, "has5g": True},
    }
    assert metrics.rank(results) == ["B7", "B40", "B1"]


def test_supported_bands_come_from_the_router_config():
    data = {"config/network/bandfreqlist.xml": {"config": {
        "lte_support_band_list": "1,3,7,40", "nr_support_band_list": "78,79"}}}
    router = router_for(data)
    assert metrics.supported_bands(router, "lte") == ["1", "3", "7", "40"]
    assert metrics.supported_bands(router, "nr") == ["78", "79"]


def test_visible_bands_never_raise():
    router = router_for({"device/nbrcellinfo": KeyError("gone"), "device/seccellinfo": {}})
    assert metrics.visible_bands(router) == {"lte": [], "nr": []}
```

- [ ] **Step 3: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_metrics.py -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.metrics'`.

- [ ] **Step 4: Write `src/cpe_band_scan/metrics.py`**

```python
"""What the radio is doing, and how good that is.

Stability lives in the SINR floor, not the average: a band that averages 8 dB but dips to
-4 dB stutters, while one holding 7-10 dB does not. RSRP above -90 dBm barely moves
throughput, so it never decides a ranking.
"""
from __future__ import annotations

import re
import statistics
import time

from .router import Router, RouterError

SAMPLES, GAP = 5, 5
GRADES = (("excellent", 5.0, -10.0), ("good", 0.0, -13.0), ("fair", -5.0, -16.0))
NUMBER = re.compile(r"[-+]?\d*\.?\d+")
SIGNAL_FIELDS = ("sinr", "rsrq", "rsrp", "nrsinr", "nrrsrp")


def number(value) -> float:
    found = NUMBER.search(str(value or ""))
    return float(found.group()) if found else float("nan")


def sample(router: Router) -> dict:
    signal = router.get("device/signal") or {}
    band = str(signal.get("band") or "")
    taken = {"band": band, "has5g": "(N" in band}
    taken.update({field: number(signal.get(field)) for field in SIGNAL_FIELDS})
    return taken


def summarise(rows: list[dict]) -> dict:
    median = lambda field: statistics.median(row[field] for row in rows)
    out = {"band": rows[-1]["band"],
           "has5g": all(row["has5g"] for row in rows),
           "floor": min(row["sinr"] for row in rows),
           "peak": max(row["sinr"] for row in rows),
           "samples": len(rows)}
    out.update({field: median(field) for field in SIGNAL_FIELDS})
    return out


def measure(router: Router, samples: int = SAMPLES, gap: int = GAP, sleep=time.sleep) -> dict:
    rows = []
    for index in range(samples):
        if index:
            sleep(gap)
        rows.append(sample(router))
    return summarise(rows)


def grade(measurement: dict, expect_5g: bool = True) -> str:
    if expect_5g and not measurement.get("has5g"):
        return "no5g"
    for name, floor, rsrq in GRADES:
        if measurement["floor"] >= floor and measurement["rsrq"] >= rsrq:
            return name
    return "poor"


def rank(results: dict, expect_5g: bool = True) -> list[str]:
    """Best first. 'auto' is a reference row, never a candidate."""
    live = {name: row for name, row in results.items()
            if name != "auto" and (row.get("has5g") or not expect_5g)}
    return sorted(live, key=lambda name: (-live[name]["floor"], -live[name]["sinr"]))


def supported_bands(router: Router, side: str) -> list[str]:
    config = (router.get("config/network/bandfreqlist.xml") or {}).get("config") or {}
    key = "nr_support_band_list" if side == "nr" else "lte_support_band_list"
    return [band.strip() for band in (config.get(key) or "").split(",") if band.strip()]


def visible_bands(router: Router) -> dict:
    """Cells the router can see right now. Only a hint: an active lock hides the rest."""
    text = ""
    for endpoint in ("device/nbrcellinfo", "device/seccellinfo"):
        try:
            payload = router.get(endpoint) or {}
        except (RouterError, Exception):
            continue
        text += "".join(str(value) for value in payload.values() if value)
    return {"lte": sorted(set(re.findall(r"\bB(\d+)", text)), key=int),
            "nr": sorted(set(re.findall(r"\bN(\d+)", text)), key=int)}
```

- [ ] **Step 5: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: measure, grade and rank bands"
```

---

## Task 5: The scan and trace engine

**Files:**
- Create: `src/cpe_band_scan/scanner.py`
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `lockfreq.lock`, `lockfreq.read_lock`, `metrics.*`, `Device.as_dict()`.
- Produces:
  - `scan(router, device, sides=("lte", "nr"), bands=None, cancelled=None, sleep=time.sleep) -> Iterator[dict]`
  - `trace(router, seconds=120, gap=10, cancelled=None, sleep=time.sleep) -> Iterator[dict]`
  - `choose(run) -> dict` with keys `lte`, `lte_scell`, `nr`
  - Constants `SETTLE = 35`, `PER_SET = 65`
- Event types, all JSON-safe dicts: `run_start`, `side_start`, `set_start`, `set_result`, `set_skipped`, `side_done`, `applied`, `cancelled`, `trace_start`, `trace_sample`, `trace_done`, `done`.
- The run document produced by the final `done` event:

```python
{"kind": "scan", "started": "2026-09-16T21:40:00", "finished": "...",
 "router_url": "http://192.168.8.1/", "device": {...}, "expect_5g": True,
 "sides": {"lte": {"sets": {"B7": ["7"]}, "results": {"B7": {...}}, "skipped": {"B39": "no_service"},
                   "order": ["B7", "B40"]}},
 "applied": {"lte": ["7"], "lte_scell": ["3"], "nr": []}}
```

**Why a generator:** the CLI prints events, the web server buffers them for polling, the tests assert on them. One run, three readers, no duplicated progress logic.

- [ ] **Step 1: Write the failing tests**

`tests/test_scanner.py`:

```python
import pytest
from huawei_lte_api import exceptions as hx

from cpe_band_scan import scanner
from cpe_band_scan.device import Device
from cpe_band_scan.router import Router
from tests.fakes import FakeSession, Seq, factory

DEVICE = Device(model="H155-381", firmware="4.0.0.5", driver="lockfreq", carrier="MCI", plmn="43211")


def signal(sinr, band="B7(N78)"):
    return {"band": band, "sinr": f"{sinr}", "rsrq": "-10", "rsrp": "-85", "nrsinr": "12", "nrrsrp": "-80"}


def build(signals, bands="1,7"):
    """A router whose signal readings follow `signals`, one per read."""
    session = FakeSession({
        "device/signal": Seq(signals),
        "net/lock-freq": {"lte_info": {}, "nr_info": {}},
        "config/network/bandfreqlist.xml": {"config": {"lte_support_band_list": bands,
                                                       "nr_support_band_list": "78"}},
        "device/nbrcellinfo": {}, "device/seccellinfo": {},
    })
    return Router("192.168.8.1", "pw", connection_factory=factory(session)), session


def run_scan(**kwargs):
    kwargs.setdefault("sleep", lambda seconds: None)
    return list(scanner.scan(**kwargs))


def test_a_scan_measures_every_supported_band_plus_the_automatic_baseline():
    router, _ = build([signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    started = [event["name"] for event in events if event["type"] == "set_start"]
    assert started == ["B1", "B7", "auto"]


def test_each_set_reports_a_graded_result():
    router, _ = build([signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    result = next(event for event in events if event["type"] == "set_result")
    assert result["result"]["grade"] == "excellent"
    assert result["name"] == "B1"


def test_a_band_with_no_service_is_skipped_not_measured():
    # the first reading is the pre-scan baseline; the second is what B1 reports once locked
    router, _ = build([signal(8)] + [signal(8, band="")] + [signal(8)] * 200)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    skipped = [event for event in events if event["type"] == "set_skipped"]
    assert skipped[0]["name"] == "B1"
    assert skipped[0]["reason"] == "no_service"


def test_a_band_the_router_refuses_is_skipped_and_the_scan_continues():
    router, session = build([signal(8)] * 200)
    session.data["POST net/lock-freq"] = hx.ResponseErrorException("100006", 100006)
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    reasons = [event["reason"] for event in events if event["type"] == "set_skipped"]
    assert reasons == ["refused", "refused", "refused"]
    assert events[-1]["type"] == "done"


def test_a_crash_mid_scan_still_leaves_the_router_on_automatic():
    """The finally block is the only thing between a crash and a router left locked to one band.
    Do not assert this from a completed scan: the synthetic `auto` set clears the lock as an
    ordinary step, so such a test passes even with the finally deleted."""
    router, session = build([signal(8), signal(8), RuntimeError("radio went away")])
    with pytest.raises(RuntimeError):
        run_scan(router=router, device=DEVICE, sides=("lte",))
    assert session.posts, "the scan must have written at least once"
    assert session.posts[-1][1]["lte_info"]["lock_mode"] == "0"


def test_cancelling_stops_the_scan_and_restores_automatic():
    router, session = build([signal(8)] * 200)
    events = list(scanner.scan(router=router, device=DEVICE, sides=("lte",),
                               cancelled=lambda: True, sleep=lambda s: None))
    assert events[-1]["type"] == "done"
    assert any(event["type"] == "cancelled" for event in events)
    assert session.posts, "the finally block must still clear the lock"
    assert session.posts[-1][1]["lte_info"]["lock_mode"] == "0"


def test_the_winner_is_applied_with_the_runners_up_as_secondaries():
    router, _ = build([signal(8)] * 200, bands="1,7")
    events = run_scan(router=router, device=DEVICE, sides=("lte",))
    record = events[-1]["run"]["sides"]["lte"]
    applied = next(event for event in events if event["type"] == "applied")
    assert applied["plan"]["lte"] == record["sets"][record["order"][0]]
    assert applied["plan"]["lte_scell"] == [band for name in record["order"][1:]
                                            for band in record["sets"][name]]


def test_the_run_document_carries_everything_needed_to_save_it():
    router, _ = build([signal(8)] * 200)
    run = run_scan(router=router, device=DEVICE, sides=("lte",))[-1]["run"]
    assert run["kind"] == "scan"
    assert run["device"]["carrier"] == "MCI"
    assert run["sides"]["lte"]["order"][0] in run["sides"]["lte"]["results"]
    assert run["started"] and run["finished"]


def test_a_connection_without_5g_still_produces_a_ranking():
    router, _ = build([signal(8, band="B1")] * 200)
    run = run_scan(router=router, device=DEVICE, sides=("lte",))[-1]["run"]
    assert run["expect_5g"] is False
    assert run["sides"]["lte"]["order"], "4G-only connections must still rank"


def test_nr_is_only_locked_when_two_nr_bands_answer():
    router, _ = build([signal(8)] * 200, bands="7")
    run = run_scan(router=router, device=DEVICE, sides=("nr",))[-1]["run"]
    assert run["applied"]["nr"] == []


def test_trace_yields_one_sample_per_step_and_a_summary():
    router, _ = build([signal(8)] * 50)
    events = list(scanner.trace(router, seconds=30, gap=10, sleep=lambda s: None))
    assert [event["type"] for event in events] == [
        "trace_start", "trace_sample", "trace_sample", "trace_sample", "trace_done"]
    assert events[-1]["run"]["kind"] == "test"
    assert events[-1]["run"]["summary"]["floor"] == 8.0
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_scanner.py -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.scanner'`.

- [ ] **Step 3: Write `src/cpe_band_scan/scanner.py`**

```python
"""One scan, many readers. The engine yields events; the CLI prints them, the server
buffers them, the tests assert on them. Nothing here knows about a terminal or HTTP."""
from __future__ import annotations

import time
from datetime import datetime

from . import lockfreq, metrics
from .router import Router, RouterError

SETTLE = 35                       # seconds a re-attach needs after a band change
PER_SET = SETTLE + metrics.SAMPLES * metrics.GAP + 5
OTHER = {"lte": "nr", "nr": "lte"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sets_for(router: Router, side: str, bands=None) -> dict:
    prefix = "N" if side == "nr" else "B"
    listed = bands or metrics.supported_bands(router, side)
    sets = {f"{prefix}{band}": [str(band)] for band in listed}
    sets["auto"] = []             # the reference row: what the router picks on its own
    return sets


def _scan_side(router, side, sets, expect_5g, cancelled, sleep):
    keep = lockfreq.read_lock(router)          # the other side keeps whatever lock it had
    other = OTHER[side]

    def set_side(bands):
        arguments = {side: bands, other: keep[other][0]}
        if other == "lte":
            arguments["lte_scell"] = keep["lte"][1]
        return lockfreq.lock(router, **arguments)

    results, skipped = {}, {}
    total = len(sets)
    yield {"type": "side_start", "side": side, "total": total, "eta_s": total * PER_SET}
    try:
        for index, (name, bands) in enumerate(sets.items(), 1):
            if cancelled():
                yield {"type": "cancelled", "side": side}
                break
            yield {"type": "set_start", "side": side, "name": name, "bands": bands,
                   "index": index, "total": total, "eta_s": (total - index + 1) * PER_SET}
            try:
                set_side(bands)
            except RouterError as error:
                skipped[name] = "refused"
                yield {"type": "set_skipped", "side": side, "name": name,
                       "reason": "refused", "detail": error.detail}
                continue
            sleep(SETTLE)
            first = metrics.sample(router)
            if not first["band"] or (side == "nr" and bands and not first["has5g"]):
                skipped[name] = "no_service"
                yield {"type": "set_skipped", "side": side, "name": name, "reason": "no_service"}
                continue
            measurement = metrics.measure(router, sleep=sleep)
            measurement["grade"] = metrics.grade(measurement, expect_5g)
            measurement["bands"] = bands
            results[name] = measurement
            yield {"type": "set_result", "side": side, "name": name, "result": measurement}
    finally:
        try:
            set_side([])
        except Exception:            # a failed restore must never replace the failure that caused the exit
            pass
    yield {"type": "side_done", "side": side, "sets": sets, "results": results,
           "skipped": skipped, "order": metrics.rank(results, expect_5g)}


def choose(run: dict) -> dict:
    """What to lock once the scan is done: the best LTE anchor, every other live band as a
    secondary so carrier aggregation survives, and an NR lock only when two or more NR bands
    answered — on NSA the NR carrier follows the LTE anchor, so locking one is pointless."""
    plan = {"lte": [], "lte_scell": [], "nr": []}
    lte = run["sides"].get("lte")
    if lte and lte["order"]:
        plan["lte"] = list(lte["sets"][lte["order"][0]])
        plan["lte_scell"] = [band for name in lte["order"][1:] for band in lte["sets"][name]]
    nr = run["sides"].get("nr")
    if nr and len(nr["order"]) >= 2:
        plan["nr"] = list(nr["sets"][nr["order"][0]])
    return plan


def scan(router: Router, device, sides=("lte", "nr"), bands=None, cancelled=None, sleep=time.sleep):
    cancelled = cancelled or (lambda: False)
    baseline = metrics.sample(router)
    expect_5g = baseline["has5g"]
    run = {"kind": "scan", "started": _now(), "finished": "", "router_url": router.url,
           "device": device.as_dict(), "expect_5g": expect_5g, "baseline": baseline,
           "sides": {}, "applied": {"lte": [], "lte_scell": [], "nr": []}}
    yield {"type": "run_start", "sides": list(sides), "expect_5g": expect_5g, "baseline": baseline}

    for side in sides:
        sets = _sets_for(router, side, bands)
        for event in _scan_side(router, side, sets, expect_5g, cancelled, sleep):
            yield event
            if event["type"] == "side_done":
                run["sides"][side] = {key: event[key] for key in ("sets", "results", "skipped", "order")}

    plan = choose(run)
    if plan["lte"] or plan["nr"] and not cancelled():
        lockfreq.lock(router, lte=plan["lte"], lte_scell=plan["lte_scell"], nr=plan["nr"])
        run["applied"] = plan
        sleep(SETTLE)
        yield {"type": "applied", "plan": plan, "signal": metrics.sample(router)}
    run["finished"] = _now()
    yield {"type": "done", "run": run}


def trace(router: Router, seconds: int = 120, gap: int = 10, cancelled=None, sleep=time.sleep):
    """Watch the current lock without touching it."""
    cancelled = cancelled or (lambda: False)
    rows = []
    yield {"type": "trace_start", "seconds": seconds, "gap": gap}
    for index in range(seconds // gap):
        if cancelled():
            yield {"type": "cancelled", "side": "trace"}
            break
        row = metrics.sample(router)
        rows.append(row)
        yield {"type": "trace_sample", "at_s": index * gap, "sample": row}
        sleep(gap)
    summary = metrics.summarise(rows)
    summary["grade"] = metrics.grade(summary, expect_5g=rows[0]["has5g"] if rows else False)
    run = {"kind": "test", "started": _now(), "finished": _now(), "router_url": router.url,
           "lock": lockfreq.read_lock(router), "samples": rows, "summary": summary}
    yield {"type": "trace_done", "run": run}
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed. If `test_the_winner_is_applied_with_the_runners_up_as_secondaries` fails, check the operator precedence in the `if plan["lte"] or plan["nr"] and not cancelled():` line and write it as `if (plan["lte"] or plan["nr"]) and not cancelled():`.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: scan and trace as an event stream"
```

---

## Task 6: Saved runs

**Files:**
- Create: `src/cpe_band_scan/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: the run document from Task 5.
- Produces: `home() -> Path`, `default_name(carrier, when=None) -> str`, `save(run, name=None) -> dict`, `list_runs() -> list[dict]`, `load(run_id) -> dict`, `rename(run_id, name) -> dict`, `delete(run_id) -> None`.
- Storage: one JSON file per run at `~/.cpe-band-scan/runs/<id>.json`, `id` = `YYYYmmdd-HHMMSS` with `-2`, `-3` suffixes on collision. `CPE_BAND_SCAN_HOME` overrides the folder, which is how tests keep off the real one.
- Summary rows from `list_runs()`: `{"id", "name", "saved", "kind", "carrier", "best"}`, newest first.

- [ ] **Step 1: Write the failing tests**

`tests/test_store.py`:

```python
import json
from datetime import datetime

import pytest

from cpe_band_scan import store


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CPE_BAND_SCAN_HOME", str(tmp_path))
    return tmp_path


RUN = {"kind": "scan", "device": {"carrier": "MCI", "model": "H155-381"},
       "sides": {"lte": {"order": ["B7", "B40"], "results": {"B7": {"floor": 7}}}}}


def test_the_default_name_uses_the_carrier_and_the_date():
    assert store.default_name("MCI", datetime(2026, 9, 16, 21, 40)) == "MCI — 16 Sep 2026, 21:40"


def test_an_unknown_carrier_still_gets_a_usable_name():
    assert store.default_name("", datetime(2026, 9, 16, 21, 40)).startswith("Unknown carrier")


def test_saving_names_the_run_after_the_carrier_by_default():
    saved = store.save(RUN)
    assert saved["name"].startswith("MCI — ")
    assert saved["id"]


def test_a_given_name_wins_over_the_default():
    assert store.save(RUN, name="Living room, MCI")["name"] == "Living room, MCI"


def test_a_saved_run_can_be_loaded_back_whole():
    saved = store.save(RUN)
    assert store.load(saved["id"])["sides"]["lte"]["order"] == ["B7", "B40"]


def test_two_runs_saved_in_the_same_second_keep_separate_files():
    first, second = store.save(RUN), store.save(RUN)
    assert first["id"] != second["id"]
    assert len(store.list_runs()) == 2


def test_the_list_carries_enough_to_choose_between_runs():
    store.save(RUN, name="Living room")
    row = store.list_runs()[0]
    assert row["name"] == "Living room"
    assert row["carrier"] == "MCI"
    assert row["best"] == "B7"
    assert row["kind"] == "scan"


def test_runs_are_listed_newest_first():
    store.save(RUN, name="older")
    store.save(RUN, name="newer")
    assert [row["name"] for row in store.list_runs()] == ["newer", "older"]


def test_renaming_keeps_the_rest_of_the_run():
    saved = store.save(RUN)
    renamed = store.rename(saved["id"], "Bedroom")
    assert renamed["name"] == "Bedroom"
    assert store.load(saved["id"])["sides"]["lte"]["order"] == ["B7", "B40"]


def test_deleting_removes_it_from_the_list():
    saved = store.save(RUN)
    store.delete(saved["id"])
    assert store.list_runs() == []


@pytest.mark.parametrize("bad_id", ["../../etc/passwd", "..", "run/../..", "nope",
                                    "20260916-214000\n"])
def test_a_run_id_that_is_not_an_id_is_refused(bad_id):
    with pytest.raises(KeyError):
        store.load(bad_id)


def test_a_corrupt_file_is_skipped_not_crashed_on(home):
    store.save(RUN)
    (home / "runs" / "broken.json").write_text("{not json", encoding="utf-8")
    assert len(store.list_runs()) == 1
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_store.py -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.store'`.

- [ ] **Step 3: Write `src/cpe_band_scan/store.py`**

```python
"""Saved runs: one JSON file each, under ~/.cpe-band-scan/runs. Nothing here ever holds a password."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

RUN_ID = re.compile(r"\A[0-9]{8}-[0-9]{6}(-[0-9]+)?\Z")   # \Z, not $: $ also matches before a trailing newline


def home() -> Path:
    return Path(os.environ.get("CPE_BAND_SCAN_HOME") or Path.home() / ".cpe-band-scan")


def runs_dir() -> Path:
    folder = home() / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def default_name(carrier: str, when: datetime | None = None) -> str:
    when = when or datetime.now()
    return f"{carrier or 'Unknown carrier'} — {when:%d %b %Y, %H:%M}"


def _unique_id(when: datetime) -> str:
    base = f"{when:%Y%m%d-%H%M%S}"
    candidate, suffix = base, 1
    while (runs_dir() / f"{candidate}.json").exists():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _path(run_id: str) -> Path:
    if not RUN_ID.match(run_id or ""):
        raise KeyError(run_id)
    path = runs_dir() / f"{run_id}.json"
    if not path.exists():
        raise KeyError(run_id)
    return path


def save(run: dict, name: str | None = None) -> dict:
    when = datetime.now()
    stored = dict(run)
    carrier = (stored.get("device") or {}).get("carrier", "")
    stored["name"] = (name or stored.get("name") or default_name(carrier, when)).strip()
    stored["id"] = stored.get("id") or _unique_id(when)
    stored["saved"] = when.isoformat(timespec="seconds")
    (runs_dir() / f"{stored['id']}.json").write_text(json.dumps(stored, indent=2), encoding="utf-8")
    return stored


def best_of(run: dict) -> str:
    order = ((run.get("sides") or {}).get("lte") or {}).get("order") or []
    return order[0] if order else ""


def list_runs() -> list[dict]:
    rows = []
    for path in runs_dir().glob("*.json"):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows.append({"id": run.get("id", path.stem), "name": run.get("name", ""),
                     "saved": run.get("saved", ""), "kind": run.get("kind", "scan"),
                     "carrier": (run.get("device") or {}).get("carrier", ""),
                     "best": best_of(run)})
    # `saved` has second resolution, so the id breaks same-second ties; without it the order
    # falls back to whatever the filesystem happened to return.
    return sorted(rows, key=lambda row: (row["saved"], row["id"]), reverse=True)


def load(run_id: str) -> dict:
    return json.loads(_path(run_id).read_text(encoding="utf-8"))


def rename(run_id: str, name: str) -> dict:
    run = load(run_id)
    run["name"] = name.strip() or run["name"]
    _path(run_id).write_text(json.dumps(run, indent=2), encoding="utf-8")
    return run


def delete(run_id: str) -> None:
    _path(run_id).unlink()
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: save, list and reopen named runs"
```

---

## Task 7: The copy catalogue

**Files:**
- Create: `src/cpe_band_scan/copy.py`
- Test: `tests/test_copy.py`

**Interfaces:**
- Consumes: the error codes from Tasks 1-2, the event types from Task 5, the grade keys from Task 4.
- Produces: the dicts `APP`, `FIELDS`, `ACTIONS`, `COLUMNS`, `GRADES`, `SIDES`, `ERRORS`, `NOTES`, `PROGRESS`, and `text(group, key, **fields) -> str`.

**Rules for every string here** (from the `ux-writing` skill, English rules file):
- Sentence case. Contractions are fine. No exclamation marks.
- Buttons are `[verb] [object]`: "Use this band", never "OK" or "Submit".
- Errors are `[what happened]. [why]. [what to do]`. Never an error code alone, never blame.
- Help text says why the thing matters or what it costs, not what it obviously is.
- Never say "disconnect your VPN". A VPN is part of the user's connection; ask for one stable server instead.
- Never promise a product fact that isn't true. The lock really does survive a reboot; the password really is memory-only.

- [ ] **Step 1: Write the failing tests**

`tests/test_copy.py`:

```python
import re
import string

import pytest

from cpe_band_scan import copy


def all_strings():
    for group in (copy.APP, copy.GRADES, copy.SIDES, copy.ERRORS, copy.NOTES, copy.PROGRESS):
        for value in group.values():
            yield value if isinstance(value, str) else ""
    for group in (copy.FIELDS, copy.ACTIONS, copy.COLUMNS):
        for entry in group.values():
            for value in entry.values():
                yield value if isinstance(value, str) else ""


def test_every_field_and_action_and_column_explains_itself():
    for name, group in (("fields", copy.FIELDS), ("actions", copy.ACTIONS), ("columns", copy.COLUMNS)):
        for key, entry in group.items():
            assert entry.get("label") is not None, f"{name}.{key} has no label"
            assert entry.get("help", "").strip(), f"{name}.{key} has no ? text"


def test_no_string_asks_the_user_to_turn_off_a_vpn():
    for value in all_strings():
        lowered = value.lower()
        assert not ("vpn" in lowered and re.search(r"turn off|disconnect|disable", lowered)), value


BUTTON_VERBS = ("connect", "scan", "test", "use", "switch", "stop", "save", "open", "rename",
                "delete", "refresh")
ACTION_WORDS = ("try", "check", "wait", "enter", "switch", "open", "use", "keep", "scan",
                "stop", "change", "turn")


def test_every_button_label_starts_with_a_verb():
    """A button says what happens when you press it, so its first word is the action.
    A denylist of bad labels would not catch a noun like "Settings"."""
    for key, entry in copy.ACTIONS.items():
        first = entry["label"].split()[0].lower()
        assert first in BUTTON_VERBS, f"{key} does not start with a verb: {entry['label']}"


NO_ACTION_NEEDED = {"band_refused"}   # the scan handles this itself; the person does nothing


def test_every_error_ends_with_something_the_person_can_do():
    """A message that only describes the failure leaves the person stuck, so the last
    sentence carries an instruction. Match whole words: a substring check passes
    "usually" as "use", which is how the first version of this test passed a dead end."""
    for code, message in copy.ERRORS.items():
        if code in NO_ACTION_NEEDED:
            continue
        tail = [part for part in message.split(".") if part.strip()][-1].lower()
        tail = tail.replace(copy.APP["name"].lower(), "")   # "CPE Band Scan" contains an action word
        assert any(re.search(rf"\b{word}\b", tail) for word in ACTION_WORDS), \
            f"{code} dead-ends: {message}"


def test_error_placeholders_are_only_the_ones_callers_pass():
    allowed = {"url", "detail", "band", "bands", "name", "minutes", "count", "index",
               "total", "grade", "floor", "side", "sets"}
    for group in (copy.ERRORS, copy.NOTES, copy.PROGRESS):
        for key, message in group.items():
            fields = {name for _, name, _, _ in string.Formatter().parse(message) if name}
            assert fields <= allowed, f"{key} uses unknown placeholders: {fields - allowed}"


def test_text_fills_placeholders():
    assert "192.168.8.1" in copy.text("ERRORS", "unreachable", url="192.168.8.1")


def test_text_never_explodes_on_a_missing_placeholder():
    assert copy.text("ERRORS", "unreachable") != ""


@pytest.mark.parametrize("code", ["unreachable", "not_huawei_api", "bad_password", "locked_out",
                                  "firmware_not_supported", "no_band_lock", "api_refused",
                                  "band_refused", "busy", "no_results", "crash"])
def test_every_failure_the_engine_can_raise_has_a_message(code):
    assert copy.ERRORS[code]


@pytest.mark.parametrize("grade", ["excellent", "good", "fair", "poor", "no5g"])
def test_every_grade_has_a_label(grade):
    assert copy.GRADES[grade]
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_copy.py -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.copy'`.

- [ ] **Step 3: Write `src/cpe_band_scan/copy.py`**

```python
"""Every word the user reads. One file, so the terminal and the page never drift apart
and a translation is a second dict rather than a rewrite."""

APP = {
    "name": "CPE Band Scan",
    "tagline": "Find the band that gives you the steadiest connection.",
    "connect_heading": "Connect to your router",
    "connect_intro": "CPE Band Scan signs in to your router, measures each band it supports, and locks the "
                     "one that holds up best. Nothing is flashed, and you can switch back to automatic "
                     "at any time.",
    "status_heading": "Your connection now",
    "results_heading": "Band results, best first",
    "saved_heading": "Saved results",
    "test_heading": "2-minute test",
}

FIELDS = {
    "router_url": {
        "label": "Router address",
        "placeholder": "192.168.8.1",
        "help": "The address of your router's admin page. Most Huawei CPE routers answer at "
                "192.168.8.1, some at 192.168.1.1. If you're not sure, check the label on the router "
                "or open the address in a browser.",
    },
    "password": {
        "label": "Admin password",
        "placeholder": "",
        "help": "The password for the router's admin page, which is usually not your Wi-Fi password. "
                "CPE Band Scan keeps it in memory while it runs, never writes it to disk, and never sends "
                "it anywhere except your own router.",
    },
    "run_name": {
        "label": "Name",
        "placeholder": "MCI — living room",
        "help": "A name you'll recognise later, such as your carrier and where the router is standing. "
                "CPE Band Scan suggests your carrier and today's date. Results stay on this computer.",
    },
}

ACTIONS = {
    "connect": {
        "label": "Connect",
        "help": "Signs in and checks whether this router can lock bands. Nothing on the router changes.",
    },
    "scan_all": {
        "label": "Scan all bands",
        "help": "Locks each supported band in turn and measures it for about a minute, then ranks them. "
                "Takes 20 to 30 minutes, and your connection drops for about half a minute per band.",
    },
    "scan_4g": {
        "label": "Scan 4G bands",
        "help": "Measures the 4G bands only. On a 5G NSA network this is the scan that matters, because "
                "the 5G carrier follows whichever 4G band the router is anchored to.",
    },
    "scan_5g": {
        "label": "Scan 5G bands",
        "help": "Measures the 5G bands only. Useful to see which 5G bands are on air here.",
    },
    "test": {
        "label": "Test for 2 minutes",
        "help": "Watches the band you're on for 2 minutes without changing anything, then reports the "
                "lowest, typical and best quality it saw. Use it when two bands scored close.",
    },
    "apply": {
        "label": "Use this band",
        "help": "Locks the router to this band and keeps the other working bands as secondary carriers. "
                "The connection drops for about 30 seconds, then comes back. The lock survives a restart.",
    },
    "clear": {
        "label": "Switch back to automatic",
        "help": "Removes the lock so the router picks bands on its own again, the way it arrived.",
    },
    "cancel": {
        "label": "Stop the scan",
        "help": "Stops after the band being measured and puts the router back on automatic. Everything "
                "measured so far is kept.",
    },
    "save": {
        "label": "Save results",
        "help": "Stores this run on this computer under a name, so you can reopen it and compare it with "
                "a scan from another place or another provider.",
    },
    "open_run": {
        "label": "Open",
        "help": "Shows the full table and details of a saved run.",
    },
    "rename_run": {
        "label": "Rename",
        "help": "Changes the name of a saved run. The results stay as they were.",
    },
    "delete_run": {
        "label": "Delete",
        "help": "Removes this saved run from your computer. This can't be undone.",
    },
    "refresh": {
        "label": "Refresh",
        "help": "Reads the signal from the router again.",
    },
}

COLUMNS = {
    "rank": {"label": "#", "help": "Position in the ranking. The top row held the steadiest signal."},
    "band": {"label": "Band", "help": "The band that was locked while this row was measured. "
                                      "'Auto' is what your router chooses on its own, kept for comparison."},
    "grade": {"label": "Rating", "help": "The row in one word, from how far the quality dropped and how "
                                          "clean the channel was. Excellent and Good are safe picks."},
    "floor": {"label": "Lowest quality", "help": "The lowest SINR during the measurement, in dB. This is "
                                                  "what makes a call or a stream stutter. Above 0 is "
                                                  "usable, above 5 is comfortable."},
    "sinr": {"label": "Typical quality", "help": "The middle SINR reading of the measurement, in dB. "
                                                  "Higher is better."},
    "rsrq": {"label": "Channel quality", "help": "RSRQ in dB, how clean the channel is. Better than -12 "
                                                  "is healthy. Worse usually means interference or a busy "
                                                  "cell rather than distance."},
    "rsrp": {"label": "Signal strength", "help": "RSRP in dBm, the raw strength. Above -90 it barely "
                                                  "affects speed, so a band shouldn't be chosen on this "
                                                  "alone."},
    "nr_sinr": {"label": "5G quality", "help": "SINR of the 5G carrier in dB, when one was connected."},
    "five_g": {"label": "5G", "help": "Whether the 5G carrier stayed up on this band. Bands that lose it "
                                       "are never recommended."},
    "carriers": {"label": "Carriers", "help": "The carriers the router combined on this band. More "
                                               "carriers usually means more speed."},
}

GRADES = {"excellent": "Excellent", "good": "Good", "fair": "Fair", "poor": "Poor",
          "no5g": "Loses 5G"}

SIDES = {"lte": "4G", "nr": "5G", "trace": "test"}

ERRORS = {
    "unreachable": "Can't reach a router at {url}. Either that's not its address, or this computer isn't "
                   "on the router's network. Check the address and try again.",
    "not_huawei_api": "Something answered at {url}, but it isn't a Huawei router. Open that address in a "
                      "browser to see what's there, then enter the right one.",
    "bad_password": "That password didn't work. CPE Band Scan needs the password for the router's "
                    "admin page, which is usually not the Wi-Fi password. Check the label on the "
                    "router and try again.",
    "locked_out": "The router is refusing sign-ins for a few minutes after too many wrong passwords. "
                  "Wait 5 minutes, then try again.",
    "firmware_not_supported": "This router runs firmware {detail}, and CPE Band Scan can only lock "
                              "bands on firmware 4. Older firmware uses a different interface, and "
                              "writing to it blindly can switch 5G off, so CPE Band Scan won't try. "
                              "If this router gets a firmware 4 update later, try again.",
    "no_band_lock": "This router signed in, but it has no band-lock page ({detail}), so CPE Band "
                    "Scan can't change its bands. Check the address if this is not the router you "
                    "meant, and try again after any firmware update.",
    "api_refused": "The router refused the request ({detail}). This is usually temporary. Wait a moment "
                   "and try again.",
    "band_refused": "The router refused band {band}, so the scan skipped it. It's on the supported list "
                    "but isn't usable on this network. The scan keeps going with the rest.",
    "busy": "A scan is already running. Stop it first, or wait for it to finish.",
    "no_results": "No band held a working connection, so nothing was locked. The router is back on "
                  "automatic. Try again from a spot with better reception, or scan one side at a "
                  "time with Scan 4G bands.",
    "crash": "CPE Band Scan stopped on an unexpected problem ({detail}). The router has been put back on "
             "automatic. Try again, and keep this message if it happens twice.",
}

NOTES = {
    "before_scan": "Scanning interrupts your connection. CPE Band Scan locks each band in turn, so the "
                   "internet drops for about 30 seconds every time it moves to the next one. Expect "
                   "20 to 30 minutes in all. You can keep working between the drops.",
    "vpn": "A VPN is fine to keep on. Stay on one server for the whole scan, because switching servers "
           "mid-run changes what you feel while the measurements stay the same. If CPE Band Scan can't reach "
           "the router while the VPN is up, switch on your VPN's local network access setting.",
    "password_note": "The password stays in memory while CPE Band Scan runs and is never saved. Change it "
                     "afterwards if someone else may have seen it.",
    "lock_survives": "The lock stays in place after a restart. Switch back to automatic whenever you want.",
    "rescan_hint": "Scan again after you move the router, change SIM, or change provider.",
    "empty_runs": "No saved results yet. Finish a scan and save it, and it'll be here to compare against.",
    "empty_results": "No results yet. Start a scan to fill this table.",
    "auto_row": "Auto is what your router chose by itself, measured the same way for comparison.",
}

PROGRESS = {
    "run_start": "Starting. CPE Band Scan measures one band at a time and ranks them at the end.",
    "side_start": "Measuring the {side} bands: {count} to go, about {minutes} minutes.",
    "set_start": "Measuring {name}, {index} of {total}. About {minutes} minutes left.",
    "set_result": "{name} scored {grade}, lowest quality {floor} dB.",
    "no_service": "{name} has no service here, so it was skipped.",
    "refused": "{name} was refused by the router, so it was skipped.",
    "side_done": "Finished the {side} bands: {count} measured.",
    "applied": "Locked to {bands}. Your connection is back.",
    "cancelled": "Scan stopped. The router is back on automatic.",
    "trace_start": "Watching your current band for {minutes} minutes. Nothing changes while this runs.",
    "trace_done": "Test finished.",
    "done": "Scan finished.",
    "saved": "Saved as {name}.",
}

_GROUPS = {"APP": APP, "FIELDS": FIELDS, "ACTIONS": ACTIONS, "COLUMNS": COLUMNS, "GRADES": GRADES,
           "SIDES": SIDES, "ERRORS": ERRORS, "NOTES": NOTES, "PROGRESS": PROGRESS}


class _Blank(dict):
    def __missing__(self, key):
        return ""


def text(group: str, key: str, **fields) -> str:
    """A string with its placeholders filled. A missing placeholder empties out rather than
    raising: a half-filled sentence still helps, a traceback does not."""
    value = _GROUPS[group].get(key, "")
    if isinstance(value, dict):
        value = value.get("label", "")
    return value.format_map(_Blank(fields))


def bundle() -> dict:
    """Everything the page needs, injected into it at load time."""
    return {name: group for name, group in _GROUPS.items()}
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed. `test_error_placeholders_are_only_the_ones_callers_pass` will point at any placeholder you invented; either use an allowed one or add it to the allowed set in the test and to the caller.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: one catalogue for every user-facing string"
```

---

## Task 8: The command line front end

**Files:**
- Create: `src/cpe_band_scan/cli.py`, `src/cpe_band_scan/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 1-7.
- Produces: `main(argv=None) -> int`, `render(event) -> str | None`, `connect(args) -> tuple[Router, Device]`, `read_password(args) -> str`.
- Commands: `cpe-band-scan ui`, `status`, `scan [4g|5g] [bands...]`, `test`, `apply <bands> [--scell 3,40] [--nr 78]`, `clear`, `runs`, `show <id>`, `help`.
- Password lookup order: `--password`, `CPE_BAND_SCAN_PASSWORD`, a `PASSWORD=` line in `./.env`, then an interactive `getpass` prompt. Never a command-line default, never echoed.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
import pytest

from cpe_band_scan import cli, copy


def test_render_turns_an_event_into_a_sentence():
    line = cli.render({"type": "set_start", "name": "B7", "index": 3, "total": 18, "eta_s": 600})
    assert "B7" in line and "3 of 18" in line


def test_render_names_the_grade_in_words():
    line = cli.render({"type": "set_result", "name": "B7",
                       "result": {"grade": "excellent", "floor": 7.0}})
    assert copy.GRADES["excellent"] in line


def test_render_ignores_events_with_nothing_to_say():
    assert cli.render({"type": "run_start", "sides": ["lte"], "expect_5g": True, "baseline": {}}) is not None
    assert cli.render({"type": "nonsense"}) is None


def test_the_password_comes_from_the_environment_before_prompting(monkeypatch):
    monkeypatch.setenv("CPE_BAND_SCAN_PASSWORD", "from-env")
    assert cli.read_password(cli.parse(["status"])) == "from-env"


def test_the_password_comes_from_a_dot_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CPE_BAND_SCAN_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PASSWORD='shh'\n", encoding="utf-8")
    assert cli.read_password(cli.parse(["status"])) == "shh"


def test_the_default_router_address_is_the_huawei_one():
    assert cli.parse(["status"]).url == "http://192.168.8.1/"


def test_apply_parses_anchors_secondaries_and_the_nr_side():
    args = cli.parse(["apply", "7", "--scell", "3,40", "--nr", "78"])
    assert (args.bands, args.scell, args.nr) == ("7", "3,40", "78")


def test_help_lists_every_command(capsys):
    assert cli.main(["help"]) == 0
    printed = capsys.readouterr().out
    for command in ("scan", "status", "test", "apply", "clear", "runs", "ui"):
        assert command in printed


def test_a_router_error_prints_the_sentence_not_a_traceback(capsys, monkeypatch):
    from cpe_band_scan.router import RouterError

    def explode(args):
        raise RouterError("bad_password")

    monkeypatch.setattr(cli, "connect", explode)
    monkeypatch.setenv("CPE_BAND_SCAN_PASSWORD", "x")
    assert cli.main(["status"]) == 1
    assert copy.ERRORS["bad_password"][:30] in capsys.readouterr().err
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_cli.py -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.cli'`.

- [ ] **Step 3: Write `src/cpe_band_scan/cli.py`**

```python
"""The terminal front end. It prints what the engine yields and nothing else."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from . import copy, lockfreq, metrics, scanner, store
from .device import probe
from .router import Router, RouterError

DEFAULT_URL = "http://192.168.8.1/"


def parse(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cpe-band-scan", description=copy.APP["tagline"], add_help=False)
    parser.add_argument("--url", default=os.environ.get("CPE_BAND_SCAN_URL", DEFAULT_URL))
    parser.add_argument("--user", default=os.environ.get("CPE_BAND_SCAN_USER", "admin"))
    parser.add_argument("--password", default=None)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("help")
    subparsers.add_parser("status")
    subparsers.add_parser("clear")
    subparsers.add_parser("runs")
    subparsers.add_parser("test")
    ui = subparsers.add_parser("ui")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--no-browser", action="store_true")
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("side", nargs="?", choices=["4g", "5g"], default=None)
    scan_parser.add_argument("bands", nargs="*", default=[])
    scan_parser.add_argument("--save", dest="save_name", default=None)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("bands")
    apply_parser.add_argument("--scell", default="")
    apply_parser.add_argument("--nr", default="")
    show = subparsers.add_parser("show")
    show.add_argument("run_id")
    args = parser.parse_args(argv)
    args.url = args.url if args.url.startswith("http") else f"http://{args.url}/"
    return args


def read_password(args) -> str:
    if getattr(args, "password", None):
        return args.password
    from_env = os.environ.get("CPE_BAND_SCAN_PASSWORD")
    if from_env:
        return from_env
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "PASSWORD" and value.strip():
                return value.strip().strip("'\"")
    return getpass.getpass(f"{copy.FIELDS['password']['label']}: ")


def connect(args):
    router = Router(args.url, read_password(args), username=args.user)
    return router, probe(router)


def render(event) -> str | None:
    kind = event.get("type")
    if kind == "run_start":
        return copy.text("PROGRESS", "run_start", count=len(event.get("sides", [])))
    if kind == "side_start":
        return copy.text("PROGRESS", "side_start", side=copy.SIDES[event["side"]],
                         count=event["total"], minutes=max(1, round(event["eta_s"] / 60)))
    if kind == "set_start":
        return copy.text("PROGRESS", "set_start", name=event["name"], index=event["index"],
                         total=event["total"], minutes=max(1, round(event["eta_s"] / 60)))
    if kind == "set_result":
        result = event["result"]
        return copy.text("PROGRESS", "set_result", name=event["name"],
                         grade=copy.GRADES[result["grade"]], floor=f"{result['floor']:g}")
    if kind == "set_skipped":
        return copy.text("PROGRESS", event["reason"], name=event["name"])
    if kind == "side_done":
        return copy.text("PROGRESS", "side_done", side=copy.SIDES[event["side"]],
                         count=len(event["results"]))
    if kind == "applied":
        return copy.text("PROGRESS", "applied", bands=",".join(event["plan"]["lte"] or event["plan"]["nr"]))
    if kind == "cancelled":
        return copy.text("PROGRESS", "cancelled")
    if kind == "trace_start":
        return copy.text("PROGRESS", "trace_start", minutes=round(event["seconds"] / 60))
    if kind == "trace_sample":
        row = event["sample"]
        return f"{event['at_s']:>4}s  {row['band']}  SINR {row['sinr']:g}  RSRQ {row['rsrq']:g}"
    if kind in ("trace_done", "done"):
        return copy.text("PROGRESS", kind if kind == "trace_done" else "done")
    if kind == "error":
        return copy.text("ERRORS", event.get("code", "crash"), detail=event.get("detail", ""))
    return None


def results_table(run: dict) -> str:
    """The same columns the page shows, in markdown, best first."""
    keys = ("rank", "band", "grade", "floor", "sinr", "rsrq", "rsrp", "five_g", "carriers")
    header = [copy.COLUMNS[key]["label"] or "-" for key in keys]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(keys)]
    for side, record in run.get("sides", {}).items():
        for position, name in enumerate(record["order"] + [n for n in record["results"]
                                                           if n not in record["order"]], 1):
            row = record["results"][name]
            lines.append("| " + " | ".join([
                str(position), name, copy.GRADES[row["grade"]], f"{row['floor']:g}", f"{row['sinr']:g}",
                f"{row['rsrq']:g}", f"{row['rsrp']:g}", "yes" if row["has5g"] else "no", row["band"],
            ]) + " |")
    return "\n".join(lines)


def _print_help() -> int:
    print(f"{copy.APP['name']} — {copy.APP['tagline']}\n")
    rows = [("ui", copy.ACTIONS["scan_all"]["help"]),
            ("scan", copy.ACTIONS["scan_all"]["help"]),
            ("scan 4g", copy.ACTIONS["scan_4g"]["help"]),
            ("scan 5g", copy.ACTIONS["scan_5g"]["help"]),
            ("status", copy.ACTIONS["refresh"]["help"]),
            ("test", copy.ACTIONS["test"]["help"]),
            ("apply <bands>", copy.ACTIONS["apply"]["help"]),
            ("clear", copy.ACTIONS["clear"]["help"]),
            ("runs", copy.ACTIONS["open_run"]["help"]),
            ("show <id>", copy.ACTIONS["open_run"]["help"])]
    width = max(len(name) for name, _ in rows)
    for name, description in rows:
        print(f"  {name:<{width}}  {description}")
    print(f"\n{copy.NOTES['vpn']}\n{copy.NOTES['password_note']}")
    return 0


def main(argv=None) -> int:
    args = parse(argv)
    command = args.command or "help"
    if command == "help":
        return _print_help()
    if command == "ui":
        from .server import serve
        return serve(port=args.port, open_browser=not args.no_browser)
    if command == "runs":
        rows = store.list_runs()
        if not rows:
            print(copy.NOTES["empty_runs"])
        for row in rows:
            print(f"{row['id']}  {row['name']}  ({row['kind']}, best {row['best'] or '-'})")
        return 0
    if command == "show":
        run = store.load(args.run_id)
        print(run["name"])
        print(results_table(run))
        return 0

    try:
        router, device = connect(args)
        print(f"{device.model} · firmware {device.firmware} · {device.carrier or '-'}")
        if command == "status":
            print(json.dumps({"lock": lockfreq.read_lock(router), "signal": metrics.sample(router),
                              "visible": metrics.visible_bands(router)}, indent=2, default=str))
        elif command == "clear":
            lockfreq.lock(router)
            print(copy.text("ACTIONS", "clear"))
        elif command == "apply":
            lockfreq.lock(router, lte=args.bands.split(","),
                          lte_scell=[b for b in args.scell.split(",") if b],
                          nr=[b for b in args.nr.split(",") if b])
            print(copy.text("PROGRESS", "applied", bands=args.bands))
        elif command == "test":
            run = None
            for event in scanner.trace(router):
                line = render(event)
                if line:
                    print(f"[{datetime.now():%H:%M:%S}] {line}", flush=True)
                if event["type"] == "trace_done":
                    run = event["run"]
            saved = store.save(run, name=store.default_name(device.carrier))
            print(copy.text("PROGRESS", "saved", name=saved["name"]))
        elif command == "scan":
            sides = {"4g": ("lte",), "5g": ("nr",)}.get(args.side, ("lte", "nr"))
            print(copy.NOTES["before_scan"])
            print(copy.NOTES["vpn"])
            run = None
            for event in scanner.scan(router, device, sides=sides, bands=args.bands or None):
                line = render(event)
                if line:
                    print(f"[{datetime.now():%H:%M:%S}] {line}", flush=True)
                if event["type"] == "done":
                    run = event["run"]
            print("\n" + results_table(run))
            saved = store.save(run, name=args.save_name or store.default_name(device.carrier))
            print(copy.text("PROGRESS", "saved", name=saved["name"]))
        return 0
    except RouterError as error:
        print(copy.text("ERRORS", error.code, url=args.url, detail=error.detail), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(copy.text("PROGRESS", "cancelled"), file=sys.stderr)
        return 130
    except Exception as error:       # the catalogue has a sentence for this; a traceback is not one
        print(copy.text("ERRORS", "crash", detail=repr(error)), file=sys.stderr)
        return 1
```

`src/cpe_band_scan/__main__.py`:

```python
from .cli import main

raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: command line front end"
```

---

## Task 9: The local server — session, guard, page, connect, status

**Files:**
- Create: `src/cpe_band_scan/server.py`, `src/cpe_band_scan/web/index.html` (placeholder shell, filled in Task 12)
- Modify: `src/cpe_band_scan/copy.py` (add the `not_connected` error), `tests/test_copy.py` (add it to the parametrised list)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: Tasks 1-7.
- Produces: `Session(router_factory=Router)` with `.token`, `.connect(url, password, username)`, `.require_router()`, `.running()`, `.start(kind, make_events)`, `.cancelled`; `Handler`; `serve(port=8765, open_browser=True, session=None) -> int`.
- API so far: `GET /` (the page, token injected), `GET /app.js`, `GET /style.css`, `POST /api/connect`, `GET /api/status`.

**Security shape:** bind `127.0.0.1`; refuse any request whose `Host` is not `127.0.0.1` or `localhost` (blocks DNS rebinding); refuse any `/api/*` request without the exact `X-CPE-Band-Scan-Token` the page was served with. A hostile page in another browser tab can send a request but cannot read our page to learn the token, and a custom header forces a preflight it cannot pass.

- [ ] **Step 1: Add the missing error to the copy catalogue**

In `src/cpe_band_scan/copy.py`, inside `ERRORS`:

```python
    "not_connected": "Not signed in to a router yet. Enter the router address and admin password, "
                     "then connect.",
```

And add `"not_connected"` to the parametrised list in `tests/test_copy.py::test_every_failure_the_engine_can_raise_has_a_message`.

- [ ] **Step 2: Write the failing tests**

`tests/test_server.py`:

```python
import http.client
import json
import threading

import pytest
from huawei_lte_api import exceptions as hx

from cpe_band_scan import server
from cpe_band_scan.router import Router
from tests.fakes import FakeSession, Seq, factory
from tests.test_device import SUPPORTED


def fake_router_factory(data=None, connect_error=None):
    def make(url, password, username="admin"):
        return Router(url, password, username=username,
                      connection_factory=factory(FakeSession(dict(SUPPORTED, **(data or {}))),
                                                 connect_error=connect_error))
    return make


@pytest.fixture
def live(request):
    """A server on a free port, torn down after the test."""
    session = server.Session(router_factory=getattr(request, "param", fake_router_factory()))
    httpd = server.build(port=0, session=session)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield session, httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def call(port, method, path, body=None, token=None, host=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-CPE-Band-Scan-Token"] = token
    if host:
        headers["Host"] = host
    connection.request(method, path, json.dumps(body) if body is not None else None, headers)
    response = connection.getresponse()
    payload = response.read()
    try:
        return response.status, json.loads(payload)
    except ValueError:
        return response.status, payload.decode()


def test_the_page_carries_the_token_and_the_copy(live):
    session, port = live
    status, body = call(port, "GET", "/")
    assert status == 200
    assert session.token in body
    assert "Router address" in body, "the copy bundle must reach the page"


def test_an_api_call_without_the_token_is_refused(live):
    _, port = live
    assert call(port, "GET", "/api/status")[0] == 403


def test_an_api_call_from_another_host_name_is_refused(live):
    session, port = live
    status, _ = call(port, "GET", "/api/status", token=session.token, host="router.attacker.test")
    assert status == 403


def test_connecting_reports_the_device_and_suggests_a_name(live):
    session, port = live
    status, body = call(port, "POST", "/api/connect",
                        {"url": "192.168.8.1", "password": "pw"}, token=session.token)
    assert status == 200
    assert body["device"]["model"] == "H155-381"
    assert body["suggested_name"].startswith("MCI — ")


@pytest.mark.parametrize("live", [fake_router_factory(
    connect_error=hx.LoginErrorUsernamePasswordWrongException("no", 108001))], indirect=True)
def test_a_wrong_password_comes_back_as_a_sentence_not_a_code(live):
    session, port = live
    status, body = call(port, "POST", "/api/connect",
                        {"url": "192.168.8.1", "password": "nope"}, token=session.token)
    assert status == 409
    assert body["error"] == "bad_password"
    assert "admin page" in body["message"]


@pytest.mark.parametrize("live", [fake_router_factory(
    {"device/information": {"DeviceName": "B525", "SoftwareVersion": "3.11.1"}})], indirect=True)
def test_an_unsupported_router_explains_why(live):
    session, port = live
    status, body = call(port, "POST", "/api/connect",
                        {"url": "192.168.8.1", "password": "pw"}, token=session.token)
    assert status == 409
    assert body["error"] == "firmware_not_supported"
    assert "3.11.1" in body["message"]


def test_status_before_connecting_says_so(live):
    session, port = live
    status, body = call(port, "GET", "/api/status", token=session.token)
    assert status == 409
    assert body["error"] == "not_connected"


def test_status_after_connecting_returns_the_signal_and_the_lock(live):
    session, port = live
    call(port, "POST", "/api/connect", {"url": "192.168.8.1", "password": "pw"}, token=session.token)
    status, body = call(port, "GET", "/api/status", token=session.token)
    assert status == 200
    assert "signal" in body and "lock" in body and body["device"]["carrier"] == "MCI"
```

Add `"device/signal"` to `tests/test_device.py::SUPPORTED` so the status call has something to read:

```python
    "device/signal": {"band": "B7(N78)", "sinr": "8dB", "rsrq": "-10dB", "rsrp": "-85dBm",
                      "nrsinr": "12", "nrrsrp": "-80"},
    "device/nbrcellinfo": {},
    "device/seccellinfo": {},
```

- [ ] **Step 3: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_server.py -q
```
Expected: `ModuleNotFoundError: No module named 'cpe_band_scan.server'`.

- [ ] **Step 4: Write the page placeholder**

`src/cpe_band_scan/web/index.html` — the real page arrives in Task 12; this is enough to serve and test:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CPE Band Scan</title>
<link rel="stylesheet" href="/style.css">
<script>/*BOOTSTRAP*/</script>
</head>
<body>
<main id="app"></main>
<script src="/app.js"></script>
</body>
</html>
```

Create empty `src/cpe_band_scan/web/app.js` and `src/cpe_band_scan/web/style.css` for now.

- [ ] **Step 5: Write `src/cpe_band_scan/server.py`**

```python
"""The local web front end.

It binds 127.0.0.1 and every /api call must carry the token that was baked into the page.
A hostile site in another tab can fire a request at localhost, but it can't read our page to
learn the token, and the custom header forces a preflight it can't satisfy. The Host check
blocks DNS rebinding.
"""
from __future__ import annotations

import hmac
import json
import secrets
import socketserver
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import copy, lockfreq, metrics, scanner, store
from .device import probe
from .router import Router, RouterError

WEB = Path(__file__).parent / "web"
DEFAULT_URL = "http://192.168.8.1/"
SLEEP = time.sleep          # read at call time so tests can run a scan without real waits
ALLOWED_HOSTS = ("127.0.0.1", "localhost")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8"}


def _default_router(url, password, username="admin"):
    return Router(url, password, username=username)


class Session:
    """One router and one job at a time. Held in memory; nothing here reaches the disk."""

    def __init__(self, router_factory=_default_router):
        self.token = secrets.token_urlsafe(24)
        self._router_factory = router_factory
        self._lock = threading.Lock()
        self.router = None
        self.device = None
        self.events = []
        self.kind = ""
        self.thread = None
        self.cancelled = False

    def connect(self, url, password, username="admin"):
        router = self._router_factory(url or DEFAULT_URL, password, username)
        self.device = probe(router)          # raises RouterError carrying the reason
        self.router = router
        return self.device

    def require_router(self) -> Router:
        if self.router is None:
            raise RouterError("not_connected")
        return self.router

    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()


class Handler(BaseHTTPRequestHandler):
    session: Session = None
    server_version = "cpe-band-scan"

    def log_message(self, *args):
        pass                                   # the terminal is for progress, not request logs

    def _send(self, status, body: bytes, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload, status=200):
        self._send(status, json.dumps(payload, default=str).encode(), "application/json")

    def _fail(self, code, status=409, **fields):
        self._json({"error": code, "message": copy.text("ERRORS", code, **fields)}, status)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return {}

    def _host_allowed(self) -> bool:
        """The page and its assets are gated on this alone: they carry the token, so a
        rebound hostname must not be able to read them."""
        if (self.headers.get("Host") or "").split(":")[0] in ALLOWED_HOSTS:
            return True
        self._json({"error": "forbidden"}, 403)
        return False

    def _allowed(self) -> bool:
        if not self._host_allowed():
            return False
        if not hmac.compare_digest(self.headers.get("X-CPE-Band-Scan-Token") or "",
                                   self.session.token):
            self._json({"error": "forbidden"}, 403)
            return False
        return True

    def _page(self):
        bootstrap = json.dumps({"token": self.session.token, "copy": copy.bundle(),
                                "defaults": {"url": DEFAULT_URL}})
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self._send(200, html.replace("/*BOOTSTRAP*/", f"window.CPE_BAND_SCAN = {bootstrap};").encode(),
                   TYPES[".html"])

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/app.js", "/style.css") and not self._host_allowed():
            return
        if path in ("/", "/index.html"):
            return self._page()
        if path in ("/app.js", "/style.css"):
            asset = WEB / path.lstrip("/")
            return self._send(200, asset.read_bytes(), TYPES[asset.suffix])
        if not path.startswith("/api/") or not self._allowed():
            return
        try:
            if path == "/api/status":
                router = self.session.require_router()
                return self._json({"device": self.session.device.as_dict(),
                                   "lock": lockfreq.read_lock(router),
                                   "signal": metrics.sample(router),
                                   "visible": metrics.visible_bands(router),
                                   "running": self.session.running()})
        except RouterError as error:
            return self._fail(error.code, detail=error.detail,
                              url=getattr(self.session.router, "url", ""))
        self._json({"error": "not_found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._json({"error": "not_found"}, 404)
        if not self._allowed():
            return
        body = self._body()
        try:
            if path == "/api/connect":
                device = self.session.connect(body.get("url") or DEFAULT_URL,
                                              body.get("password") or "",
                                              body.get("username") or "admin")
                return self._json({"device": device.as_dict(),
                                   "suggested_name": store.default_name(device.carrier)})
        except RouterError as error:
            return self._fail(error.code, detail=error.detail, url=body.get("url") or DEFAULT_URL)
        self._json({"error": "not_found"}, 404)


class LocalServer(ThreadingHTTPServer):
    """Bind without the reverse DNS lookup HTTPServer does by default: on a machine whose
    resolver is slow or VPN-routed it blocks for tens of seconds before the page is reachable,
    and the name it resolves is only used for CGI variables this server never emits."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = "127.0.0.1"
        self.server_port = self.server_address[1]


def build(port=8765, session=None) -> LocalServer:
    Handler.session = session or Session()
    return LocalServer(("127.0.0.1", port), Handler)


def serve(port=8765, open_browser=True, session=None) -> int:
    for attempt in range(10):
        try:
            httpd = build(port + attempt, session)
            break
        except OSError:
            continue
    else:
        raise SystemExit(copy.text("ERRORS", "busy"))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"{copy.APP['name']} — {url}")
    print(copy.NOTES["password_note"])
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
```

- [ ] **Step 6: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed. `test_the_page_carries_the_token_and_the_copy` also proves the copy bundle reaches the browser.

- [ ] **Step 7: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: local server with a token-guarded API"
```

---

## Task 10: The job API — scan, test, progress, cancel, apply

**Files:**
- Modify: `src/cpe_band_scan/server.py`
- Test: `tests/test_server_jobs.py`

**Interfaces:**
- Consumes: `Session` from Task 9, `scanner.scan`, `scanner.trace`, `lockfreq.lock`.
- Produces: `Session.start(kind, make_events)`, `Session.cancel()`; endpoints `POST /api/scan`, `POST /api/test`, `POST /api/cancel`, `POST /api/apply`, `POST /api/clear`, `GET /api/events?since=N`.
- `GET /api/events` answers `{"since": int, "events": [...], "running": bool, "kind": str}`. The page polls it every 2 seconds with the `since` it was last given, so a reload or a sleeping laptop loses nothing.

**Why polling and not server-sent events:** the page and the server are both on this machine, so the router's 30-second drops never touch this connection. Polling survives a page reload for free, in a third of the code.

- [ ] **Step 1: Write the failing tests**

`tests/test_server_jobs.py`:

```python
import time

import pytest

from cpe_band_scan import server
from tests.test_server import call, fake_router_factory, live  # noqa: F401  (live is a fixture)


def connect(port, session):
    return call(port, "POST", "/api/connect", {"url": "192.168.8.1", "password": "pw"},
                token=session.token)


def drain(port, session, timeout=5):
    """Poll until the job reports it has finished."""
    since, events = 0, []
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, body = call(port, "GET", f"/api/events?since={since}", token=session.token)
        since, new = body["since"], body["events"]
        events += new
        if any(event["type"] == "finished" for event in new):
            return events
        time.sleep(0.05)
    raise AssertionError(f"job never finished; saw {[e['type'] for e in events]}")


def test_a_scan_cannot_start_before_connecting(live):
    session, port = live
    status, body = call(port, "POST", "/api/scan", {}, token=session.token)
    assert status == 409 and body["error"] == "not_connected"


def test_a_scan_streams_events_and_finishes(live, monkeypatch):
    monkeypatch.setattr(server.scanner, "SETTLE", 0)
    session, port = live
    connect(port, session)
    assert call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["7"]},
                token=session.token)[0] == 200
    events = drain(port, session)
    kinds = [event["type"] for event in events]
    assert "set_start" in kinds and "done" in kinds and kinds[-1] == "finished"


def test_events_are_only_delivered_once(live, monkeypatch):
    monkeypatch.setattr(server.scanner, "SETTLE", 0)
    session, port = live
    connect(port, session)
    call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["7"]}, token=session.token)
    drain(port, session)
    _, body = call(port, "GET", f"/api/events?since={len(session.events)}", token=session.token)
    assert body["events"] == []
    assert body["running"] is False


def test_a_second_scan_while_one_runs_is_refused(live, monkeypatch):
    session, port = live
    connect(port, session)
    session.thread = type("Alive", (), {"is_alive": lambda self: True})()
    status, body = call(port, "POST", "/api/scan", {"sides": ["lte"]}, token=session.token)
    assert status == 409 and body["error"] == "busy"


def test_cancelling_sets_the_flag_the_engine_reads(live):
    session, port = live
    connect(port, session)
    assert call(port, "POST", "/api/cancel", {}, token=session.token)[0] == 200
    assert session.cancelled is True


def test_a_crash_inside_the_job_becomes_an_error_event_not_a_dead_poll(live, monkeypatch):
    session, port = live
    connect(port, session)

    def explode(*args, **kwargs):
        raise ZeroDivisionError("boom")

    monkeypatch.setattr(server.scanner, "scan", explode)
    call(port, "POST", "/api/scan", {"sides": ["lte"]}, token=session.token)
    events = drain(port, session)
    assert events[0]["type"] == "error" and events[0]["code"] == "crash"


def test_applying_a_band_locks_it(live):
    session, port = live
    connect(port, session)
    status, _ = call(port, "POST", "/api/apply", {"lte": ["7"], "scell": ["3"]}, token=session.token)
    assert status == 200


def test_clearing_returns_the_router_to_automatic(live):
    session, port = live
    connect(port, session)
    assert call(port, "POST", "/api/clear", {}, token=session.token)[0] == 200


def test_a_two_minute_test_runs_as_a_job(live, monkeypatch):
    session, port = live
    connect(port, session)
    call(port, "POST", "/api/test", {"seconds": 20, "gap": 10}, token=session.token)
    events = drain(port, session)
    assert [event["type"] for event in events][:2] == ["trace_start", "trace_sample"]
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_server_jobs.py -q
```
Expected: failures on `POST /api/scan` returning 404.

- [ ] **Step 3: Add the job machinery to `Session`**

Insert into `class Session`, after `running`:

```python
    def start(self, kind: str, make_events):
        """Run an event generator on a worker thread. One job at a time, always."""
        with self._lock:
            if self.running():
                raise RouterError("busy")
            self.events, self.kind, self.cancelled = [], kind, False
            self.thread = threading.Thread(target=self._drive, args=(make_events,), daemon=True)
            self.thread.start()

    def cancel(self) -> None:
        self.cancelled = True

    def _drive(self, make_events):
        try:
            for event in make_events(lambda: self.cancelled):
                self.events.append(event)
        except RouterError as error:
            self.events.append({"type": "error", "code": error.code, "detail": error.detail,
                                "message": copy.text("ERRORS", error.code, detail=error.detail)})
        except Exception as error:                      # a crash must still reach the page
            self.events.append({"type": "error", "code": "crash", "detail": repr(error),
                                "message": copy.text("ERRORS", "crash", detail=repr(error))})
        finally:
            self.events.append({"type": "finished", "kind": self.kind})
```

`self.events.append` is safe across threads without a lock, and readers take a slice; no locking needed for the event buffer.

- [ ] **Step 4: Add the routes**

In `do_GET`, inside the `try`, before the final `_json(... 404)`:

```python
            if path == "/api/events":
                since = int(parse_qs(urlparse(self.path).query).get("since", ["0"])[0])
                events = self.session.events[since:]
                return self._json({"since": since + len(events), "events": events,
                                   "running": self.session.running(), "kind": self.session.kind})
```

In `do_POST`, inside the `try`, after the `/api/connect` branch:

```python
            if path == "/api/scan":
                router, device = self.session.require_router(), self.session.device
                sides = tuple(body.get("sides") or ("lte", "nr"))
                bands = body.get("bands") or None
                self.session.start("scan", lambda cancelled: scanner.scan(
                    router, device, sides=sides, bands=bands, cancelled=cancelled, sleep=SLEEP))
                return self._json({"started": True})
            if path == "/api/test":
                router = self.session.require_router()
                seconds, gap = int(body.get("seconds") or 120), int(body.get("gap") or 10)
                self.session.start("test", lambda cancelled: scanner.trace(
                    router, seconds=seconds, gap=gap, cancelled=cancelled, sleep=SLEEP))
                return self._json({"started": True})
            if path == "/api/cancel":
                self.session.cancel()
                return self._json({"cancelling": True})
            if path == "/api/apply":
                router = self.session.require_router()
                current = lockfreq.read_lock(router)     # an absent side keeps the lock it has:
                lte = body["lte"] if "lte" in body else current["lte"][0]      # applying a 4G band
                scell = body["scell"] if "scell" in body else current["lte"][1]  # must not drop 5G
                nr = body["nr"] if "nr" in body else current["nr"][0]
                lockfreq.lock(router, lte=lte, lte_scell=scell, nr=nr)
                return self._json({"applied": True})
            if path == "/api/clear":
                lockfreq.lock(self.session.require_router())
                return self._json({"applied": True})
```

- [ ] **Step 5: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed. If `test_a_scan_streams_events_and_finishes` times out, check that `scanner.SETTLE` is read at call time rather than captured at import.

- [ ] **Step 6: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: run scans as background jobs the page can follow"
```

---

## Task 11: The saved-runs API

**Files:**
- Modify: `src/cpe_band_scan/server.py`
- Test: `tests/test_server_runs.py`

**Interfaces:**
- Consumes: `store` from Task 6.
- Produces: `GET /api/runs`, `GET /api/runs/<id>`, `POST /api/runs` (save `{run, name}`), `POST /api/runs/<id>/rename` (`{name}`), `DELETE /api/runs/<id>`.
- The page never invents a run document: it saves back the one it received in the `done` event, so what's stored is exactly what the engine produced.

- [ ] **Step 1: Write the failing tests**

`tests/test_server_runs.py`:

```python
import pytest

from tests.test_server import call, fake_router_factory, live  # noqa: F401

RUN = {"kind": "scan", "device": {"carrier": "MCI"},
       "sides": {"lte": {"order": ["B7"], "results": {"B7": {"floor": 7}}, "sets": {"B7": ["7"]},
                         "skipped": {}}}}


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CPE_BAND_SCAN_HOME", str(tmp_path))


def test_an_empty_list_is_an_empty_list_not_an_error(live):
    session, port = live
    status, body = call(port, "GET", "/api/runs", token=session.token)
    assert status == 200 and body["runs"] == []


def test_saving_returns_the_stored_run_with_its_name_and_id(live):
    session, port = live
    status, body = call(port, "POST", "/api/runs", {"run": RUN, "name": "Living room"},
                        token=session.token)
    assert status == 200
    assert body["run"]["name"] == "Living room"
    assert body["run"]["id"]


def test_a_saved_run_can_be_opened_again(live):
    session, port = live
    _, saved = call(port, "POST", "/api/runs", {"run": RUN}, token=session.token)
    status, body = call(port, "GET", f"/api/runs/{saved['run']['id']}", token=session.token)
    assert status == 200 and body["run"]["sides"]["lte"]["order"] == ["B7"]


def test_renaming_keeps_the_results(live):
    session, port = live
    _, saved = call(port, "POST", "/api/runs", {"run": RUN}, token=session.token)
    status, body = call(port, "POST", f"/api/runs/{saved['run']['id']}/rename", {"name": "Bedroom"},
                        token=session.token)
    assert status == 200 and body["run"]["name"] == "Bedroom"
    assert body["run"]["sides"]["lte"]["order"] == ["B7"]


def test_deleting_removes_it(live):
    session, port = live
    _, saved = call(port, "POST", "/api/runs", {"run": RUN}, token=session.token)
    assert call(port, "DELETE", f"/api/runs/{saved['run']['id']}", token=session.token)[0] == 200
    assert call(port, "GET", "/api/runs", token=session.token)[1]["runs"] == []


def test_an_unknown_run_is_a_404_not_a_crash(live):
    session, port = live
    assert call(port, "GET", "/api/runs/20260101-000000", token=session.token)[0] == 404


def test_a_run_id_that_walks_the_filesystem_is_refused(live):
    session, port = live
    assert call(port, "GET", "/api/runs/..%2f..%2fetc%2fpasswd", token=session.token)[0] == 404
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_server_runs.py -q
```
Expected: 404s where 200s are wanted.

- [ ] **Step 3: Add the routes**

In `do_GET`, inside the `try`, next to `/api/events`:

```python
            if path == "/api/runs":
                return self._json({"runs": store.list_runs()})
            if path.startswith("/api/runs/"):
                try:
                    return self._json({"run": store.load(unquote(path.split("/")[3]))})
                except KeyError:
                    return self._json({"error": "not_found"}, 404)
```

In `do_POST`, inside the `try`, after `/api/clear`:

```python
            if path == "/api/runs":
                return self._json({"run": store.save(body.get("run") or {}, body.get("name"))})
            if path.startswith("/api/runs/") and path.endswith("/rename"):
                try:
                    return self._json({"run": store.rename(unquote(path.split("/")[3]),
                                                           body.get("name") or "")})
                except KeyError:
                    return self._json({"error": "not_found"}, 404)
```

Add `do_DELETE` to `Handler`:

```python
    def do_DELETE(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/runs/"):
            return self._json({"error": "not_found"}, 404)
        if not self._allowed():
            return
        try:
            store.delete(unquote(path.split("/")[3]))
            return self._json({"deleted": True})
        except KeyError:
            self._json({"error": "not_found"}, 404)
```

And extend the import at the top of `server.py`:

```python
from urllib.parse import parse_qs, unquote, urlparse
```

- [ ] **Step 4: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: save, reopen, rename and delete runs from the page"
```

---

## Task 12: The page — shell, connect screen, status, and the `?` system

**Files:**
- Replace: `src/cpe_band_scan/web/index.html`, `src/cpe_band_scan/web/app.js`, `src/cpe_band_scan/web/style.css`
- Create: `tools/demo_server.py` (a fake-router server so the page can be clicked without hardware; not shipped in the package)
- Test: manual, plus the parity test in Task 15

**Interfaces:**
- Consumes: `window.CPE_BAND_SCAN = {token, copy, defaults}` injected by Task 9, and the endpoints from Tasks 9-11.
- Produces the JS functions later tasks call: `api(method, path, body)`, `el(tag, attrs, ...children)`, `help(group, key)`, `labelFor(group, key)`, `showError(code, message)`, `render()`, `renderConnect()`, `renderMain()`, `statusCard()`, and the module-level `state` object.
- `state = {device, status, runs, run, viewing, suggestedName, events, since, running, kind, busy, error}`.

**The `?` contract:** every `?` button is built by `help("GROUP", "key")` and takes its words from `copy` — never from a string in the JS. Task 15 enforces that every key used exists, and that every field, action and column key is used somewhere.

- [ ] **Step 1: Write `src/cpe_band_scan/web/index.html`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CPE Band Scan</title>
<link rel="stylesheet" href="/style.css">
<script>/*BOOTSTRAP*/</script>
</head>
<body>
<main id="app">
  <header id="top"></header>
  <div id="banner" role="status" hidden></div>
  <section id="view"></section>
</main>
<div id="popover" role="dialog" hidden></div>
<script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `src/cpe_band_scan/web/style.css`**

```css
:root {
  color-scheme: light dark;
  --bg: #ffffff; --fg: #16181d; --muted: #5d6470; --line: #e3e6ea;
  --accent: #1f6feb; --good: #1a7f37; --warn: #9a6700; --bad: #b42318; --card: #f7f8fa;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #16181d; --fg: #e9ecf1; --muted: #9aa3b0; --line: #2a2f38;
          --accent: #6ea8fe; --good: #4ac26b; --warn: #d4a72c; --bad: #ff7b72; --card: #1d2128; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); line-height: 1.5; }
#app { max-width: 60rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
h1 { font-size: 1.35rem; margin: 0; }
h2 { font-size: 1.05rem; margin: 2rem 0 .5rem; }
p.lede { color: var(--muted); margin: .25rem 0 1.5rem; max-width: 46rem; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: .6rem; padding: 1rem; }
.row { display: flex; gap: .75rem; align-items: center; flex-wrap: wrap; }
label { display: block; font-weight: 600; margin-bottom: .25rem; }
input[type=text], input[type=password] {
  width: 100%; padding: .55rem .7rem; border: 1px solid var(--line); border-radius: .4rem;
  background: var(--bg); color: var(--fg); font-size: 1rem; }
.field { margin-bottom: 1rem; max-width: 26rem; }
button { font: inherit; padding: .5rem .9rem; border-radius: .4rem; border: 1px solid var(--line);
         background: var(--bg); color: var(--fg); cursor: pointer; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.quiet { border: none; background: none; color: var(--accent); padding: .25rem .4rem; }
button:disabled { opacity: .5; cursor: not-allowed; }
button.help { border-radius: 50%; width: 1.35rem; height: 1.35rem; padding: 0; line-height: 1;
              font-size: .8rem; color: var(--muted); margin-left: .35rem; }
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: .45rem .5rem; border-bottom: 1px solid var(--line); }
th { font-size: .85rem; color: var(--muted); font-weight: 600; white-space: nowrap; }
tr.best td { background: color-mix(in srgb, var(--accent) 8%, transparent); }
.grade-excellent { color: var(--good); font-weight: 600; }
.grade-good { color: var(--good); }
.grade-fair { color: var(--warn); }
.grade-poor, .grade-no5g { color: var(--bad); }
.badge { font-size: .75rem; border: 1px solid var(--line); border-radius: 1rem; padding: .05rem .5rem;
         color: var(--muted); }
#banner { padding: .75rem 1rem; border-radius: .5rem; margin-bottom: 1rem;
          border: 1px solid var(--line); background: var(--card); }
#banner.bad { border-color: var(--bad); color: var(--bad); }
#popover { position: absolute; max-width: 22rem; background: var(--bg); color: var(--fg);
           border: 1px solid var(--line); border-radius: .5rem; padding: .75rem .9rem;
           box-shadow: 0 8px 24px rgba(0,0,0,.18); font-size: .9rem; z-index: 10; }
.note { color: var(--muted); font-size: .9rem; margin: .5rem 0; }
.log { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .85rem;
       max-height: 12rem; overflow: auto; border: 1px solid var(--line); border-radius: .4rem;
       padding: .5rem; background: var(--card); }
progress { width: 100%; height: .5rem; }
```

- [ ] **Step 3: Write `src/cpe_band_scan/web/app.js`**

```js
"use strict";
const { token, copy, defaults } = window.CPE_BAND_SCAN;

const state = {
  device: null, status: null, runs: [], run: null, viewing: null, suggestedName: "",
  events: [], since: 0, running: false, kind: "", busy: false, error: null,
};

// ---- plumbing --------------------------------------------------------------
async function api(method, path, body) {
  const response = await fetch(path, {
    method,
    headers: { "X-CPE-Band-Scan-Token": token, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const failure = new Error(payload.message || payload.error || "");
    failure.code = payload.error;
    throw failure;
  }
  return payload;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "onclick") node.addEventListener("click", value);
    else if (key === "class") node.className = value;
    else if (value !== null && value !== false) node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function labelFor(group, key) {
  const entry = copy[group][key];
  return typeof entry === "string" ? entry : entry.label;
}

// ---- the ? system ----------------------------------------------------------
const popover = document.getElementById("popover");

function showHelp(text, anchor) {
  popover.textContent = text;
  popover.hidden = false;
  const box = anchor.getBoundingClientRect();
  popover.style.top = `${window.scrollY + box.bottom + 6}px`;
  popover.style.left = `${Math.min(window.scrollX + box.left, window.innerWidth - 360)}px`;
}

document.addEventListener("click", (event) => {
  if (!event.target.closest("#popover") && !event.target.closest(".help")) popover.hidden = true;
});
document.addEventListener("keydown", (event) => { if (event.key === "Escape") popover.hidden = true; });

function help(group, key) {
  const entry = copy[group][key];
  const button = el("button", {
    class: "help", type: "button",
    "aria-label": `What is ${labelFor(group, key) || key}?`,
    "data-help": `${group}.${key}`,
  }, "?");
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    showHelp(entry.help, button);
  });
  return button;
}

function field(key, type = "text", value = "") {
  const entry = copy.FIELDS[key];
  const input = el("input", { type, id: key, value, placeholder: entry.placeholder || "" });
  return el("div", { class: "field" },
    el("label", { for: key }, entry.label, help("FIELDS", key)), input);
}

function action(key, handler, extra = {}) {
  const button = el("button", Object.assign({ onclick: handler }, extra), copy.ACTIONS[key].label);
  return el("span", { class: "row" }, button, help("ACTIONS", key));
}

function showError(message) {
  const banner = document.getElementById("banner");
  banner.textContent = message || "";
  banner.className = message ? "bad" : "";
  banner.hidden = !message;
}

// ---- views -----------------------------------------------------------------
function renderConnect() {
  const view = document.getElementById("view");
  view.replaceChildren(
    el("p", { class: "lede" }, copy.APP.connect_intro),
    el("div", { class: "card" },
      el("h2", {}, copy.APP.connect_heading),
      field("router_url", "text", defaults.url),
      field("password", "password"),
      action("connect", onConnect, { class: "primary" }),
      el("p", { class: "note" }, copy.NOTES.password_note)),
    el("p", { class: "note" }, copy.NOTES.vpn));
  document.getElementById("password").addEventListener("keydown", (event) => {
    if (event.key === "Enter") onConnect();
  });
}

async function onConnect() {
  showError(null);
  state.busy = true;
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
    render();
  }
}

async function refreshStatus() {
  try {
    state.status = await api("GET", "/api/status");
    state.running = state.status.running;
  } catch (failure) {
    showError(failure.message);
  }
}

function signalLine(signal) {
  return `${signal.band || "-"} · SINR ${signal.sinr} dB · RSRQ ${signal.rsrq} dB · RSRP ${signal.rsrp} dBm`;
}

function lockLine(lock) {
  const [anchors, secondaries] = lock.lte;
  if (!anchors.length) return labelFor("ACTIONS", "clear");
  return `B${anchors.join(", B")}${secondaries.length ? ` (+B${secondaries.join(", B")})` : ""}`;
}

function statusCard() {
  const status = state.status;
  if (!status) return el("div");
  return el("div", { class: "card" },
    el("h2", {}, copy.APP.status_heading),
    el("p", {}, signalLine(status.signal)),
    el("p", { class: "note" }, lockLine(status.lock)),
    el("div", { class: "row" },
      action("refresh", async () => { await refreshStatus(); render(); }),
      action("clear", onClear)));
}

function deviceLine() {
  const device = state.device;
  return el("p", { class: "note" },
    [device.model, `firmware ${device.firmware}`, device.carrier].filter(Boolean).join(" · "));
}

async function onClear() {
  try {
    await api("POST", "/api/clear", {});
    await refreshStatus();
  } catch (failure) {
    showError(failure.message);
  }
  render();
}

function renderMain() {
  const view = document.getElementById("view");
  view.replaceChildren(deviceLine(), statusCard());
}

function render() {
  const top = document.getElementById("top");
  top.replaceChildren(el("h1", {}, copy.APP.name), el("p", { class: "lede" }, copy.APP.tagline));
  if (!state.device) renderConnect(); else renderMain();
}

async function resume() {
  // A scan runs for half an hour with the connection dropping at every band change, so a
  // reload is likely. The router session lives in the server, and /api/events replays from
  // any index, so the page can pick a running job back up instead of losing it.
  const status = await api("GET", "/api/status").catch(() => null);
  if (!status) return render();              // not connected yet: the connect screen is right
  state.device = status.device;
  state.status = status;
  await refreshRuns();
  const answer = await api("GET", "/api/events?since=0").catch(() => null);
  if (answer) {
    state.since = answer.since;
    state.events = answer.events;
    state.running = answer.running;
    state.kind = answer.kind;
    for (const event of answer.events) {
      if (event.type === "done" || event.type === "trace_done") state.run = event.run;
    }
  }
  render();
  if (state.running) poll();
}

resume();
```

- [ ] **Step 4: Write `tools/demo_server.py` so the page can be exercised without a router**

```python
"""Run the page against a fake router: python tools/demo_server.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cpe_band_scan import scanner, server                      # noqa: E402
from tests.test_server import fake_router_factory         # noqa: E402

scanner.SETTLE = 1                                        # no 35-second waits in the demo
session = server.Session(router_factory=fake_router_factory())
session.connect("192.168.8.1", "demo")
server.serve(port=8766, session=session)
```

- [ ] **Step 5: Look at it**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/python tools/demo_server.py
```
Check by hand, then stop it with Ctrl-C:
- the connect screen shows both fields with a `?` beside each, and the VPN note;
- clicking a `?` opens the popover, clicking elsewhere or pressing Escape closes it;
- a wrong password shows the sentence from `copy.ERRORS`, not a code;
- after connecting, the status card shows the signal line and the current lock.

- [ ] **Step 6: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: connect screen, status card and the ? help system"
```

---

## Task 13: The page — scanning, progress, ranked results, apply

**Files:**
- Modify: `src/cpe_band_scan/web/app.js`
- Test: manual against `tools/demo_server.py`, plus Task 15

**Interfaces:**
- Consumes: `POST /api/scan`, `GET /api/events`, `POST /api/cancel`, `POST /api/apply`.
- Produces: `scanControls()`, `progressCard()`, `resultsTable(run)`, `onScan(sides)`, `onApply(side, record, name)`, `poll()`, `describe(event)`.

**What the user sees while it runs:** a progress bar, "Measuring B7, 6 of 18. About 12 minutes left.", and a rolling log of finished bands with their grades. The page polls every 2 seconds, so a reload never loses the run. That directly answers the "don't let it look stuck" requirement.

- [ ] **Step 1: Add the scan controls and the progress card to `app.js`**

Insert before `renderMain`:

```js
const SIDES = { all: ["lte", "nr"], "4g": ["lte"], "5g": ["nr"] };

function scanControls() {
  const disabled = state.running || state.busy;
  return el("div", { class: "card" },
    el("h2", {}, copy.APP.results_heading),
    el("p", { class: "note" }, copy.NOTES.before_scan),
    el("p", { class: "note" }, copy.NOTES.vpn),
    el("div", { class: "row" },
      action("scan_all", () => onScan(SIDES.all), { class: "primary", disabled }),
      action("scan_4g", () => onScan(SIDES["4g"]), { disabled }),
      action("scan_5g", () => onScan(SIDES["5g"]), { disabled })));
}

function describe(event) {
  const words = copy.PROGRESS;
  const fill = (template, fields) =>
    template.replace(/\{(\w+)\}/g, (_, key) => (fields[key] === undefined ? "" : fields[key]));
  switch (event.type) {
    case "set_start":
      return fill(words.set_start, { name: event.name, index: event.index, total: event.total,
                                     minutes: Math.max(1, Math.round(event.eta_s / 60)) });
    case "set_result":
      return fill(words.set_result, { name: event.name,
                                      grade: copy.GRADES[event.result.grade],
                                      floor: event.result.floor });
    case "set_skipped":
      return fill(words[event.reason] || words.refused, { name: event.name });
    case "side_done":
      return fill(words.side_done, { side: copy.SIDES[event.side],
                                     count: Object.keys(event.results).length });
    case "applied":
      return fill(words.applied, { bands: (event.plan.lte.concat(event.plan.nr)).join(", ") });
    case "cancelled": return words.cancelled;
    case "trace_start": return fill(words.trace_start, { minutes: Math.round(event.seconds / 60) });
    case "trace_sample":
      return `${event.at_s}s  ${event.sample.band}  SINR ${event.sample.sinr}`;
    case "trace_done": return words.trace_done;
    case "done": return words.done;
    case "error": return event.message || copy.ERRORS[event.code] || "";
    default: return null;
  }
}

function progressCard() {
  const lines = state.events.map(describe).filter(Boolean);
  const last = state.events.filter((event) => event.type === "set_start").slice(-1)[0];
  return el("div", { class: "card" },
    el("p", {}, lines[lines.length - 1] || copy.PROGRESS.run_start),
    last ? el("progress", { value: last.index, max: last.total }) : el("div"),
    el("div", { class: "log" }, lines.slice(-40).reverse().map((line) => el("div", {}, line))),
    el("div", { class: "row" }, action("cancel", onCancel, { disabled: !state.running })));
}

async function onScan(sides) {
  showError(null);
  state.events = [];
  state.since = 0;
  state.run = null;
  try {
    await api("POST", "/api/scan", { sides });
    state.running = true;
    render();
    poll();
  } catch (failure) {
    showError(failure.message);
    render();
  }
}

async function onCancel() {
  try { await api("POST", "/api/cancel", {}); } catch (failure) { showError(failure.message); }
}

async function poll() {
  const answer = await api("GET", `/api/events?since=${state.since}`).catch(() => null);
  if (answer) {
    state.since = answer.since;
    state.events = state.events.concat(answer.events);
    state.running = answer.running;
    state.kind = answer.kind;
    for (const event of answer.events) {
      if (event.type === "done" || event.type === "trace_done") state.run = event.run;
      if (event.type === "error") showError(describe(event));
    }
    render();
  }
  if (state.running) setTimeout(poll, 2000);
  else { await refreshStatus(); render(); }
}
```

- [ ] **Step 2: Add the results table**

```js
const COLUMN_KEYS = ["rank", "band", "grade", "five_g", "floor", "sinr", "rsrq", "rsrp",
                     "nr_sinr", "carriers"];

function resultsTable(run) {
  if (!run || !run.sides) return el("p", { class: "note" }, copy.NOTES.empty_results);
  const blocks = [];
  for (const [side, record] of Object.entries(run.sides)) {
    const ranked = record.order.concat(
      Object.keys(record.results).filter((name) => !record.order.includes(name)));
    const head = el("tr", {},
      COLUMN_KEYS.map((key) => el("th", {}, copy.COLUMNS[key].label, help("COLUMNS", key))),
      el("th", {}, help("ACTIONS", "apply")));       // the apply button explains itself here
    const rows = ranked.map((name, index) => {
      const row = record.results[name];
      const isBest = index === 0 && record.order.includes(name);
      return el("tr", { class: isBest ? "best" : "" },
        el("td", {}, record.order.includes(name) ? index + 1 : "-"),
        el("td", {}, name, isBest ? el("span", { class: "badge" }, copy.GRADES[row.grade]) : null),
        el("td", { class: `grade-${row.grade}` }, copy.GRADES[row.grade]),
        el("td", {}, row.has5g ? "yes" : "no"),
        el("td", {}, `${row.floor}`),
        el("td", {}, `${row.sinr}`),
        el("td", {}, `${row.rsrq}`),
        el("td", {}, `${row.rsrp}`),
        el("td", {}, `${row.nrsinr}`),
        el("td", {}, row.band),
        el("td", {}, el("button", {
          class: isBest ? "primary" : "",
          disabled: state.running || name === "auto",
          onclick: () => onApply(side, record, name),
        }, copy.ACTIONS.apply.label)));
    });
    blocks.push(el("div", {},
      el("h2", {}, copy.SIDES[side]),
      el("table", {}, el("thead", {}, head), el("tbody", {}, rows)),
      Object.keys(record.skipped).length
        ? el("p", { class: "note" }, `${Object.keys(record.skipped).join(", ")}: `
            + copy.PROGRESS.no_service.replace("{name}", "").trim())
        : null,
      el("p", { class: "note" }, copy.NOTES.auto_row)));
  }
  return el("div", {}, blocks);
}

async function onApply(side, record, name) {
  showError(null);
  const chosen = record.sets[name];
  const others = record.order.filter((other) => other !== name)
    .flatMap((other) => record.sets[other]);
  const payload = side === "nr" ? { nr: chosen } : { lte: chosen, scell: others };
  try {
    await api("POST", "/api/apply", payload);
    await refreshStatus();
  } catch (failure) {
    showError(failure.message);
  }
  render();
}
```

- [ ] **Step 3: Wire them into `renderMain`**

```js
function renderMain() {
  const view = document.getElementById("view");
  view.replaceChildren(
    deviceLine(),
    statusCard(),
    state.running || state.events.length ? progressCard() : scanControls(),
    resultsTable(state.viewing || state.run),
    el("p", { class: "note" }, copy.NOTES.lock_survives),
    el("p", { class: "note" }, copy.NOTES.rescan_hint));
}
```

- [ ] **Step 4: Look at it**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/python tools/demo_server.py
```
Start a scan in the demo and check:
- the progress line names the band, its position and the minutes left, and updates every couple of seconds;
- the log grows with one line per finished band, including its grade;
- reloading the page mid-scan keeps the progress going;
- the finished table is sorted best first, the top row is highlighted and its button is the primary one;
- every column header has a `?` that explains the number;
- `auto` appears as a comparison row and cannot be applied.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: scan progress and a ranked, applyable results table"
```

---

## Task 14: The page — the 2-minute test, saving, and the saved-results browser

**Files:**
- Modify: `src/cpe_band_scan/web/app.js`
- Test: manual against `tools/demo_server.py`, plus Task 15

**Interfaces:**
- Consumes: `POST /api/test`, `POST /api/runs`, `GET /api/runs`, `GET /api/runs/<id>`, `POST /api/runs/<id>/rename`, `DELETE /api/runs/<id>`.
- Produces: `testCard()`, `saveCard()`, `savedRuns()`, `onTest()`, `onSave()`, `onOpenRun(id)`, `onRenameRun(id)`, `onDeleteRun(id)`, `refreshRuns()`, `traceSummary(run)`.

- [ ] **Step 1: Add the test, save and saved-runs pieces to `app.js`**

Insert before `renderMain`:

```js
function testCard() {
  return el("div", { class: "card" },
    el("h2", {}, copy.APP.test_heading),
    el("p", { class: "note" }, copy.ACTIONS.test.help),
    el("div", { class: "row" },
      action("test", onTest, { disabled: state.running || state.busy })),
    state.run && state.run.kind === "test" ? traceSummary(state.run) : null);
}

function traceSummary(run) {
  const keys = ["floor", "sinr", "rsrq", "rsrp", "five_g", "carriers"];
  const summary = run.summary;
  const value = {
    floor: summary.floor, sinr: summary.sinr, rsrq: summary.rsrq, rsrp: summary.rsrp,
    five_g: summary.has5g ? "yes" : "no", carriers: summary.band,
  };
  return el("table", {},
    el("tbody", {}, keys.map((key) => el("tr", {},
      el("th", {}, copy.COLUMNS[key].label, help("COLUMNS", key)),
      el("td", {}, `${value[key]}`)))));
}

async function onTest() {
  showError(null);
  state.events = []; state.since = 0; state.run = null;
  try {
    await api("POST", "/api/test", {});
    state.running = true;
    render();
    poll();
  } catch (failure) {
    showError(failure.message);
    render();
  }
}

function saveCard() {
  if (!state.run) return null;
  const input = el("input", { type: "text", id: "run_name",
                              value: state.suggestedName || "",
                              placeholder: copy.FIELDS.run_name.placeholder });
  return el("div", { class: "card" },
    el("label", { for: "run_name" }, copy.FIELDS.run_name.label, help("FIELDS", "run_name")),
    input,
    el("div", { class: "row" }, action("save", onSave, { class: "primary" })));
}

async function onSave() {
  const name = document.getElementById("run_name").value;
  try {
    const answer = await api("POST", "/api/runs", { run: state.run, name });
    state.run = answer.run;
    await refreshRuns();
    showError(null);
  } catch (failure) {
    showError(failure.message);
  }
  render();
}

async function refreshRuns() {
  try { state.runs = (await api("GET", "/api/runs")).runs; } catch { state.runs = []; }
}

function savedRuns() {
  if (!state.runs.length) return el("p", { class: "note" }, copy.NOTES.empty_runs);
  const head = el("tr", {}, el("th", {}, copy.FIELDS.run_name.label), el("th", {}), el("th", {}),
    el("th", {}, help("ACTIONS", "open_run"), help("ACTIONS", "rename_run"),
                 help("ACTIONS", "delete_run")));
  return el("table", {}, el("thead", {}, head),
    el("tbody", {}, state.runs.map((row) => el("tr", {},
      el("td", {}, row.name),
      el("td", { class: "note" }, `${copy.SIDES[row.kind === "test" ? "trace" : "lte"]} · ${row.saved}`),
      el("td", {}, row.best || "-"),
      el("td", {},
        el("button", { class: "quiet", onclick: () => onOpenRun(row.id) }, copy.ACTIONS.open_run.label),
        el("button", { class: "quiet", onclick: () => onRenameRun(row) }, copy.ACTIONS.rename_run.label),
        el("button", { class: "quiet", onclick: () => onDeleteRun(row) },
           copy.ACTIONS.delete_run.label))))));
}

async function onOpenRun(id) {
  try {
    state.viewing = (await api("GET", `/api/runs/${id}`)).run;
  } catch (failure) {
    showError(failure.message);
  }
  render();
}

async function onRenameRun(row) {
  const name = window.prompt(copy.FIELDS.run_name.help, row.name);
  if (name === null) return;
  try {
    await api("POST", `/api/runs/${row.id}/rename`, { name });
    await refreshRuns();
  } catch (failure) {
    showError(failure.message);
  }
  render();
}

async function onDeleteRun(row) {
  if (!window.confirm(`${copy.ACTIONS.delete_run.label} — ${row.name}?`)) return;
  try {
    await api("DELETE", `/api/runs/${row.id}`);
    if (state.viewing && state.viewing.id === row.id) state.viewing = null;
    await refreshRuns();
  } catch (failure) {
    showError(failure.message);
  }
  render();
}
```

- [ ] **Step 2: Extend `renderMain` to show them**

```js
function renderMain() {
  const view = document.getElementById("view");
  const shown = state.viewing || state.run;
  view.replaceChildren(
    deviceLine(),
    statusCard(),
    state.running || state.events.length ? progressCard() : scanControls(),
    shown && shown.kind === "test" ? el("div") : resultsTable(shown),
    testCard(),
    saveCard(),
    el("h2", {}, copy.APP.saved_heading),
    savedRuns(),
    el("p", { class: "note" }, copy.NOTES.lock_survives),
    el("p", { class: "note" }, copy.NOTES.rescan_hint));
}
```

- [ ] **Step 3: Look at it**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && CPE_BAND_SCAN_HOME=/tmp/cpe-band-scan-demo .venv/bin/python tools/demo_server.py
```
Check:
- the test runs for its full length, shows a line per sample, and ends with the floor/typical/peak table;
- the save box is pre-filled with the carrier and today's date, and saving adds a row to the list;
- opening a saved run shows its full table, renaming keeps the results, deleting asks first;
- every action button has a `?` next to it.

- [ ] **Step 4: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: 2-minute test, named saves and the saved-results browser"
```

---

## Task 15: Remember the router address between runs

**Files:**
- Modify: `src/cpe_band_scan/store.py`, `src/cpe_band_scan/server.py`
- Test: `tests/test_settings.py`

**Interfaces:**
- Produces: `store.settings() -> dict`, `store.save_settings(**values) -> dict`, stored at `~/.cpe-band-scan/settings.json`.
- The page's address field is pre-filled from the remembered address, falling back to `http://192.168.8.1/`.

**Why:** `192.168.8.1` is right for most Huawei CPE routers but not for all of them — this one lives at `192.168.1.1`. Typing it on every launch is a papercut, and the address is not a secret. The password is never part of this file.

- [ ] **Step 1: Write the failing tests**

`tests/test_settings.py`:

```python
import pytest

from cpe_band_scan import store


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CPE_BAND_SCAN_HOME", str(tmp_path))
    return tmp_path


def test_settings_start_empty_without_a_file():
    assert store.settings() == {}


def test_a_saved_address_comes_back():
    store.save_settings(router_url="http://192.168.1.1/")
    assert store.settings()["router_url"] == "http://192.168.1.1/"


def test_saving_merges_rather_than_replaces():
    store.save_settings(router_url="http://192.168.1.1/")
    store.save_settings(username="root")
    assert store.settings() == {"router_url": "http://192.168.1.1/", "username": "root"}


def test_a_password_is_never_written_even_if_passed(home):
    store.save_settings(router_url="http://192.168.1.1/", password="secret")
    assert "secret" not in (home / "settings.json").read_text(encoding="utf-8")


def test_a_corrupt_settings_file_is_ignored(home):
    (home / "settings.json").write_text("{not json", encoding="utf-8")
    assert store.settings() == {}
```

- [ ] **Step 2: Run them and watch them fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_settings.py -q
```
Expected: `AttributeError: module 'cpe_band_scan.store' has no attribute 'settings'`.

- [ ] **Step 3: Add settings to `src/cpe_band_scan/store.py`**

```python
SETTINGS_KEYS = ("router_url", "username")          # a password is never one of these


def settings_path():
    home().mkdir(parents=True, exist_ok=True)
    return home() / "settings.json"


def settings() -> dict:
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(**values) -> dict:
    kept = dict(settings())
    kept.update({key: value for key, value in values.items() if key in SETTINGS_KEYS and value})
    settings_path().write_text(json.dumps(kept, indent=2), encoding="utf-8")
    return kept
```

- [ ] **Step 4: Remember the address on a successful connect**

In `server.py`, in the `/api/connect` branch, right after `device = self.session.connect(...)`:

```python
                store.save_settings(router_url=self.session.router.url,
                                    username=body.get("username") or "admin")
```

In `Handler._page`, serve the remembered address as the field's default:

```python
        bootstrap = json.dumps({"token": self.session.token, "copy": copy.bundle(),
                                "defaults": {"url": store.settings().get("router_url", DEFAULT_URL)}})
```

- [ ] **Step 5: Run the tests and watch them pass**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "feat: remember the router address, never the password"
```

---

## Task 16: Parity tests and one end-to-end run

**Files:**
- Create: `tests/test_parity.py`, `tests/test_end_to_end.py`

**Interfaces:** consumes everything. Produces no production code.

**Why this task exists:** the `?` texts live in Python and are used in JavaScript. Nothing but a test keeps the two sides honest, and a `?` with no words behind it is exactly the kind of gap nobody notices until a user clicks it. The end-to-end test proves the whole chain — connect, scan, rank, apply, save, reopen — works through the real HTTP surface against a fake router.

- [ ] **Step 1: Write the parity tests**

`tests/test_parity.py`:

```python
"""The page and the copy catalogue must agree."""
import re
from pathlib import Path

import pytest

from cpe_band_scan import copy

WEB = Path(__file__).resolve().parents[1] / "src" / "cpe_band_scan" / "web"
APP_JS = (WEB / "app.js").read_text(encoding="utf-8")
INDEX = (WEB / "index.html").read_text(encoding="utf-8")

USED_HELP = set(re.findall(r'help\(\s*"(\w+)"\s*,\s*"(\w+)"\s*\)', APP_JS))
USED_COPY = set(re.findall(r'copy\.(\w+)\.(\w+)', APP_JS))


def test_every_help_key_used_by_the_page_exists():
    for group, key in USED_HELP:
        assert key in getattr(copy, group), f'help("{group}", "{key}") has no entry'


def test_every_copy_key_used_by_the_page_exists():
    for group, key in USED_COPY:
        catalogue = getattr(copy, group, None)
        assert catalogue is not None, f"copy.{group} does not exist"
        assert key in catalogue, f"copy.{group}.{key} does not exist"


@pytest.mark.parametrize("group", ["FIELDS", "ACTIONS", "COLUMNS"])
def test_every_entry_is_actually_rendered_by_the_page(group):
    """field(), action() and the column loop each build their ? from the key they are given,
    so the key itself is what has to appear in the page code."""
    missing = [key for key in getattr(copy, group)
               if f'"{key}"' not in APP_JS and f"copy.{group}.{key}" not in APP_JS]
    assert not missing, f"{group} entries the page never renders: {missing}"


@pytest.mark.parametrize("group", ["FIELDS", "ACTIONS", "COLUMNS"])
def test_each_group_gets_its_question_marks_from_the_catalogue(group):
    assert f'help("{group}"' in APP_JS


def test_the_page_never_hardcodes_words_the_catalogue_owns():
    for entry in list(copy.ACTIONS.values()) + list(copy.FIELDS.values()):
        assert entry["label"] not in INDEX, f"{entry['label']} is hardcoded in index.html"


def test_the_bootstrap_placeholder_is_still_there():
    assert "/*BOOTSTRAP*/" in INDEX, "the server injects the token and copy at this marker"
```

- [ ] **Step 2: Run them and fix what they find**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_parity.py -q
```
If a field, action or column has no `?` on the page, add the `?` rather than deleting the entry. If an entry genuinely has no place in the page (a CLI-only string), move it out of `FIELDS`/`ACTIONS`/`COLUMNS` into `PROGRESS` or `NOTES`.

- [ ] **Step 3: Write the end-to-end test**

`tests/test_end_to_end.py`:

```python
"""Connect, scan, rank, apply, save, reopen — through real HTTP, against a fake router."""
import time

import pytest

from cpe_band_scan import server
from tests.test_server import call, fake_router_factory, live  # noqa: F401


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CPE_BAND_SCAN_HOME", str(tmp_path))
    monkeypatch.setattr(server.scanner, "SETTLE", 0)


def test_the_whole_journey(live):
    session, port = live

    status, connected = call(port, "POST", "/api/connect",
                             {"url": "192.168.8.1", "password": "pw"}, token=session.token)
    assert status == 200 and connected["device"]["driver"] == "lockfreq"

    assert call(port, "POST", "/api/scan", {"sides": ["lte"], "bands": ["1", "7"]},
                token=session.token)[0] == 200

    since, run = 0, None
    deadline = time.time() + 10
    while time.time() < deadline and run is None:
        _, body = call(port, "GET", f"/api/events?since={since}", token=session.token)
        since = body["since"]
        for event in body["events"]:
            if event["type"] == "done":
                run = event["run"]
        time.sleep(0.05)
    assert run, "the scan never produced a run document"

    order = run["sides"]["lte"]["order"]
    assert order, "the scan produced no ranking"
    assert run["applied"]["lte"], "the winner was not applied"

    _, saved = call(port, "POST", "/api/runs", {"run": run, "name": "End to end"},
                    token=session.token)
    _, listed = call(port, "GET", "/api/runs", token=session.token)
    assert listed["runs"][0]["name"] == "End to end"

    _, reopened = call(port, "GET", f"/api/runs/{saved['run']['id']}", token=session.token)
    assert reopened["run"]["sides"]["lte"]["order"] == order

    assert call(port, "POST", "/api/apply", {"lte": ["7"], "scell": ["3"]},
                token=session.token)[0] == 200
    assert call(port, "POST", "/api/clear", {}, token=session.token)[0] == 200
```

- [ ] **Step 4: Run the whole suite**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q
```
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A && git commit -m "test: page and copy stay in step, and one full journey"
```

---

## Task 17: Install path, launchers, and the README

**Files:**
- Create: `README.md`, `run-cpe-band-scan.command`, `run-cpe-band-scan.bat`
- Modify: `pyproject.toml`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Write the failing test**

`tests/test_packaging.py`:

```python
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_both_entry_points_reach_the_cli():
    scripts = PROJECT["project"]["scripts"]
    assert scripts["cpe-band-scan"] == "cpe_band_scan.cli:main"
    assert scripts["cpescan"] == "cpe_band_scan.cli:main", "the short alias saves ten keystrokes"


def test_the_web_assets_ship_with_the_package():
    assert "web/*" in PROJECT["tool"]["setuptools"]["package-data"]["cpe_band_scan"]


def test_only_one_runtime_dependency():
    assert PROJECT["project"]["dependencies"] == ["huawei-lte-api>=1.7"]


def test_the_readme_tells_someone_how_to_start_without_an_llm():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for needed in ("pipx install", "cpe-band-scan ui", "192.168.8.1", "192.168.1.1"):
        assert needed in readme
```

- [ ] **Step 2: Run it and watch it fail**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest tests/test_packaging.py -q
```
Expected: `KeyError: 'cpescan'`.

- [ ] **Step 3: Add the short alias**

In `pyproject.toml`:

```toml
[project.scripts]
cpe-band-scan = "cpe_band_scan.cli:main"
cpescan = "cpe_band_scan.cli:main"
```

- [ ] **Step 4: Write `README.md`**

````markdown
# CPE Band Scan

Find the mobile band that gives you the steadiest connection, and lock your Huawei router to it.

CPE Band Scan talks to the router's own web interface over your local network. Nothing is flashed, and
one click puts the router back on automatic.

## Install

```bash
pipx install cpe-band-scan
```

No pipx? `python3 -m pip install --user cpe-band-scan` works too.

## Use it

```bash
cpe-band-scan ui
```

Your browser opens on the app. Enter:

- **Router address** — `192.168.8.1` for most Huawei routers. Some use `192.168.1.1`. CPE Band Scan
  remembers whichever one works.
- **Admin password** — the password for the router's admin page, not the Wi-Fi password.

Then press **Scan all bands** and leave it running. It measures each band for about a minute and
ranks them, then locks the best one. Expect 20 to 30 minutes, and a drop of about half a minute
each time a band changes.

When two bands score close, **Test for 2 minutes** watches the one you're on without changing
anything, so you can compare their worst moments rather than their best.

Save a run under a name and it stays on this computer, ready to compare with the next place or the
next provider.

### Using a VPN

Keep it on. CPE Band Scan reads the numbers from the router itself, so a VPN doesn't change them. Stay
on one server for the whole scan, and if CPE Band Scan can't reach the router while the VPN is up,
switch on your VPN's local network access setting.

## From the terminal instead

```bash
cpe-band-scan status              # what you're connected to right now
cpe-band-scan scan                # every band, both 4G and 5G
cpe-band-scan scan 4g             # 4G only
cpe-band-scan test                # watch the current band for 2 minutes
cpe-band-scan apply 7 --scell 3   # lock to B7, keep B3 as a secondary carrier
cpe-band-scan clear               # back to automatic
cpe-band-scan runs                # saved results
```

The password comes from `CPE_BAND_SCAN_PASSWORD`, a `PASSWORD=` line in a `.env` file in the current
folder, or a prompt. The router address comes from `--url`.

## Which routers work

Huawei CPE routers on firmware 4 (H155-381, H155-181, H153, H158 and relatives). CPE Band Scan checks
the firmware before it writes anything and tells you if it can't help. Older firmware uses a
different interface, which CPE Band Scan doesn't speak yet.

## What it stores

Saved runs and the router address live in `~/.cpe-band-scan`. The password never leaves memory.
````

- [ ] **Step 5: Write the double-click launchers**

`run-cpe-band-scan.command` (macOS, then `chmod +x run-cpe-band-scan.command`):

```bash
#!/bin/sh
cd "$(dirname "$0")" || exit 1
python3 -m cpe_band_scan ui
```

`run-cpe-band-scan.bat` (Windows):

```bat
@echo off
cd /d "%~dp0"
python -m cpe_band_scan ui
pause
```

- [ ] **Step 6: Verify a real install works**

```bash
cd /tmp && rm -rf cpe-band-scan-check && python3 -m venv cpe-band-scan-check && cpe-band-scan-check/bin/pip install /Users/esi/Work/Other/cpe-band-scan && cpe-band-scan-check/bin/cpe-band-scan help
```
Expected: the command table prints. Then run `cpe-band-scan-check/bin/cpe-band-scan ui --no-browser`, open the address it prints, and stop it with Ctrl-C.

- [ ] **Step 7: Run the suite, then commit**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/pytest -q && git add -A && git commit -m "feat: install path, launchers and the README"
```

---

## Task 18: Ship the assistant skill inside the app repo

**Files:**
- Create: `skills/bandscan/SKILL.md`, `skills/bandscan/reference.md` (moved from the personal skills repo, rewritten to call the app)
- Modify: `README.md` (a section pointing at the bundled skill)
- Remove: `/Users/esi/Work/Other/skills/skills/bandscan/` and its row in that repo's `README.md`

**Why the skill travels with the app:** anyone who installs CPE Band Scan can then point their
assistant at the same repository and get the judgement layer for free — locating the router,
reading the ranked table, deciding which runner-up deserves a two-minute test. The app stays the
one implementation; the skill keeps only the part a person would otherwise have to think through.
Two copies of the band logic in two repositories would drift the first time either is fixed.

**The skill keeps the short name `bandscan`** so it stays quick to invoke as `/bandscan`. The long
name belongs to the app, which people type once per session at most.

- [ ] **Step 1: Move the skill in, without deleting anything yet**

```bash
mkdir -p /Users/esi/Work/Other/cpe-band-scan/skills/bandscan
cp /Users/esi/Work/Other/skills/skills/bandscan/SKILL.md /Users/esi/Work/Other/skills/skills/bandscan/reference.md /Users/esi/Work/Other/cpe-band-scan/skills/bandscan/
```

The `scripts/` folder is deliberately not copied: the installed app replaces it.

- [ ] **Step 2: Rewrite the setup step in the moved `SKILL.md`**

Step 4 becomes:

```markdown
4. **Setup once:** `pipx install cpe-band-scan` (or `pip install --user cpe-band-scan`). Every
   command below is `cpe-band-scan <command>`, run from the folder that should hold the logs;
   `cpescan` is a shorter alias for the same thing. The app also has a GUI: `cpe-band-scan ui`
   opens a local page with the same scan, the same ranked table and the same two-minute test.
   Offer it whenever the person would rather click than read a table in chat.
```

- [ ] **Step 3: Repoint every invocation in the moved `SKILL.md`**

```bash
cd /Users/esi/Work/Other/cpe-band-scan/skills/bandscan && sed -i '' -E 's#python3? (<skill>/scripts/)?bandscan\.py #cpe-band-scan #g' SKILL.md
```

Then read the file and repair what the substitution left behind:
- Step 5, the firmware probe, is now a single `cpe-band-scan status`, which prints the model,
  firmware and carrier on one line and refuses an unsupported device with the reason in words.
- Step 7, the background scan, keeps its progress discipline but tails the app's own output.
- The commands table's first column becomes `cpe-band-scan scan`, `cpe-band-scan status`, and so on.

- [ ] **Step 4: Point `reference.md` at the implementation**

Under the driver table:

```markdown
The driver itself lives in `src/cpe_band_scan/device.py` in this repository; this table is the
reasoning behind it, not a second implementation. A new firmware family means a new driver module
there and a new row here.
```

- [ ] **Step 5: Check nothing still refers to the deleted scripts**

```bash
cd /Users/esi/Work/Other/cpe-band-scan/skills/bandscan && grep -n "bandscan\.py\|hw\.py\|scripts/" SKILL.md reference.md
```
Expected: no matches.

- [ ] **Step 6: Add a section to the app `README.md`**

````markdown
## Using it with an assistant

This repository also ships a Claude Code skill in `skills/bandscan`. Point your assistant at it and
it will find your router, run the scan, read the table for you and suggest which runner-up is worth
a two-minute test. It drives this same app, so both routes do exactly the same thing.

```bash
ln -s "$PWD/skills/bandscan" ~/.claude/skills/bandscan
```
````

- [ ] **Step 7: Repoint the local symlinks, then remove the old copy**

Repoint first, so the symlinks are never left dangling:

```bash
ln -sfn /Users/esi/Work/Other/cpe-band-scan/skills/bandscan ~/.claude/skills/bandscan
ln -sfn /Users/esi/Work/Other/cpe-band-scan/skills/bandscan ~/.agents/skills/bandscan
ls -l ~/.claude/skills/bandscan ~/.agents/skills/bandscan
```

Confirm the moved copy is complete, then drop the original. It was never committed, so the copy in
this repository is the only version that matters:

```bash
diff -r /Users/esi/Work/Other/skills/skills/bandscan /Users/esi/Work/Other/cpe-band-scan/skills/bandscan
```
Expected: only the absent `scripts/` folder differs. Then:

```bash
rm -rf /Users/esi/Work/Other/skills/skills/bandscan
cd /Users/esi/Work/Other/skills && git checkout -- README.md
```

- [ ] **Step 8: Prove the skill still points at something that exists**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && .venv/bin/cpe-band-scan help && grep -c "cpe-band-scan" skills/bandscan/SKILL.md
```
Expected: the command table prints, and the skill names the app several times.

- [ ] **Step 9: Save the work**

```bash
cd /Users/esi/Work/Other/cpe-band-scan && git add -A
```
Then commit with the message `feat: ship the assistant skill with the app`.

---

## Self-review notes

- **Spec coverage:** R1 Tasks 9/12/15, R2 Task 12, R3 Tasks 2/7/9, R4 Tasks 4/5/13, R5 Tasks 4/13,
  R6 Task 13, R7 Tasks 5/14, R8 Tasks 7/12/13/14/16, R9 Tasks 7/16, R10 Tasks 6/11/14, R11 Tasks 2/6. The bundled assistant skill is Task 18.
- **Cross-task interaction worth knowing:** Task 10's worker thread and Task 13's poller share
  `Session.events`. Appending from the worker while a request thread takes a slice is safe under the
  GIL, which is why no lock guards it; `Session.start` takes the lock only to stop two jobs starting
  at once.
- **Sharp edge:** `scanner.SETTLE` is read at call time so tests can patch it. Keep it that way —
  importing it as a bare name elsewhere would freeze it at 35 seconds and make every server test
  crawl.
- **Left for a second pass:** a throughput test per band, a firmware-3.x driver, a signed
  double-click bundle, keychain storage, a Persian UI. Each is in the spec with the trigger that
  should bring it back.
