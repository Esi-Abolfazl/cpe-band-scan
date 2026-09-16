import re
import string
from pathlib import Path

import pytest

from cpe_band_scan import copy

SRC = Path(__file__).resolve().parents[1] / "src" / "cpe_band_scan"
CALLERS = "".join(path.read_text(encoding="utf-8") for path in SRC.rglob("*")
                  if path.suffix in (".py", ".js") and path.name != "copy.py")


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
                "delete", "refresh", "start", "apply")


def test_every_button_label_starts_with_a_verb():
    """A button says what happens when you press it, so its first word is the action."""
    for key, entry in copy.ACTIONS.items():
        first = entry["label"].split()[0].lower()
        assert first in BUTTON_VERBS, f"{key} does not start with a verb: {entry['label']}"


ACTIONS_WORDS = ("try", "check", "wait", "enter", "switch", "open", "use", "keep", "scan",
                 "stop", "change", "turn")


def test_every_error_ends_with_something_the_person_can_do():
    """A message that only describes the failure leaves the person stuck, so the last
    sentence carries an instruction. Match whole words: a substring check passes
    "usually" as "use", which is how the first version of this test passed a dead end."""
    for code, message in copy.ERRORS.items():
        tail = [part for part in message.split(".") if part.strip()][-1].lower()
        tail = tail.replace(copy.APP["name"].lower(), "")   # "CPE Band Scan" contains an action word
        assert any(re.search(rf"\b{word}\b", tail) for word in ACTIONS_WORDS), \
            f"{code} dead-ends: {message}"


def test_error_placeholders_are_only_the_ones_callers_pass():
    allowed = {"url", "detail", "band", "bands", "name", "minutes", "count", "index",
               "total", "grade", "floor", "side", "sets", "width", "what", "left"}
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
                                  "busy", "not_connected", "crash",
                                  "bad_request"])
def test_every_failure_the_engine_can_raise_has_a_message(code):
    assert copy.ERRORS[code]


@pytest.mark.parametrize("grade", ["excellent", "good", "fair", "poor", "no5g"])
def test_every_grade_has_a_label(grade):
    assert copy.GRADES[grade]


def test_the_stopped_sentence_says_nothing_about_the_router():
    """It renders for a cancelled test as well as a cancelled scan, so it can only speak
    about the run. What happened to the lock has its own sentences now, and which of them
    renders is not known when this one is written."""
    assert "router" not in copy.PROGRESS["cancelled"].lower()


def test_no_message_claims_a_crash_or_a_dead_scan_leaves_the_router_on_automatic():
    """Both used to say so. A scan that stops on its own now puts back the lock the router
    arrived with, so 'back on automatic' is exactly the state the person is not in."""
    for code in ("crash",):
        assert "automatic" not in copy.ERRORS[code].lower(), copy.ERRORS[code]


def test_every_error_sentence_is_raised_somewhere():
    """A sentence nobody raises is a sentence nobody maintains; two of them still claimed the
    router was back on automatic long after that stopped being true."""
    for code in copy.ERRORS:
        assert f'"{code}"' in CALLERS, f"ERRORS[{code!r}] has no caller"


def test_the_scan_scope_offers_all_4g_and_5g_and_each_explains_itself():
    options = copy.FIELDS["scan_scope"]["options"]
    assert list(options) == ["all", "lte", "nr"]
    for key, option in options.items():
        assert option["label"].strip() and option["help"].strip(), f"scan_scope.{key} is unexplained"


def test_there_is_one_scan_button_not_three():
    assert "scan" in copy.ACTIONS
    assert not {"scan_all", "scan_4g", "scan_5g"} & set(copy.ACTIONS)


def test_bad_request_does_not_tell_a_terminal_user_to_reload_a_page():
    assert "page" not in copy.ERRORS["bad_request"].lower()
