import json
from datetime import datetime

import pytest

from cpe_band_scan import store


RUN = {"kind": "scan", "device": {"carrier": "MCI", "model": "H155-381"},
       "sides": {"lte": {"order": ["B7", "B40"], "results": {"B7": {"floor": 7}}}}}


@pytest.fixture
def home(isolated_home, tmp_path):
    return tmp_path


def test_the_default_name_uses_the_carrier_and_the_date():
    assert store.default_name("MCI", datetime(2026, 9, 16, 21, 40)) == "MCI — 16 Sep 2026, 21:40"


def test_an_unknown_carrier_still_gets_a_usable_name():
    assert store.default_name("", datetime(2026, 9, 16, 21, 40)).startswith("Unknown carrier")


def test_saving_names_the_run_after_the_carrier_by_default():
    saved = store.save(RUN)
    assert saved["name"].startswith("MCI — ")
    assert saved["id"]


def test_a_given_name_wins_over_the_default():
    assert store.save(RUN, name="Living room, MCI")["name"] == "Living room, MCI"


def test_a_saved_run_can_be_loaded_back_whole():
    saved = store.save(RUN)
    assert store.load(saved["id"])["sides"]["lte"]["order"] == ["B7", "B40"]


def test_two_runs_saved_in_the_same_second_keep_separate_files():
    first, second = store.save(RUN), store.save(RUN)
    assert first["id"] != second["id"]
    assert len(store.list_runs()) == 2


def test_two_runs_saved_in_the_same_second_still_have_a_stable_order(home):
    """A shared timestamp must not leave the order to whatever the filesystem returns."""
    first = store.save(RUN, name="earlier")
    second = store.save(RUN, name="later")
    same = json.loads((home / "runs" / f"{first['id']}.json").read_text(encoding="utf-8"))
    later = json.loads((home / "runs" / f"{second['id']}.json").read_text(encoding="utf-8"))
    later["saved"] = same["saved"]
    (home / "runs" / f"{second['id']}.json").write_text(json.dumps(later), encoding="utf-8")
    assert [row["name"] for row in store.list_runs()] == ["later", "earlier"]


def test_the_list_carries_enough_to_choose_between_runs():
    store.save(RUN, name="Living room")
    row = store.list_runs()[0]
    assert row["name"] == "Living room"
    assert row["carrier"] == "MCI"
    assert row["best"] == "B7"
    assert row["kind"] == "scan"


def test_a_5g_only_run_reports_its_5g_side_as_best_and_labels_the_row():
    run_5g_only = {"kind": "scan", "device": {"carrier": "MCI", "model": "H155-381"},
                   "sides": {"nr": {"order": ["N78", "N41"], "results": {"N78": {"floor": 8}}}}}
    assert store.best_of(run_5g_only) == "N78"
    store.save(run_5g_only, name="5G only")
    row = next(row for row in store.list_runs() if row["name"] == "5G only")
    assert row["best"] == "N78"
    assert row["sides"] == ["nr"]


def test_runs_are_listed_newest_first():
    store.save(RUN, name="older")
    store.save(RUN, name="newer")
    assert [row["name"] for row in store.list_runs()] == ["newer", "older"]


def test_renaming_keeps_the_rest_of_the_run():
    saved = store.save(RUN)
    renamed = store.rename(saved["id"], "Bedroom")
    assert renamed["name"] == "Bedroom"
    assert store.load(saved["id"])["sides"]["lte"]["order"] == ["B7", "B40"]


def test_deleting_removes_it_from_the_list():
    saved = store.save(RUN)
    store.delete(saved["id"])
    assert store.list_runs() == []


@pytest.mark.parametrize("bad_id", ["../../etc/passwd", "..", "run/../..", "nope",
                                    "20260916-214000\n"])
def test_a_run_id_that_is_not_an_id_is_refused(bad_id):
    with pytest.raises(KeyError):
        store.load(bad_id)


def test_a_corrupt_file_is_skipped_not_crashed_on(home):
    store.save(RUN)
    (home / "runs" / "broken.json").write_text("{not json", encoding="utf-8")
    assert len(store.list_runs()) == 1


def test_a_run_with_a_made_up_id_is_saved_under_a_minted_one(home):
    """load, rename and delete already refuse an id that is not ours; save must too, or a
    request with id "../x" writes outside the runs folder."""
    saved = store.save(dict(RUN, id="../escaped"))
    assert store.RUN_ID.match(saved["id"])
    assert not (home / "escaped.json").exists()
    assert [path.parent for path in home.rglob("*.json")] == [home / "runs"]


def test_a_run_saved_again_keeps_its_own_id(home):
    first = store.save(RUN)
    assert store.save(first)["id"] == first["id"]
