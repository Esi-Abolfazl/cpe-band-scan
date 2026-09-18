"""Which driver may write to this router. The lock-freq page answers, never the model name and
never the version string: Huawei ships the same page on 4.x and on the 10.x line, so the version
only picks the wording when the page is missing."""
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


OLD_INTERFACE = ("2.", "3.")   # these drive bands through the mode endpoint this app must never
                               # write: a band list there silently switches 5G off


def _no_lock_page(firmware: str, detail: str) -> RouterError:
    if firmware.startswith(OLD_INTERFACE):
        return RouterError("firmware_not_supported", firmware or "unknown")
    return RouterError("no_band_lock", detail)


def _lock_freq_switch(router: Router) -> str:
    """Diagnostic only, and never raises. `3` is what the H155 web UI sets, but the value differs
    between firmware lines, so it says what the router reported, not whether it can lock."""
    try:
        switches = router.get("net/net-feature-switch") or {}
    except RouterError as error:
        return f"lock_freq_switch unreadable ({error.detail})"
    return f"lock_freq_switch={switches.get('lock_freq_switch')!r}"


def probe(router: Router) -> Device:
    info = router.get("device/information") or {}
    firmware = (info.get("SoftwareVersion") or "").strip()
    model = (info.get("DeviceName") or "").strip()

    try:
        router.get("net/lock-freq")          # the page answering is the capability itself
    except RouterError as error:
        raise _no_lock_page(firmware, f"{model} {firmware}, {_lock_freq_switch(router)}, "
                                      f"{error.detail}") from error

    carrier, plmn = read_carrier(router)
    return Device(model=model, firmware=firmware,
                  driver="lockfreq", carrier=carrier, plmn=plmn)
