"""Every word the user reads. One file, so the terminal and the page never drift apart
and a translation is a second dict rather than a rewrite."""

APP = {
    "name": "CPE Band Scan",
    "tagline": "Find the band that gives you the steadiest connection.",
    "connect_heading": "Connect to your router",
    "connect_intro": "Measures every band your router supports and locks the steadiest one. Nothing is flashed.",
    "status_heading": "Your connection now",
    "results_heading": "Band results, best first",
    "profiles_heading": "Lock profiles",
    "test_heading": "Test a band without scanning",
    "lock_heading": "Band lock",
    "scan_heading": "Scan",
    "progress_heading": "Scan progress",
    "results_side_heading": "{side} results, best first",
    "log_heading": "{side} log",
}

FIELDS = {
    "router_url": {
        "label": "Router address",
        "placeholder": "192.168.8.1",
        "help": "Usually 192.168.8.1 or 192.168.1.1. It's on the router's label.",
    },
    "username": {
        "label": "Admin username",
        "placeholder": "admin",
        "help": "A router whose login page asks only for a password still signs in as admin.",
    },
    "password": {
        "label": "Admin password",
        "placeholder": "",
        "help": "The router admin password, not the Wi-Fi one.",
    },
    "profile_name": {
        "label": "Profile name",
        "placeholder": "MCI — living room",
        "help": "Carrier and place, so you find it later.",
    },
    "remember": {
        "label": "Remember the password on this computer",
        "placeholder": "",
        "help": "Saved on this computer for your user account only. Forget it any time.",
    },
    "scan_scope": {
        "label": "What to scan",
        "placeholder": "",
        "help": "All bands is the full picture. On 5G NSA the 4G bands decide most.",
        "options": {
            "all": {"label": "All bands",
                    "help": "Every 4G band, then every 5G band. Takes 20 to 30 minutes."},
            "lte": {"label": "4G bands only",
                    "help": "The 4G bands. On a 5G NSA network this is the scan that matters, because "
                            "the 5G carrier follows whichever 4G band the router is anchored to. "
                            "Takes 10 to 15 minutes."},
            "nr": {"label": "5G bands only",
                   "help": "The 5G bands. Useful to see which 5G bands are on air here. Takes 5 to "
                           "10 minutes."},
        },
    },
    "test_target": {
        "label": "Band to test",
        "placeholder": "",
        "help": "A pick is locked for the test only. Your lock comes back after.",
        "options": {
            "current": {"label": "What you're on now",
                        "help": "Watches the connection as it is. Nothing on the router changes."},
            "pick": {"label": "Bands from the results",
                     "help": "Locks the chosen 4G and 5G bands for the test only, together. Your "
                             "connection drops for about 30 seconds at the start and again at the end."},
        },
    },
    "test_minutes": {
        "label": "How long",
        "placeholder": "",
        "help": "Two minutes shows if it's steady. Ten is the one to trust.",
        "options": {"1": {"label": "1 min", "help": ""}, "2": {"label": "2 min", "help": ""},
                    "5": {"label": "5 min", "help": ""}, "10": {"label": "10 min", "help": ""}},
    },
    "follow": {
        "label": "Follow",
        "placeholder": "",
        "help": "Keeps the newest line in view. Scrolling up pauses it.",
    },
    "speed_test": {
        "label": "Measure speed and ping on each band",
        "placeholder": "",
        "help": "Adds about 10 seconds and downloads up to 50 MB of mobile data per band. Goes around "
                "your VPN, so the numbers are the band's, not the VPN's.",
    },
}

ACTIONS = {
    "connect": {
        "label": "Connect",
        "help": "Signs in and checks whether this router can lock bands. Nothing on the router changes.",
    },
    "scan": {
        "label": "Start the scan",
        "help": "Locks each band for about a minute and ranks them. Internet drops at every change.",
    },
    "test": {
        "label": "Start the test",
        "help": "Watches one band and reports its lowest, typical and best quality.",
    },
    "stop_test": {
        "label": "Stop the test",
        "help": "Stops watching. If the test locked a band for you, your own lock is put back.",
    },
    "apply": {
        "label": "Apply",
        "help": "Locks this band. Internet drops for about 30 seconds.",
    },
    "clear": {
        "label": "Switch back to automatic",
        "help": "Removes the lock so the router picks bands on its own again, the way it arrived.",
    },
    "cancel": {
        "label": "Stop the scan",
        "help": "Stops after this band and puts your lock back. Results so far are kept.",
    },
    "save_profile": {
        "label": "Save current lock",
        "help": "Saves the current lock under a name.",
    },
    "apply_profile": {
        "label": "Apply",
        "help": "Locks these bands. Internet drops for about 30 seconds.",
    },
    "rename_profile": {
        "label": "Rename",
        "help": "Changes the name of a profile. The lock in it stays as it was.",
    },
    "delete_profile": {
        "label": "Delete",
        "help": "Removes this profile from your computer. The router keeps whatever lock it has.",
    },
    "confirm_delete": {
        "label": "Delete now",
        "help": "Second press. The profile is gone for good.",
    },
    "save_name": {
        "label": "Save name",
        "help": "Keeps the new name.",
    },
    "cancel_rename": {
        "label": "Cancel",
        "help": "Keeps the old name.",
    },
    "forget": {
        "label": "Forget the password",
        "help": "Removes the remembered password from this computer. You'll type it next time.",
    },
    "refresh": {
        "label": "Refresh",
        "help": "Reads the signal from the router again.",
    },
}

