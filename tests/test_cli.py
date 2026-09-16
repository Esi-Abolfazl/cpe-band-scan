import re
from pathlib import Path

import pytest

from cpe_band_scan import cli, copy

WEB_APP_JS = (Path(__file__).resolve().parents[1] / "src" / "cpe_band_scan"
             / "web" / "app.js").read_text(encoding="utf-8")


def test_render_turns_an_event_into_a_sentence():
    line = cli.render({"type": "set_start", "name": "B7", "index": 3, "total": 18, "eta_s": 600})
    assert "B7" in line and "3 of 18" in line


def test_render_names_the_grade_in_words():
    line = cli.render({"type": "set_result", "name": "B7",
                       "result": {"grade": "excellent", "floor": 7.0}})
    assert copy.GRADES["excellent"] in line


def test_render_ignores_events_with_nothing_to_say():
    assert cli.render({"type": "run_start", "sides": ["lte"], "expect_5g": True, "baseline": {}}) is not None
    assert cli.render({"type": "nonsense"}) is None


def test_render_announces_the_start_of_a_side():
    line = cli.render({"type": "side_start", "side": "lte", "total": 6, "eta_s": 900})
    assert line is not None
    assert copy.SIDES["lte"] in line and "6" in line


def test_the_password_comes_from_the_environment_before_prompting(monkeypatch):
    monkeypatch.setenv("CPE_BAND_SCAN_PASSWORD", "from-env")
    assert cli.read_password(cli.parse(["status"])) == "from-env"


def test_the_password_comes_from_a_dot_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("CPE_BAND_SCAN_PASSWORD", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PASSWORD='shh'\n", encoding="utf-8")
    assert cli.read_password(cli.parse(["status"])) == "shh"


def test_the_default_router_address_is_the_huawei_one():
    assert cli.parse(["status"]).url == "http://192.168.8.1/"


def test_apply_parses_anchors_secondaries_and_the_nr_side():
    args = cli.parse(["apply", "7", "--scell", "3,40", "--nr", "78"])
    assert (args.bands, args.scell, args.nr) == ("7", "3,40", "78")


@pytest.mark.parametrize("argv,expected", [
    (["scan"], (("lte", "nr"), [])),
    (["scan", "4g"], (("lte",), [])),
    (["scan", "5g"], (("nr",), [])),
    (["scan", "5g", "78"], (("nr",), ["78"])),
    (["scan", "4g", "7", "40"], (("lte",), ["7", "40"])),
    (["scan", "7", "40"], (("lte",), ["7", "40"])),
])
def test_scan_target_reads_the_side_and_the_bands(argv, expected):
    """Bare band numbers are 4G bands. Sending them to the 5G side as well meant N7 and N40,
    two minutes of refusals nobody asked for."""
    assert cli.scan_target(cli.parse(argv)) == expected


def test_the_password_cannot_be_passed_on_the_command_line():
    """argv is visible in ps and lands in shell history, which is disk."""
    with pytest.raises(SystemExit):
        cli.parse(["--password", "x", "status"])


def test_apply_tells_the_truth_about_the_next_30_seconds(monkeypatch, capsys):
    from cpe_band_scan.router import Router
    from tests.fakes import FakeSession, factory
    from tests.test_scanner import DEVICE
    router = Router("192.168.8.1", "pw", connection_factory=factory(FakeSession()))
    monkeypatch.setattr(cli, "connect", lambda args: (router, DEVICE))
    assert cli.main(["apply", "7", "--scell", "3"]) == 0
    out = capsys.readouterr().out
    assert copy.text("PROGRESS", "lock_written", bands="7") in out
    assert "connection is back" not in out


def test_help_lists_every_command(capsys):
    assert cli.main(["help"]) == 0
    printed = capsys.readouterr().out
    for command in ("scan", "status", "test", "apply", "clear", "runs", "ui"):
        assert command in printed


def test_help_describes_each_command_distinctly(capsys):
    cli.main(["help"])
    lines = {line.split(None, 1)[0]: line for line in capsys.readouterr().out.splitlines()
             if line.strip().startswith(("ui ", "runs ", "show "))}
    assert copy.FIELDS["scan_scope"]["options"]["all"]["help"] not in lines["ui"]
    assert lines["runs"] != lines["show"]


def test_a_router_error_prints_the_sentence_not_a_traceback(capsys, monkeypatch):
    from cpe_band_scan.router import RouterError

    def explode(args):
        raise RouterError("bad_password")

    monkeypatch.setattr(cli, "connect", explode)
    monkeypatch.setenv("CPE_BAND_SCAN_PASSWORD", "x")
    assert cli.main(["status"]) == 1
    assert copy.ERRORS["bad_password"][:30] in capsys.readouterr().err


def test_an_unexpected_exception_prints_the_crash_sentence_not_a_traceback(capsys, monkeypatch):
    def explode(args):
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "connect", explode)
    monkeypatch.setenv("CPE_BAND_SCAN_PASSWORD", "x")
    assert cli.main(["status"]) == 1
    assert copy.ERRORS["crash"][:30] in capsys.readouterr().err


