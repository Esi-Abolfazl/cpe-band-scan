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