COLUMNS = {
    "rank": {"label": "#", "help": "Position in the ranking. The top row held the steadiest signal."},
    "band": {"label": "Band", "help": "The band that was locked. Auto is the router's own choice."},
    "grade": {"label": "Rating", "help": "Excellent and Good are safe picks."},
    "floor": {"label": "Lowest", "help": "Lowest SINR seen, in dB. Above 0 usable, above 5 comfortable."},
    "sinr": {"label": "Typical", "help": "The middle SINR reading of the measurement, in dB. "
                                                  "Higher is better."},
    "rsrq": {"label": "Channel", "help": "RSRQ in dB. Better than -12 is healthy."},
    "rsrp": {"label": "Strength", "help": "RSRP in dBm. Above -90 it barely matters."},
    "nr_sinr": {"label": "5G quality", "help": "SINR of the 5G carrier in dB, when one was connected."},
    "five_g": {"label": "5G", "help": "Whether the 5G carrier stayed up on this band. Bands that lose it "
                                       "are never recommended."},
    "carriers": {"label": "Carriers", "help": "The carriers the router combined on this band. More "
                                               "carriers usually means more speed."},
    "speed": {"label": "Speed", "help": "Download in Mbit/s over 5 seconds, straight through the router. "
                                         "One moment's reading: cell load changes it hour to hour."},
    "ping": {"label": "Ping", "help": "Time to reach the internet in ms, the middle of 5 tries. Under 50 "
                                       "feels instant, over 150 you notice."},
}

GRADES = {"excellent": "Excellent", "good": "Good", "fair": "Fair", "poor": "Poor",
          "no5g": "No 5G"}

SIDES = {"lte": "4G", "nr": "5G", "trace": "test"}

ERRORS = {
    "unreachable": "No router answers at {url}. Check the address and that you're on its network.",
    "not_huawei_api": "{url} answers, but it isn't a Huawei router. Check the address.",
    "bad_password": "The router rejected this login ({detail}). Check the admin username and password.",
    "no_password": "No admin password was given. Enter the router admin password, then connect.",
    "locked_out": "Too many wrong passwords. Wait 5 minutes, then try again.",
    "firmware_not_supported": "Firmware {detail} locks bands through an older interface this app "
                              "doesn't write. Check whether the router has an update.",
    "no_band_lock": "This router has no band-lock page ({detail}). Check the address.",
    "api_refused": "The router refused the request ({detail}). This is usually temporary. Wait a moment "
                   "and try again.",
    "busy": "A scan is already running. Stop it first, or wait for it to finish.",
    "not_connected": "Not signed in to a router yet. Enter the router address and admin password, "
                     "then connect.",
    "bad_request": "CPE Band Scan got a request it can't act on ({detail}). Check what was sent and "
                   "try again.",
    "crash": "Stopped on an unexpected problem ({detail}). Check your bands before scanning again.",
    "run_not_found": "There's no saved run {detail}. List the saved ones with `cpe-band-scan runs`.",
    "store_unreadable": "Can't read {detail}, so it was left untouched. Fix or remove that file, then "
                        "try again.",
}

