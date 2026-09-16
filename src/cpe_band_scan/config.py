"""Every environment variable the app reads, read here and nowhere else. Read at call time,
never at import, so a test's CPE_BAND_SCAN_HOME takes effect."""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_URL = "http://192.168.8.1/"


def home() -> Path:
    return Path(os.environ.get("CPE_BAND_SCAN_HOME") or Path.home() / ".cpe-band-scan")


def router_url() -> str:
    return os.environ.get("CPE_BAND_SCAN_URL", DEFAULT_URL)


def username() -> str:
    return os.environ.get("CPE_BAND_SCAN_USER", "admin")


def password() -> str | None:
    """CPE_BAND_SCAN_PASSWORD, else a PASSWORD= line in ./.env, else None (the caller prompts)."""
    from_env = os.environ.get("CPE_BAND_SCAN_PASSWORD")
    if from_env:
        return from_env
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "PASSWORD" and value.strip():
                return value.strip().strip("'\"")
    return None
