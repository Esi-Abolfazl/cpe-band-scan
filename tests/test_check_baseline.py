"""The ratchet only lets a baseline count fall: a grown count fails, a fallen one asks for --write."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_baseline", ROOT / "scripts" / "check_baseline.py")
check_baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_baseline)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text('x = "MARK one"\ny = "MARK two"\n', encoding="utf-8")
    baseline = tmp_path / "gates-baseline.json"
    monkeypatch.setattr(check_baseline, "ROOT", tmp_path)
    monkeypatch.setattr(check_baseline, "BASELINE", baseline)

    def write(count):
        baseline.write_text(json.dumps({"routes": {"rule": "tst-04", "pattern": '"MARK ',
                                                   "files": ["*.py"], "count": count}}))
    return write


def test_equal_count_passes(repo):
    repo(2)
    assert check_baseline.main([]) == 0


def test_grown_count_fails(repo, capsys):
    repo(1)
    assert check_baseline.main([]) == 1
    assert "routes: 2 > baseline 1 (tst-04)" in capsys.readouterr().err


def test_fallen_count_fails_until_written(repo):
    repo(3)
    assert check_baseline.main([]) == 1
    assert check_baseline.main(["--write"]) == 0
    assert json.loads(check_baseline.BASELINE.read_text())["routes"]["count"] == 2
    assert check_baseline.main([]) == 0


def test_the_committed_baseline_matches_the_tree():
    assert check_baseline.main([]) == 0
