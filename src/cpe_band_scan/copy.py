"""Every word the user reads. One file, so the terminal and the page never drift apart
and a translation is a second dict rather than a rewrite."""

APP = {
    "name": "CPE Band Scan",
    "tagline": "Find the band that gives you the steadiest connection.",
    "connect_heading": "Connect to your router",
    "connect_intro": "CPE Band Scan signs in to your router, measures each band it supports, and locks the "
                     "one that holds up best. Nothing is flashed, and you can switch back to automatic "
                     "at any time.",
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
        "help": "The address of your router's admin page. Most Huawei CPE routers answer at "
                "192.168.8.1, some at 192.168.1.1. If you're not sure, check the label on the router "
                "or open the address in a browser.",
    },
    "password": {
        "label": "Admin password",
        "placeholder": "",
        "help": "The password for the router's admin page, which is usually not your Wi-Fi password. "
                "CPE Band Scan keeps it in memory while it runs, never writes it to disk, and never sends "
                "it anywhere except your own router.",
    },
    "profile_name": {
        "label": "Profile name",
        "placeholder": "MCI — living room",
        "help": "A name you'll recognise later, such as your carrier and where the router is standing. "
                "CPE Band Scan suggests your carrier and today's date.",
    },
    "remember": {
        "label": "Remember the password on this computer",
        "placeholder": "",
        "help": "Saves the admin password in CPE Band Scan's settings file, readable by your user "
                "account only, so you don't type it next time. Anyone who can sign in as you on this "
                "computer can read it. Forget it from the connect screen whenever you like.",
    },
    "scan_scope": {
        "label": "What to scan",
        "placeholder": "",
        "help": "Which bands the scan measures. All bands is the full picture. On a 5G NSA network "
                "the 4G bands decide most, because the 5G carrier follows the 4G band the router is "
                "anchored to.",
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
        "help": "What the test watches. Your current lock is measured as it is. Choosing a band from "
                "the results locks it for the length of the test, then puts your lock back.",
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
        "help": "Longer tests catch the dips a short one misses. Two minutes shows whether a band is "
                "steady; ten minutes is the one to trust before you settle on it.",
        "options": {"1": {"label": "1 min", "help": ""}, "2": {"label": "2 min", "help": ""},
                    "5": {"label": "5 min", "help": ""}, "10": {"label": "10 min", "help": ""}},
    },
    "follow": {
        "label": "Follow",
        "placeholder": "",
        "help": "Keeps the log scrolled to the newest line. Scrolling up switches it off so you can "
                "read; tick it to catch up again.",
    },
}

