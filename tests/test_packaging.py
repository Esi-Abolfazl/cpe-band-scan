import os
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
PIP_ERA = ("pip install", "pipx", "python -m venv", "python3 -m venv")


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
    for needed in ("uv sync", "cpe-band-scan ui", "192.168.8.1", "192.168.1.1"):
        assert needed in readme


def test_the_skill_never_recommends_the_password_on_the_command_line():
    skill = (ROOT / "skills" / "bandscan" / "SKILL.md").read_text(encoding="utf-8")
    assert "--password" not in skill


def test_the_mac_launcher_runs_through_uv_and_is_executable():
    """The system python3 has no cpe_band_scan module; uv run builds the app's own environment."""
    launcher = ROOT / "Run on Mac.command"
    text = launcher.read_text(encoding="utf-8")
    assert "uv run cpe-band-scan ui" in text
    assert not [s for s in PIP_ERA if s in text]
    assert "python3 -m cpe_band_scan" not in text
    assert os.access(launcher, os.X_OK), "double-clicking needs the executable bit"


def test_the_windows_launcher_runs_through_uv():
    text = (ROOT / "Run on Windows.bat").read_text(encoding="utf-8")
    assert "uv run cpe-band-scan ui" in text
    assert not [s for s in PIP_ERA if s in text]
    assert "python -m cpe_band_scan" not in text


def test_the_readme_and_skill_never_promise_a_package_that_is_not_published():
    """Until the name is on PyPI, the two docs people install from point at this folder.

    The design spec's naming table is deliberately out of scope: it records the command
    the name will take once published.
    """
    for rel in ("README.md", "skills/bandscan/SKILL.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        for promise in (
            "uv tool install cpe-band-scan",
            "uvx cpe-band-scan",
            "pipx install cpe-band-scan",
            "pip install --user cpe-band-scan",
        ):
            assert promise not in text, f"{rel}: {promise}"
        if rel == "README.md":
            assert "Run on Mac" in text and "Run on Windows" in text


def test_ci_runs_the_gates_agents_md_lists_verbatim():
    """ci.yml claims these lines are AGENTS.md Gates verbatim; that is the claim under test."""
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    block = agents.split("## Gates", 1)[1].split("```")[1]
    gates = [line for line in block.splitlines() if line.strip()]

    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    after = ci.split("# The three lines below are AGENTS.md § Gates, verbatim.", 1)[1]
    runs = [
        line.strip().removeprefix("- run: ")
        for line in after.splitlines()
        if line.strip().startswith("- run: ")
    ]
    assert runs == gates


def test_the_launchers_name_the_one_thing_to_install_when_uv_is_missing():
    """uv fetches Python itself, so uv is the only prerequisite left to name."""
    for name, install in (
        ("Run on Mac.command", "brew install uv"),
        ("Run on Windows.bat", "winget install astral-sh.uv"),
    ):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "needs uv" in text, name
        assert install in text, name


def test_the_package_init_re_exports_nothing():
    assert (ROOT / "src" / "cpe_band_scan" / "__init__.py").read_text(encoding="utf-8").strip() == ""


def test_local_credential_files_are_ignored_and_a_sanitized_example_is_not():
    """config.password() and the README read PASSWORD= from ./.env; nothing stopped a commit of it."""
    def ignored(name):
        return subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT, check=False).returncode == 0
    assert ignored(".env") and ignored(".env.local")
    assert not ignored(".env.example")
