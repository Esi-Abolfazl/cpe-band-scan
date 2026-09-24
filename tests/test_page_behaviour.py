"""What the page does and sends, executed in Node rather than read from its source."""
import json

from cpe_band_scan import api
from tests import page

RESULTS = {"sides": {"lte": {"order": ["B7", "auto", "B3"], "sets": {"B7": ["7"], "auto": [], "B3": ["3"]},
                             "results": {}, "skipped": {}},
                     "nr": {"order": ["N78", "auto"], "sets": {"N78": ["78"], "auto": []},
                            "results": {}, "skipped": {}}}}
TEST_FILES = ["app.js", "test.js"]
STUBS = "globalThis.render = () => {}; globalThis.poll = () => {}; globalThis.buildTestLive = () => null;"


def start_test(lte="", nr=""):
    return page.run(TEST_FILES, STUBS + f"""
        state.results = {json.dumps(RESULTS)};
        state.testTarget = "pick"; state.testPick = {{ lte: "{lte}", nr: "{nr}" }}; state.testMinutes = "1";
        const words = testWhat();
        await onTest();
        return words;""")


def test_picking_automatic_for_a_test_asks_for_automatic_not_for_the_current_lock():
    """Regression: the auto row's empty band list was dropped from the request, so the test
    measured whatever was locked - B7 - while the page said it was testing automatic."""
    ran = start_test(lte="auto")
    assert ran["requests"][0]["body"] == {"seconds": 60, "gap": 10, "lte": [], "scell": []}
    assert "automatic" in ran["result"]


def test_picking_a_band_keeps_the_other_ranked_bands_as_secondaries_and_leaves_5g_alone():
    ran = start_test(lte="B7")
    assert ran["requests"][0]["body"] == {"seconds": 60, "gap": 10, "lte": ["7"], "scell": ["3"]}


def test_picking_5g_automatic_leaves_the_4g_side_as_it_is():
    ran = start_test(nr="auto")
    assert ran["requests"][0]["body"] == {"seconds": 60, "gap": 10, "nr": []}


def in_use(current, saved):
    return page.run(["app.js", "test.js", "profiles.js"], f"""
        state.status = {{ lock: {json.dumps(current)} }};
        return profileInUse({{ lock: {json.dumps(saved)} }});""")["result"]


def test_a_profile_that_differs_only_in_its_secondary_carriers_is_not_in_use():
    """Regression: only anchors were compared, so B7 + B1 showed In use over B7 + B3 and its
    Apply button was gone."""
    assert in_use({"lte": [["7"], ["3"]], "nr": [[], []]}, {"lte": [["7"], ["1"]], "nr": [[], []]}) is False
    assert in_use({"lte": [[], []], "nr": [["78"], ["41"]]}, {"lte": [[], []], "nr": [["78"], []]}) is False


def test_a_profile_with_the_same_bands_in_another_order_is_in_use():
    assert in_use({"lte": [["7"], ["1", "3"]], "nr": [["78"], []]},
                  {"lte": [["7"], ["3", "1"]], "nr": [["78"], []]}) is True


def test_a_failed_profile_read_keeps_the_list_and_says_why():
    """Regression: any failure replaced the list with [], telling the person they had no saved
    profiles when the file was only unreadable."""
    ran = page.run(["app.js", "test.js", "profiles.js"], """
        state.profiles = [{ id: "a", name: "Home" }];
        await refreshProfiles();
        return state.profiles.map((profile) => profile.name);""",
        responses={f"GET {api.ROUTES['profiles']}": {"status": 409, "body": {
            "error": "store_unreadable", "message": "Can't read profiles.json"}}})
    assert ran["result"] == ["Home"]
    assert ran["banner"] == "Can't read profiles.json"
