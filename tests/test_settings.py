import os
import threading
import time

import pytest

from cpe_band_scan import store
from cpe_band_scan.router import RouterError


@pytest.fixture
def home(tmp_path):
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


def test_save_settings_never_writes_a_password_even_if_passed(home):
    store.save_settings(router_url="http://192.168.1.1/", password="secret")
    assert "secret" not in (home / "settings.json").read_text(encoding="utf-8")


def test_remember_password_is_the_one_path_that_writes_it_and_locks_the_file_down(home):
    store.remember_password("secret")
    assert store.remembered_password() == "secret"
    assert oct((home / "settings.json").stat().st_mode & 0o777) == "0o600"
    store.remember_password(None)
    assert store.remembered_password() == ""
    assert "secret" not in (home / "settings.json").read_text(encoding="utf-8")


LOCK = {"lte": (["3"], ["1", "7"]), "nr": (["78"], [])}


def test_a_profile_keeps_the_lock_and_comes_back_newest_first():
    first = store.save_profile("Home", "MCI", LOCK)
    second = store.save_profile("", "MCI", {"lte": ([], []), "nr": ([], [])})
    rows = store.list_profiles()
    assert [row["id"] for row in rows] == [second["id"], first["id"]]
    assert store.load_profile(first["id"])["lock"] == {"lte": [["3"], ["1", "7"]], "nr": [["78"], []]}
    assert second["name"].startswith("MCI")


def test_a_profile_can_be_renamed_and_deleted():
    saved = store.save_profile("Home", "MCI", LOCK)
    assert store.rename_profile(saved["id"], " Office ")["name"] == "Office"
    store.delete_profile(saved["id"])
    assert store.list_profiles() == []
    with pytest.raises(KeyError):
        store.load_profile(saved["id"])


def test_a_corrupt_settings_file_is_set_aside_rather_than_overwritten(home):
    """Read as empty and then saved over, a broken file used to lose whatever the person could
    still have recovered from it."""
    (home / "settings.json").write_text("{not json", encoding="utf-8")
    assert store.settings() == {}
    store.save_settings(router_url="http://192.168.8.1/")
    assert (home / "settings.json.bad").read_text(encoding="utf-8") == "{not json"
    assert store.settings() == {"router_url": "http://192.168.8.1/"}
    assert oct((home / "settings.json").stat().st_mode & 0o777) == "0o600"


def test_a_corrupt_profiles_file_is_reported_and_never_written_over(home):
    """Regression: it read as no profiles, and the next save wrote one profile over all of them."""
    (home / "profiles.json").write_text("{not json", encoding="utf-8")
    for attempt in (store.list_profiles, lambda: store.save_profile("New", "MCI", LOCK)):
        with pytest.raises(RouterError) as caught:
            attempt()
        assert caught.value.code == "store_unreadable"
    assert (home / "profiles.json").read_text(encoding="utf-8") == "{not json"


def test_renaming_different_profiles_at_once_keeps_every_rename(home, monkeypatch):
    """Two requests each read the file, changed one row and wrote it back: the later write
    undid the earlier rename."""
    ids = [store.save_profile(f"P{index}", "MCI", LOCK)["id"] for index in range(6)]
    replace = os.replace
    monkeypatch.setattr(os, "replace", lambda *args: (time.sleep(0.02), replace(*args)))
    threads = [threading.Thread(target=store.rename_profile, args=(profile_id, f"R{profile_id}"))
               for profile_id in ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(row["name"] for row in store.list_profiles()) == sorted(f"R{profile_id}" for profile_id in ids)


def test_a_write_that_fails_part_way_leaves_the_old_file_whole(home, monkeypatch):
    saved = store.save_profile("Home", "MCI", LOCK)
    before = (home / "profiles.json").read_bytes()

    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        store.rename_profile(saved["id"], "Work")
    assert (home / "profiles.json").read_bytes() == before
    assert sorted(path.name for path in home.iterdir()) == ["profiles.json"]
