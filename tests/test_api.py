"""Handlers called directly, for the lock rules they own."""
import pytest

from cpe_band_scan import api, server
from tests.test_server_jobs import _locked_router_factory


_BOTH_WITH_SECONDARIES = {
    "lte_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "7"}]}, "all_bands": "3,7"},
    "nr_info": {"lock_mode": "3", "freq_infos": {"freq_info": [{"band": "78"}]}, "all_bands": "41,78"},
}


@pytest.mark.parametrize("body,kept,expected", [
    ({"lte": ["1"]}, "nr_info", "41,78"),
    ({"nr": ["41"]}, "lte_info", "3,7"),
])
def test_applying_one_side_keeps_the_other_sides_secondary_carriers(body, kept, expected):
    """Regression: apply refilled the untouched 5G side from its anchor alone, so locking a
    4G band silently dropped the 5G secondary carrier the person had."""
    make, fake = _locked_router_factory(_BOTH_WITH_SECONDARIES)
    session = server.Session(router_factory=make)
    session.connect("192.168.8.1", "pw", "admin")
    api.apply(session, body, "", {})
    assert fake.posts[-1][1][kept]["all_bands"] == expected