def test_results_table_matches_the_pages_column_order():
    """Fix 5: the terminal and the page must show the same columns in the same order, or a
    run compared between the two disagrees about what it saw - including 5G quality, which
    the page showed but the terminal dropped entirely."""
    match = re.search(r"COLUMN_KEYS\s*=\s*\[(.*?)\]", WEB_APP_JS, re.S)
    page_keys = [key.strip().strip('"') for key in match.group(1).replace("\n", " ").split(",")]
    row = {"grade": "excellent", "floor": 7.0, "sinr": 9.0, "rsrq": -9.0, "rsrp": -80.0,
          "nrsinr": 12.0, "has5g": True, "band": "B7(N78)"}
    run = {"sides": {"lte": {"order": ["B7"], "results": {"B7": row}}}}
    header = cli.results_table(run).splitlines()[0]
    expected = "| " + " | ".join(copy.COLUMNS[key]["label"] for key in page_keys) + " |"
    assert header == expected


def test_results_table_lists_ranked_bands_in_order_with_the_auto_row_last():
    keys = ("rank", "band", "grade", "five_g", "floor", "sinr", "rsrq", "rsrp", "nr_sinr", "carriers")
    row = lambda grade, floor, sinr, rsrq, rsrp, has5g, band: {
        "grade": grade, "floor": floor, "sinr": sinr, "rsrq": rsrq, "rsrp": rsrp,
        "has5g": has5g, "band": band, "nrsinr": 12.0,
    }
    run = {"sides": {"lte": {
        "order": ["B3", "B7"],
        "results": {
            "B7": row("excellent", 7.0, 9.0, -9.0, -80.0, True, "B7"),
            "B3": row("good", 2.0, 5.0, -11.0, -85.0, True, "B3"),
            "auto": row("fair", -2.0, 1.0, -14.0, -95.0, False, "auto-band"),
        },
    }}}

    lines = cli.results_table(run).splitlines()

    header, separator, *data_lines = lines
    for key in keys:
        assert copy.COLUMNS[key]["label"] in header
    assert set(separator) <= {"|", "-"}
    assert len(data_lines) == 3

    names_in_order = [line.split("|")[2].strip() for line in data_lines]
    assert names_in_order == ["B3", "B7", "auto"]


def test_the_applied_line_names_every_band_the_lock_now_holds():
    """The page joins the LTE and NR bands; the terminal printed `lte or nr`, so a 5G scan
    announced the restored 4G anchor and never the NR band it had chosen."""
    line = cli.render({"type": "applied", "signal": {},
                       "plan": {"lte": ["7"], "lte_scell": ["3"], "nr": ["78"]}})
    assert "7, 78" in line, "the terminal must name the same bands as the page, joined the same way"


def test_the_terminal_has_a_sentence_for_a_scan_that_changed_nothing():
    """A scan that concluded nothing keeps the person's lock. That is a result, and both
    front ends have to say it - silence reads as a scan that did something unnamed."""
    assert cli.render({"type": "unchanged"}) == copy.PROGRESS["unchanged"]
    assert 'case "unchanged"' in WEB_APP_JS, "the page must render it too, or the two disagree"


def test_both_front_ends_say_whether_the_lock_came_back():
    """A cancelled scan either put the arriving lock back or did not, and the two are not
    the same news. Neither front end may leave it unsaid."""
    for kind in ("lock_back", "lock_lost"):
        assert cli.render({"type": kind}) == copy.PROGRESS[kind]
        assert f'case "{kind}"' in WEB_APP_JS, "the page must render it too"


