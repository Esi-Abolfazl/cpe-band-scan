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


@pytest.mark.parametrize("given", ["", None])
def test_number_is_nan_when_there_is_nothing_to_read(given):
    assert math.isnan(metrics.number(given))


def test_number_reads_a_threshold_string_as_its_bound():
    """">=-140" is a real reading some firmware sends for "at or below -140", not a missing
    value, so it parses to the bound rather than nan."""
    assert metrics.number(">=-140") == -140.0


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


def test_rank_orders_by_grade_then_floor_then_typical_signal_and_auto_competes():
    results = {
        "B1": {"floor": 2, "sinr": 9, "rsrq": -8, "has5g": True},
        "B7": {"floor": 7, "sinr": 8, "rsrq": -8, "has5g": True},
        "B40": {"floor": 2, "sinr": 11, "rsrq": -8, "has5g": True},
        "B3": {"floor": 20, "sinr": 20, "rsrq": -8, "has5g": False},
        "auto": {"floor": 30, "sinr": 30, "rsrq": -8, "has5g": True},
    }
    assert metrics.rank(results) == ["auto", "B7", "B40", "B1"]


def test_a_fair_band_never_ranks_above_an_excellent_one_on_a_higher_floor():
    """B3 had the same floor and a better typical signal than B1, but a dirty channel made it
    Fair; the page then showed Fair above Excellent."""
    results = {
        "B3": {"floor": 7, "sinr": 8, "rsrq": -16, "has5g": True},
        "B1": {"floor": 7, "sinr": 7, "rsrq": -6.5, "has5g": True},
    }
    assert metrics.rank(results) == ["B1", "B3"]


def test_rank_keeps_a_band_with_no_5g_when_none_is_expected():
    results = {
        "B1": {"floor": 5, "sinr": 9, "rsrq": -8, "has5g": False},
        "auto": {"floor": 30, "sinr": 30, "rsrq": -8, "has5g": True},
    }
    assert metrics.rank(results, expect_5g=False) == ["auto", "B1"]


def test_supported_bands_come_from_the_router_config():
    data = {"config/network/bandfreqlist.xml": {"config": {
        "lte_support_band_list": "1,3,7,40", "nr_support_band_list": "78,79"}}}
    router = router_for(data)
    assert metrics.supported_bands(router, "lte") == ["1", "3", "7", "40"]
    assert metrics.supported_bands(router, "nr") == ["78", "79"]


def test_visible_bands_never_raise():
    router = router_for({"device/nbrcellinfo": KeyError("gone"), "device/seccellinfo": {}})
    assert metrics.visible_bands(router) == {"lte": [], "nr": []}


def test_the_5g_side_is_ranked_by_the_5g_carrier():
    """During a 5G scan the 4G anchor stays on automatic, so the LTE floor is the same noise
    for every NR band. Only the NR carrier's own numbers tell the bands apart."""
    results = {
        "N78": {"floor": 8, "sinr": 8, "rsrq": -8, "nrfloor": 1, "nrsinr": 2, "nrrsrp": -80, "has5g": True},
        "N1": {"floor": 8, "sinr": 8, "rsrq": -8, "nrfloor": 12, "nrsinr": 20, "nrrsrp": -90, "has5g": True},
        "N28": {"floor": 8, "sinr": 8, "rsrq": -8, "nrfloor": 12, "nrsinr": 22, "nrrsrp": -70, "has5g": True},
        "auto": {"floor": 8, "sinr": 8, "rsrq": -8, "nrfloor": 25, "nrsinr": 30, "nrrsrp": -60, "has5g": True},
    }
    assert metrics.rank(results, side="nr") == ["auto", "N28", "N1", "N78"]


def test_a_5g_band_is_rated_by_its_own_carrier_not_by_the_4g_anchor():
    """Regression: grade() read the LTE floor and RSRQ on the 5G side too, so an NR band at
    -5 dB riding an excellent 4G anchor outranked one at +25 dB on a merely good anchor."""
    weak = {"floor": 10, "sinr": 12, "rsrq": -8, "nrfloor": -5, "nrsinr": -5, "nrrsrp": -100, "has5g": True}
    strong = {"floor": 1, "sinr": 3, "rsrq": -12, "nrfloor": 25, "nrsinr": 25, "nrrsrp": -85, "has5g": True}
    assert metrics.rank({"N41": weak, "N78": strong}, side="nr") == ["N78", "N41"]
    assert metrics.grade(strong, side="nr") == "excellent"
    assert metrics.grade(weak, side="nr") == "fair"


def test_the_4g_anchor_alone_never_reorders_the_5g_side():
    nr = [{"nrfloor": 9, "nrsinr": 10, "nrrsrp": -80}, {"nrfloor": 3, "nrsinr": 4, "nrrsrp": -80}]
    for lte in ({"floor": -8, "sinr": -6, "rsrq": -20}, {"floor": 12, "sinr": 14, "rsrq": -6}):
        results = {"N78": {**nr[0], **lte, "has5g": True},
                   "N41": {**nr[1], "floor": 12, "sinr": 14, "rsrq": -6, "has5g": True}}
        assert metrics.rank(results, side="nr") == ["N78", "N41"]


def test_the_5g_floor_is_the_lowest_nr_reading_that_was_reported():
    data = {"device/signal": Seq([signal(nrsinr="9"), signal(nrsinr=""), signal(nrsinr="3")])}
    assert metrics.measure(router_for(data), samples=3, sleep=lambda s: None)["nrfloor"] == 3.0


def test_the_4g_side_is_still_ranked_by_the_floor():
    results = {
        "B7": {"floor": 7, "sinr": 8, "rsrq": -8, "nrsinr": 2, "nrrsrp": -80, "has5g": True},
        "B1": {"floor": 2, "sinr": 9, "rsrq": -8, "nrsinr": 20, "nrrsrp": -70, "has5g": True},
    }
    assert metrics.rank(results, side="lte") == ["B7", "B1"]


def test_rank_leaves_out_rows_that_have_no_number_to_rank_on():
    """No NR field reported means nrsinr is nan; nan compares false everywhere, so sorting on
    it returns input order dressed up as a ranking."""
    nan = float("nan")
    results = {
        "N78": {"floor": 8, "sinr": 8, "rsrq": -8, "nrfloor": nan, "nrsinr": nan, "nrrsrp": nan, "has5g": False},
        "N1": {"floor": 8, "sinr": 8, "rsrq": -8, "nrfloor": 15, "nrsinr": 20, "nrrsrp": -90, "has5g": True},
    }
    assert metrics.rank(results, expect_5g=False, side="nr") == ["N1"]


def test_carriers_are_parsed_from_the_firmware_band_string():
    parsed = metrics.carriers("20MHz@3300(B7) + 20MHz@1500(B3) + 100MHz@650000(N78)")
    assert parsed == [
        {"tech": "lte", "band": "B7", "width_mhz": 20, "earfcn": 3300},
        {"tech": "lte", "band": "B3", "width_mhz": 20, "earfcn": 1500},
        {"tech": "nr", "band": "N78", "width_mhz": 100, "earfcn": 650000}]


def test_carriers_survive_a_bare_band_string_and_an_empty_one():
    assert [c["band"] for c in metrics.carriers("B7(N78)")] == ["B7", "N78"]
    assert metrics.carriers("") == []


def test_sample_carries_the_parsed_carriers():
    taken = metrics.sample(router_for({"device/signal": signal()}))
    assert [c["tech"] for c in taken["carriers"]] == ["lte", "nr"]
