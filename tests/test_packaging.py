import os
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_both_entry_points_reach_the_cli():
    scripts = PROJECT["project"]["scripts"]
    assert scripts["cpe-band-scan"] == "cpe_band_scan.cli:main"
    assert scripts["cpescan"] == "cpe_band_scan.cli:main", "the short alias saves ten keystrokes"


def test_the_web_assets_ship_with_the_package():
    assert "web/*" in PROJECT["tool"]["setuptools"]["package-data"]["cpe_band_scan"]


def test_only_one_runtime_dependency():
    assert PROJECT["project"]["dependencies"] == ["huawei-lte-api>=1.7"]


def test_the_readme_tells_someone_how_to_start_without_an_llm():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for needed in ("pipx install", "cpe-band-scan ui", "192.168.8.1", "192.168.1.1"):
        assert needed in readme


def test_the_skill_never_recommends_the_password_on_the_command_line():
    skill = (ROOT / "skills" / "bandscan" / "SKILL.md").read_text(encoding="utf-8")
    assert "--password" not in skill


def test_the_mac_launcher_runs_from_its_own_venv_and_is_executable():
    """The system python3 has no cpe_band_scan module; the launcher must make its own."""
    launcher = ROOT / "run-cpe-band-scan.command"
    text = launcher.read_text(encoding="utf-8")
    assert "python3 -m venv .venv" in text
    assert ".venv/bin/cpe-band-scan ui" in text
    assert "python3 -m cpe_band_scan" not in text
    assert os.access(launcher, os.X_OK), "double-clicking needs the executable bit"


def test_the_windows_launcher_runs_from_its_own_venv():
    text = (ROOT / "run-cpe-band-scan.bat").read_text(encoding="utf-8")
    assert "python -m venv .venv" in text
    assert ".venv\\Scripts\\cpe-band-scan ui" in text
    assert "python -m cpe_band_scan" not in text


def test_the_readme_never_promises_a_package_that_is_not_published():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "pipx install cpe-band-scan" not in readme
    assert "pip install --user cpe-band-scan" not in readme
    assert "run-cpe-band-scan.command" in readme and "run-cpe-band-scan.bat" in readme


def test_the_launchers_name_the_python_floor_when_install_fails():
    for name in ("run-cpe-band-scan.command", "run-cpe-band-scan.bat"):
        assert "Python 3.10 or newer" in (ROOT / name).read_text(encoding="utf-8"), name
