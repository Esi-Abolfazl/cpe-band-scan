import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """No test may touch the person's real ~/.cpe-band-scan."""
    monkeypatch.setenv("CPE_BAND_SCAN_HOME", str(tmp_path))
