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
    "device/signal": {"band": "B7(N78)", "sinr": "8dB", "rsrq": "-10dB", "rsrp": "-85dBm",
                      "nrsinr": "12", "nrrsrp": "-80"},
    "device/nbrcellinfo": {},
    "device/seccellinfo": {},
}


def router_for(overrides=None):
    data = dict(SUPPORTED, **(overrides or {}))
    return Router("192.168.8.1", "pw", connection_factory=factory(FakeSession(data)))


def test_a_supported_router_reports_its_driver_and_carrier():
    device = probe(router_for())
    assert device == Device(model="H155-381", firmware="4.0.0.5", driver="lockfreq",
                            carrier="MCI", plmn="43211")


def test_the_ten_line_firmware_is_supported_when_it_has_the_lock_page():
    """A version gate on "4." refused 10.0.5.2(H1SP9C43) before it was ever asked whether it has
    the page (reported 2026-09-18). The page decides; the version does not."""
    device = probe(router_for({"device/information": {"DeviceName": "H155-381",
                                                      "SoftwareVersion": "10.0.5.2(H1SP9C43)"}}))
    assert device.driver == "lockfreq"
    assert device.firmware == "10.0.5.2(H1SP9C43)"


def test_old_firmware_without_the_lock_page_names_the_interface_not_the_missing_page():
    with pytest.raises(RouterError) as caught:
        probe(router_for({"device/information": {"DeviceName": "B525", "SoftwareVersion": "3.11.1"},
                          "net/lock-freq": hx.ResponseErrorException("not here", 100002)}))
    assert caught.value.code == "firmware_not_supported"
    assert "3.11.1" in caught.value.detail


def test_the_switch_value_never_decides_only_the_page_does():
    """lock_freq_switch is 3 on the H155's firmware; other lines report something else while the
    page works, so a router that answers net/lock-freq is driven whatever the switch says."""
    device = probe(router_for({"net/net-feature-switch": {"lock_freq_switch": "1"}}))
    assert device.driver == "lockfreq"


def test_a_router_whose_lock_page_cannot_be_read_is_refused():
    with pytest.raises(RouterError) as caught:
        probe(router_for({"net/lock-freq": hx.ResponseErrorException("not here", 100002)}))
    assert caught.value.code == "no_band_lock"


def test_the_refusal_names_the_model_firmware_and_switch_so_one_report_is_enough():
    with pytest.raises(RouterError) as caught:
        probe(router_for({"net/lock-freq": hx.ResponseErrorException("not here", 100002),
                          "net/net-feature-switch": {"lock_freq_switch": "0"}}))
    detail = caught.value.detail
    assert "H155-381" in detail and "4.0.0.5" in detail and "lock_freq_switch='0'" in detail


def test_an_unreadable_switch_never_hides_why_the_lock_page_was_refused():
    with pytest.raises(RouterError) as caught:
        probe(router_for({"net/lock-freq": hx.ResponseErrorException("not here", 100002),
                          "net/net-feature-switch": hx.ResponseErrorException("nope", 100002)}))
    assert caught.value.code == "no_band_lock"
    assert "unreadable" in caught.value.detail


def test_a_missing_carrier_name_never_fails_the_probe():
    device = probe(router_for({"net/current-plmn": hx.ResponseErrorException("nope", 100002)}))
    assert device.carrier == ""
    assert device.driver == "lockfreq"


def test_the_carrier_falls_back_to_the_network_code():
    assert read_carrier(router_for({"net/current-plmn": {"Numeric": "43211"}})) == ("43211", "43211")


def test_as_dict_is_json_safe():
    assert probe(router_for()).as_dict()["model"] == "H155-381"