def test_help_explains_each_scan_scope_in_the_catalogue_s_words(capsys):
    cli.main(["help"])
    out = capsys.readouterr().out
    for option in copy.FIELDS["scan_scope"]["options"].values():
        assert option["help"] in out


def test_scan_has_a_no_speed_switch_and_speed_is_on_by_default():
    assert cli.parse(["scan"]).speed is True
    assert cli.parse(["scan", "--no-speed"]).speed is False
    assert cli.parse(["scan", "--no-speed", "4g", "7"]).speed is False


def _run_with_speed():
    row = {"grade": "excellent", "floor": 7.0, "sinr": 9.0, "rsrq": -9.0, "rsrp": -80.0,
           "nrsinr": 12.0, "has5g": True, "band": "B7(N78)",
           "speed": {"latency_ms": 85, "jitter_ms": 12, "mbps": 42.5, "bytes": 1, "seconds": 5.0}}
    dead = dict(row, speed={"error": "no_answer"})
    return {"speed": {"bypass": "confirmed", "lan_ip": "192.168.8.2", "public_ip": "5.1.1.1"},
            "sides": {"lte": {"order": ["B7", "B3"], "results": {"B7": row, "B3": dead}}}}


def test_results_table_adds_speed_and_ping_after_the_5g_column_only_when_the_run_has_them():
    plain = {"sides": {"lte": {"order": ["B7"], "results": {"B7": {
        "grade": "excellent", "floor": 7.0, "sinr": 9.0, "rsrq": -9.0, "rsrp": -80.0,
        "nrsinr": 12.0, "has5g": True, "band": "B7(N78)"}}}}}
    assert cli.column_keys(plain) == list(cli.BASE_KEYS)
    keys = cli.column_keys(_run_with_speed())
    assert keys[cli.SPEED_AT:cli.SPEED_AT + 2] == ["speed", "ping"]
    assert keys[:cli.SPEED_AT] == list(cli.BASE_KEYS[:cli.SPEED_AT])
    header, _, first, second = cli.results_table(_run_with_speed()).splitlines()
    assert copy.COLUMNS["speed"]["label"] in header and copy.COLUMNS["ping"]["label"] in header
    cells = [cell.strip() for cell in first.split("|")[1:-1]]
    assert cells[cli.SPEED_AT] == "42.5" and cells[cli.SPEED_AT + 1] == "85"
    dead_cells = [cell.strip() for cell in second.split("|")[1:-1]]
    assert dead_cells[cli.SPEED_AT] == copy.NOTES["probe_no_answer"]


def test_a_blocked_probe_adds_no_columns_but_keeps_its_sentence():
    run = _run_with_speed()
    run["speed"]["bypass"] = "blocked"
    assert cli.column_keys(run) == list(cli.BASE_KEYS)
    assert cli.speed_note(run) == copy.NOTES["probe_blocked"]


def test_the_speed_note_names_the_verdict_and_is_silent_without_one():
    assert cli.speed_note(_run_with_speed()) == copy.NOTES["probe_confirmed"]
    assert cli.speed_note({"sides": {}}) == ""


def test_render_says_speed_and_ping_when_a_result_has_them_and_not_when_the_probe_failed():
    with_speed = cli.render({"type": "set_result", "name": "B7",
                             "result": {"grade": "excellent", "floor": 7.0,
                                        "speed": {"latency_ms": 85, "jitter_ms": 1, "mbps": 42.5, "bytes": 1, "seconds": 5}}})
    assert "42.5" in with_speed and "85" in with_speed
    failed = cli.render({"type": "set_result", "name": "B7",
                         "result": {"grade": "excellent", "floor": 7.0, "speed": {"error": "no_answer"}}})
    assert "Mbit" not in failed


def test_render_opens_the_scan_with_the_bypass_verdict_when_there_is_one():
    line = cli.render({"type": "run_start", "sides": ["lte"], "expect_5g": True, "baseline": {},
                       "speed": {"bypass": "failed", "lan_ip": "", "public_ip": ""}})
    assert copy.NOTES["probe_failed"] in line
    plain = cli.render({"type": "run_start", "sides": ["lte"], "expect_5g": True, "baseline": {}})
    assert "VPN" not in plain
