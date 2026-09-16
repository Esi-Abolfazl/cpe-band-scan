import pytest

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


@pytest.mark.parametrize("given", ["78", b"78", 78, None, ["7x"], [""], [{"band": "7"}]])
def test_anything_but_a_list_of_band_numbers_is_refused(given):
    """`"78"` iterates to "7" and "8", which would lock two bands nobody asked for. The
    write path is the one place every caller passes through, so it is where this is checked."""
    with pytest.raises(ValueError):
        band_info(given)


def test_band_numbers_may_arrive_as_ints_or_strings():
    assert band_info([7, "40"])["all_bands"] == "7,40"