NOTES = {
    "before_scan": "Internet drops for about 30 seconds at every band. Expect 20 to 30 minutes.",
    "vpn": "A VPN is fine. Stay on one server for the whole scan.",
    "probe_not_needed": "No VPN was active, so speed and ping are your plain connection.",
    "probe_confirmed": "Speed and ping were measured straight through the router, past your VPN, so "
                       "they are the band's own numbers.",
    "probe_failed": "Your VPN couldn't be bypassed, so speed and ping include it. Compare rows with "
                    "each other, not with other scans.",
    "probe_blocked": "Your VPN blocks everything outside its tunnel, so speed and ping weren't measured. "
                     "Allow local network access in the VPN's settings, or scan with the speed test "
                     "unticked.",
    "probe_no_answer": "no answer",
    "username_note": "Leave this as admin. Change it only if your router has its own username box "
                     "and a different name in it.",
    "password_note": "Kept in memory only, unless you tick Remember.",
    "password_remembered": "The password is remembered on this computer.",
    "lock_survives": "The lock stays in place after a restart. Switch back to automatic whenever you want.",
    "rescan_hint": "Scan again after you move the router, change SIM, or change provider.",
    "empty_runs": "No saved results yet. Finish a scan and it'll be here to compare against.",
    "empty_profiles": "No profiles yet. Save a lock you like and apply it later.",
    "show_command": "Shows the full table and details of a saved run.",
    "profile_auto": "Automatic on both sides",
    "empty_results": "No results yet. Start a scan to fill this table.",
    "auto_row": "Auto is what your router chose by itself, measured the same way for comparison.",
    "no_lock": "No band lock. The router is choosing bands by itself.",
    "locked_to": "Locked to {bands}",
    "with_secondary": "with {bands} as secondary carriers",
    "applying": "Applying…",
    "in_use": "In use",
    "best": "Best",
    "quality": "Quality",
    "channel": "Channel",
    "strength": "Strength",
    "no_5g_carrier": "No 5G carrier right now.",
    "no_lte_carrier": "No 4G carrier right now.",
    "width_mhz": "{width} MHz",
    "side_waiting": "waiting",
    "side_running": "{index} of {total} · about {minutes} min left",
    "side_done": "done",
    "side_skipped": "not scanned",
    "side_stopped": "stopped",
    "log_waits": "Starts after the 4G bands.",
    "no_results_to_pick": "Run a scan first; then the bands it measured can be picked here.",
    "test_running": "Testing {what} · {left} left",
    "test_target_current": "your connection as it is",
    "keep_side": "{side}: keep as it is",
    "side_auto": "{side}: automatic",
    "test_plan": "The test locks {bands}, then puts your own lock back.",
    "ui_command": "Opens the app in your browser, where the same scan, table and test are "
                  "buttons instead of commands.",
    "runs_command": "Lists the scans and tests you have saved on this computer, newest first.",
    "status_command": "Shows what you're connected to right now: the router, the bands in use, "
                      "and the signal quality, without changing anything.",
}

PROGRESS = {
    "run_start": "Starting. CPE Band Scan measures one band at a time and ranks them at the end.",
    "side_start": "Measuring the {side} bands: {count} to go, about {minutes} min left.",
    "set_start": "Measuring {name}, {index} of {total}. About {minutes} min left.",
    "log_measuring": "Measuring {name}",
    "log_result": "{name}: {grade}, lowest {floor} dB",
    "log_result_probe": "{name}: {grade}, lowest {floor} dB, {mbps} Mbit/s, {ping} ms",
    "log_skipped": "{name}: skipped",
    "log_refused": "{name}: refused",
    "set_result": "{name} scored {grade}, lowest quality {floor} dB.",
    "set_result_probe": "{name} scored {grade}, lowest quality {floor} dB, {mbps} Mbit/s, {ping} ms ping.",
    "no_service": "{name} has no service here, so it was skipped.",
    "refused": "{name} was refused by the router, so it was skipped.",
    "side_done": "Finished the {side} bands: {count} measured.",
    "applied": "Locked to {bands}. Your connection is back.",
    "lock_written": "Locked to {bands}. Internet drops for about 30 seconds.",
    "kept_auto": "Automatic held up better than any single band, so nothing was locked.",
    "unchanged": "No band did better than what you already had, so nothing was changed.",
    "cancelled": "Stopped, so nothing more will be measured.",
    "lock_back": "The band lock you had before the scan is back. Nothing else changed.",
    "lock_lost": "Your old lock couldn't be put back. The router is on automatic. Apply a band to lock again.",
    "trace_start": "Watching your connection as it is for {minutes} min. Nothing changes while this runs.",
    "trace_start_locked": "Locked to {name} for a {minutes} min test. Your own lock comes back when it ends.",
    "trace_done": "Test finished.",
    "done": "Scan finished.",
    "saved": "Saved as {name}.",
}

_GROUPS = {"APP": APP, "FIELDS": FIELDS, "ACTIONS": ACTIONS, "COLUMNS": COLUMNS, "GRADES": GRADES,
           "SIDES": SIDES, "ERRORS": ERRORS, "NOTES": NOTES, "PROGRESS": PROGRESS}


class _Blank(dict):
    def __missing__(self, key):
        return ""


def text(group: str, key: str, **fields) -> str:
    """A string with its placeholders filled. A missing placeholder empties out rather than
    raising: a half-filled sentence still helps, a traceback does not."""
    value = _GROUPS[group].get(key, "")
    if isinstance(value, dict):
        value = value.get("label", "")
    return value.format_map(_Blank(fields))


def bundle() -> dict:
    """Everything the page needs, injected into it at load time."""
    return {name: group for name, group in _GROUPS.items()}