ACTIONS = {
    "connect": {
        "label": "Connect",
        "help": "Signs in and checks whether this router can lock bands. Nothing on the router changes.",
    },
    "scan": {
        "label": "Start the scan",
        "help": "Locks each band you chose in turn and measures it for about a minute, then ranks "
                "them. Your connection drops for about half a minute every time the band changes.",
    },
    "test": {
        "label": "Start the test",
        "help": "Watches the chosen band for the chosen time and reports the lowest, typical and best "
                "quality it saw. Use it when two bands scored close.",
    },
    "stop_test": {
        "label": "Stop the test",
        "help": "Stops watching. If the test locked a band for you, your own lock is put back.",
    },
    "apply": {
        "label": "Apply",
        "help": "Locks the router to this band and keeps the other working bands as secondary carriers. "
                "The connection drops for about 30 seconds, then comes back. The lock survives a restart.",
    },
    "clear": {
        "label": "Switch back to automatic",
        "help": "Removes the lock so the router picks bands on its own again, the way it arrived.",
    },
    "cancel": {
        "label": "Stop the scan",
        "help": "Stops after the band being measured and puts the router back how it arrived, lock and "
                "all. Everything measured so far is kept.",
    },
    "save_profile": {
        "label": "Save current lock",
        "help": "Stores the lock the router holds right now under a name, so you can apply it again "
                "later: one profile per carrier or per place.",
    },
    "apply_profile": {
        "label": "Apply",
        "help": "Locks the router to this profile's bands. The connection drops for about 30 seconds, "
                "then comes back.",
    },
    "rename_profile": {
        "label": "Rename",
        "help": "Changes the name of a profile. The lock in it stays as it was.",
    },
    "delete_profile": {
        "label": "Delete",
        "help": "Removes this profile from your computer. The router keeps whatever lock it has.",
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
    "band": {"label": "Band", "help": "The band that was locked while this row was measured. "
                                      "'Auto' is what your router chooses on its own, kept for comparison."},
    "grade": {"label": "Rating", "help": "The row in one word, from how far the quality dropped and how "
                                          "clean the channel was. Excellent and Good are safe picks."},
    "floor": {"label": "Lowest", "help": "The lowest SINR during the measurement, in dB. This is "
                                                  "what makes a call or a stream stutter. Above 0 is "
                                                  "usable, above 5 is comfortable."},
    "sinr": {"label": "Typical", "help": "The middle SINR reading of the measurement, in dB. "
                                                  "Higher is better."},
    "rsrq": {"label": "Channel", "help": "RSRQ in dB, how clean the channel is. Better than -12 "
                                                  "is healthy. Worse usually means interference or a busy "
                                                  "cell rather than distance."},
    "rsrp": {"label": "Strength", "help": "RSRP in dBm, the raw strength. Above -90 it barely "
                                                  "affects speed, so a band shouldn't be chosen on this "
                                                  "alone."},
    "nr_sinr": {"label": "5G quality", "help": "SINR of the 5G carrier in dB, when one was connected."},
    "five_g": {"label": "5G", "help": "Whether the 5G carrier stayed up on this band. Bands that lose it "
                                       "are never recommended."},
    "carriers": {"label": "Carriers", "help": "The carriers the router combined on this band. More "
                                               "carriers usually means more speed."},
}

GRADES = {"excellent": "Excellent", "good": "Good", "fair": "Fair", "poor": "Poor",
          "no5g": "Loses 5G"}

SIDES = {"lte": "4G", "nr": "5G", "trace": "test"}

ERRORS = {
    "unreachable": "Can't reach a router at {url}. Either that's not its address, or this computer isn't "
                   "on the router's network. Check the address and try again.",
    "not_huawei_api": "Something answered at {url}, but it isn't a Huawei router. Open that address in a "
                      "browser to see what's there, then enter the right one.",
    "bad_password": "That password didn't work. CPE Band Scan needs the password for the router's "
                    "admin page, which is usually not the Wi-Fi password. Check the label on the "
                    "router and try again.",
    "locked_out": "The router is refusing sign-ins for a few minutes after too many wrong passwords. "
                  "Wait 5 minutes, then try again.",
    "firmware_not_supported": "This router runs firmware {detail}, and CPE Band Scan can only lock "
                              "bands on firmware 4. Older firmware uses a different interface, and "
                              "writing to it blindly can switch 5G off, so CPE Band Scan won't try. "
                              "If this router gets a firmware 4 update later, try again.",
    "no_band_lock": "This router signed in, but it has no band-lock page ({detail}), so CPE Band "
                    "Scan can't change its bands. Check the address if this is not the router you "
                    "meant, and try again after any firmware update.",
    "api_refused": "The router refused the request ({detail}). This is usually temporary. Wait a moment "
                   "and try again.",
    "busy": "A scan is already running. Stop it first, or wait for it to finish.",
    "not_connected": "Not signed in to a router yet. Enter the router address and admin password, "
                     "then connect.",
    "bad_request": "CPE Band Scan got a request it can't act on ({detail}). Check what was sent and "
                   "try again.",
    "crash": "CPE Band Scan stopped on an unexpected problem ({detail}). Check which bands your "
             "router is on before you scan again, and keep this message if it happens twice.",
}

NOTES = {
    "before_scan": "Scanning interrupts your connection. CPE Band Scan locks each band in turn, so the "
                   "internet drops for about 30 seconds every time it moves to the next one. Expect "
                   "20 to 30 minutes in all. You can keep working between the drops.",
    "vpn": "A VPN is fine to keep on. Stay on one server for the whole scan, because switching servers "
           "mid-run changes what you feel while the measurements stay the same. If CPE Band Scan can't reach "
           "the router while the VPN is up, switch on your VPN's local network access setting.",
    "password_note": "Unless you tick Remember, the password stays in memory while CPE Band Scan runs "
                     "and is never saved. Change it afterwards if someone else may have seen it.",
    "password_remembered": "The password is remembered on this computer.",
    "lock_survives": "The lock stays in place after a restart. Switch back to automatic whenever you want.",
    "rescan_hint": "Scan again after you move the router, change SIM, or change provider.",
    "empty_runs": "No saved results yet. Finish a scan and it'll be here to compare against.",
    "empty_profiles": "No profiles yet. Once the router holds a lock you like, save it here under a name "
                      "and apply it again after you move or change carrier.",
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
    "set_result": "{name} scored {grade}, lowest quality {floor} dB.",
    "no_service": "{name} has no service here, so it was skipped.",
    "refused": "{name} was refused by the router, so it was skipped.",
    "side_done": "Finished the {side} bands: {count} measured.",
    "applied": "Locked to {bands}. Your connection is back.",
    "lock_written": "Locked to {bands}. The connection drops for about 30 seconds while the router "
                    "re-attaches, then comes back.",
    "kept_auto": "Automatic held up better than any single band, so nothing was locked.",
    "unchanged": "No band did better than what you already had, so nothing was changed.",
    "cancelled": "Stopped, so nothing more will be measured.",
    "lock_back": "The band lock you had before the scan is back. Nothing else changed.",
    "lock_lost": "The band lock you had couldn't be put back, so the router is choosing bands on "
                 "its own. Pick a band from the results to lock it again.",
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
