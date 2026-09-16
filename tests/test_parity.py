"""The page and the copy catalogue must agree."""
import re
from pathlib import Path

import pytest

from cpe_band_scan import copy

WEB = Path(__file__).resolve().parents[1] / "src" / "cpe_band_scan" / "web"
APP_JS = "\n".join(p.read_text(encoding="utf-8") for p in sorted(WEB.glob("*.js")))
INDEX = (WEB / "index.html").read_text(encoding="utf-8")
# The <title> holds the app's own name (copy.APP, not a FIELDS/ACTIONS/COLUMNS label) and
# legitimately shares words with them (COLUMNS.band's "Band" vs. "CPE Band Scan") - only the
# body is the shell a hardcoded catalogue label would actually turn up in.
INDEX_BODY = re.search(r"<body>(.*)</body>", INDEX, re.S).group(1)

USED_HELP = set(re.findall(r'help\(\s*"(\w+)"\s*,\s*"(\w+)"\s*\)', APP_JS))
USED_COPY = set(re.findall(r'copy\.(\w+)\.(\w+)', APP_JS))

LITERALS = (set(re.findall(r'"([^"\\\n]*)"', APP_JS))
            | set(re.findall(r"'([^'\\\n]*)'", APP_JS))
            | set(re.findall(r"`([^`\\\n]*)`", APP_JS)))


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


@pytest.mark.parametrize("group", ["FIELDS", "COLUMNS"])
def test_labels_carry_their_explanation_as_a_hover_not_a_question_mark(group):
    assert f'help("{group}"' in APP_JS
    assert 'title: entry.help' in APP_JS
    assert '"?"' not in APP_JS, "the ? buttons are gone for good (2026-09-16 review)"


def test_buttons_explain_themselves_on_hover_only():
    """A button says what it does; a ? next to it is clutter (2026-09-16 review)."""
    assert 'help("ACTIONS"' not in APP_JS
    assert "title: copy.ACTIONS[key].help" in APP_JS


def test_the_page_never_hardcodes_words_the_catalogue_owns():
    """Every label is built at runtime from the catalogue, so a label appearing as a string
    literal in the page means someone wrote a word the catalogue is supposed to own."""
    for group in ("FIELDS", "ACTIONS", "COLUMNS"):
        for key, entry in getattr(copy, group).items():
            if not entry["label"]:
                continue
            assert entry["label"] not in LITERALS, f"{group}.{key} is hardcoded in app.js"
            assert entry["label"] not in INDEX_BODY, f"{group}.{key} is hardcoded in index.html"


def test_the_bootstrap_placeholder_is_still_there():
    assert "/*BOOTSTRAP*/" in INDEX, "the server injects the token and copy at this marker"


SRC = Path(__file__).resolve().parents[1] / "src"
FORBIDDEN_ENDPOINT = "net-mode"   # firmware 4.x answers this endpoint without an error, but
                                   # writing a band list to it also applies the mode field and
                                   # silently switches 5G off - net/lock-freq is the only
                                   # endpoint this app is allowed to write a band lock through
FORBIDDEN_ARG = "LTEBand"         # the argument name that goes with that same endpoint


