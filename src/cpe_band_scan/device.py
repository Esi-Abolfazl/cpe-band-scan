"""Which driver may write to this router. The firmware answers, never the model name:
the same box ships with 3.x and 4.x, and the two speak different band-lock APIs."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .router import Router, RouterError


@dataclass(frozen=True)
class Device:
    model: str
    firmware: str
    driver: str
    carrier: str
    plmn: str

    def as_dict(self) -> dict:
        return asdict(self)


def read_carrier(router: Router) -> tuple[str, str]:
    """(name, plmn). Never raises: a nameless carrier is cosmetic, not a failure."""
    try:
        plmn = router.get("net/current-plmn") or {}
    except RouterError:
        return "", ""
    numeric = (plmn.get("Numeric") or "").strip()
    name = (plmn.get("ShortName") or plmn.get("FullName") or numeric or "").strip()
    return name, numeric


def probe(router: Router) -> Device:
    info = router.get("device/information") or {}
    firmware = (info.get("SoftwareVersion") or "").strip()
    if not firmware.startswith("4."):
        raise RouterError("firmware_not_supported", firmware or "unknown")

    switches = router.get("net/net-feature-switch") or {}
    if str(switches.get("lock_freq_switch") or "") != "3":
        raise RouterError("no_band_lock", f"lock_freq_switch={switches.get('lock_freq_switch')!r}")

    try:
        router.get("net/lock-freq")
    except RouterError as error:
        raise RouterError("no_band_lock", error.detail) from error

    carrier, plmn = read_carrier(router)
    return Device(model=(info.get("DeviceName") or "").strip(), firmware=firmware,
                  driver="lockfreq", carrier=carrier, plmn=plmn)
