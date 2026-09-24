"""What the page does and sends, executed in Node rather than read from its source."""
import json

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