def test_poll_gives_up_after_repeated_failures():
    """Fix 7: poll() treated a failed request as 'nothing new' and re-armed indefinitely, so
    a dead server was indistinguishable from a running scan on the one screen the person is
    watching. It must count consecutive failures, reset the count on any success, and once
    a few have piled up, stop polling and show the catalogue's crash sentence."""
    poll_body = re.search(r"async function poll\(\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert re.search(r"pollFailures\s*(\+=\s*1|=\s*state\.pollFailures\s*\+\s*1)", poll_body), \
        "poll() never counts consecutive failures"
    assert re.search(r"pollFailures\s*=\s*0", poll_body), \
        "poll() never resets the failure count on a successful poll"
    assert "copy.ERRORS.crash" in poll_body or 'copy.ERRORS["crash"]' in poll_body, \
        "poll() never shows the catalogue's crash sentence once it gives up"


def test_starting_a_scan_or_test_resets_the_poll_failure_counter():
    """pollFailures only reset on a successful poll, so a scan or test started right after a
    give-up began partway to giving up again. Starting one must reset the counter."""
    for name in ("onScan", "onTest"):
        pattern = rf"async function {name}\([^)]*\)\s*\{{(.*?)\n\}}"
        body = re.search(pattern, APP_JS, re.S).group(1)
        assert re.search(r"pollFailures\s*=\s*0", body), f"{name}() never resets pollFailures"


def _normalised(text: str) -> str:
    """Strip what a careless (or deliberate) reintroduction would use to dodge a plain
    substring search: quotes, whitespace and concatenation operators. `"net-" "mode"` or
    `"net-" + "mode"` both collapse back to `net-mode` once these are gone."""
    return re.sub(r'[\'"\s+]', "", text)


def test_no_source_file_touches_the_forbidden_net_mode_endpoint():
    """Writing a band list to net-mode is rejected by the firmware yet still applies the mode
    part, which switches 5G off with no warning. The whole driver design in lockfreq.py exists
    to avoid this endpoint - if this test trips, route the change through lockfreq.py instead
    of deleting the guard. The source is normalised first so splitting the endpoint name across
    two string pieces can't slip past a plain substring search."""
    for path in sorted(SRC.rglob("*.py")):
        normalised = _normalised(path.read_text(encoding="utf-8"))
        assert FORBIDDEN_ENDPOINT not in normalised, f"{path} touches the forbidden net-mode endpoint"
        assert FORBIDDEN_ARG not in normalised, f"{path} references LTEBand, the net-mode argument"


def test_the_typed_profile_name_is_kept_in_state_not_only_in_the_input():
    """render() rebuilds every element, so an input's value lives only as long as the next
    render. Refresh, apply and the poll all render; the typed name must be in state."""
    body = re.search(r"function profilesCard\(\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert "state.profileName" in body, "profilesCard() does not read the typed name back"
    assert re.search(r'addEventListener\(\s*"input"', body), "profilesCard() never records typing"


def test_the_scope_is_chosen_with_native_radios_and_one_start_button():
    """One primary action per screen: the person picks all / 4G / 5G, then presses Start.
    Native radios inside a fieldset keep the keyboard and screen-reader behaviour for free."""
    body = re.search(r"function scanCard\(\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'choices("scan_scope"' in body and 'action("scan"' in body
    radios = re.search(r"function choices\([^)]*\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'type: "radio"' in radios and '"fieldset"' in radios and '"legend"' in radios
    assert not re.search(r"scan_(all|4g|5g)", APP_JS), "the three old scan buttons are back"


def test_every_scope_option_label_comes_from_the_catalogue():
    for key, option in copy.FIELDS["scan_scope"]["options"].items():
        assert option["label"] not in LITERALS, f"scan_scope.{key} is hardcoded in app.js"


def test_resume_restores_the_suggested_name():
    body = re.search(r"async function resume\(\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert "suggested_name" in body


def test_the_page_and_the_terminal_put_the_speed_columns_in_the_same_place():
    """Mirrors need a parity check: the two front ends each insert the same two keys at the
    same index, and both only when the run carries speed."""
    from cpe_band_scan import cli
    keys = re.search(r"const SPEED_KEYS\s*=\s*\[(.*?)\]", APP_JS).group(1)
    page_keys = [key.strip().strip('"') for key in keys.split(",")]
    assert page_keys == list(cli.SPEED_KEYS)
    page_at = int(re.search(r"const SPEED_AT\s*=\s*(\d+)", APP_JS).group(1))
    assert page_at == cli.SPEED_AT
    table = re.search(r"function resultsTable\(run\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert "columnKeys(run)" in table and "run.speed" in table
    assert "showsSpeed(run)" in table
    assert 'bypass !== "blocked"' in APP_JS


def test_the_scan_form_offers_the_speed_test_on_by_default_and_sends_the_choice():
    assert re.search(r"speedTest:\s*true", APP_JS), "the speed test is on until unticked"
    card = re.search(r"function scanCard\(\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'toggle("speed_test"' in card
    scan = re.search(r"async function onScan\([^)]*\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert "speed: state.speedTest" in scan


def test_the_verdict_is_said_under_the_table_and_in_the_log():
    table = re.search(r"function resultsTable\(run\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'copy.NOTES["probe_" + run.speed.bypass]' in table
    describe = re.search(r"function describe\(event\)\s*\{(.*?)\n\}", APP_JS, re.S).group(1)
    assert 'copy.NOTES["probe_" + event.speed.bypass]' in describe
    assert "words.log_result_probe" in describe
