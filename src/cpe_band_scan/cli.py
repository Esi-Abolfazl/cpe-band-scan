"""The terminal front end. It prints what the engine yields and nothing else."""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime

from . import config, copy, lockfreq, metrics, scanner, speed, store
from .device import probe
from .router import Router, RouterError

def parse(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cpe-band-scan", description=copy.APP["tagline"], add_help=False)
    parser.add_argument("--url", default=config.router_url())
    parser.add_argument("--user", default=config.username())
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("help")
    subparsers.add_parser("status")
    subparsers.add_parser("clear")
    subparsers.add_parser("runs")
    subparsers.add_parser("test")
    ui = subparsers.add_parser("ui")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--no-browser", action="store_true")
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("args", nargs="*", default=[],
                             help="optional 4g or 5g, then any bands to measure")
    scan_parser.add_argument("--save", dest="save_name", default=None)
    scan_parser.add_argument("--no-speed", dest="speed", action="store_false",
                             help="skip the per-band speed and ping probe")
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("bands")
    apply_parser.add_argument("--scell", default="")
    apply_parser.add_argument("--nr", default="")
    show = subparsers.add_parser("show")
    show.add_argument("run_id")
    args = parser.parse_args(argv)
    args.url = args.url if args.url.startswith("http") else f"http://{args.url}/"
    return args


def read_password(args) -> str:
    return config.password() or getpass.getpass(f"{copy.FIELDS['password']['label']}: ")


def connect(args):
    router = Router(args.url, read_password(args), username=args.user)
    return router, probe(router)


def scan_target(args) -> tuple[tuple[str, ...], list[str]]:
    """Which sides to scan and which bands. Bare band numbers are 4G bands; the 5G side is
    scanned only when asked for with `5g`, because N7 for B7 is never what was meant."""
    words = list(args.args)
    side = words.pop(0) if words and words[0] in ("4g", "5g") else None
    if side:
        return {"4g": ("lte",), "5g": ("nr",)}[side], words
    return (("lte",) if words else ("lte", "nr")), words


def render(event) -> str | None:
    kind = event.get("type")
    if kind == "run_start":
        line = copy.text("PROGRESS", "run_start", count=len(event.get("sides", [])))
        if event.get("speed"):
            line += " " + copy.text("NOTES", f"probe_{event['speed']['bypass']}")
        return line
    if kind == "side_start":
        return copy.text("PROGRESS", "side_start", side=copy.SIDES[event["side"]],
                         count=event["total"], minutes=max(1, round(event["eta_s"] / 60)))
    if kind == "set_start":
        return copy.text("PROGRESS", "set_start", name=event["name"], index=event["index"],
                         total=event["total"], minutes=max(1, round(event["eta_s"] / 60)))
    if kind == "set_result":
        result = event["result"]
        reading = result.get("speed") or {}
        if reading and "error" not in reading:
            return copy.text("PROGRESS", "set_result_probe", name=event["name"],
                             grade=copy.GRADES[result["grade"]], floor=f"{event['floor']:g}",
                             mbps=f"{reading['mbps']:g}", ping=reading["latency_ms"])
        return copy.text("PROGRESS", "set_result", name=event["name"],
                         grade=copy.GRADES[result["grade"]], floor=f"{event['floor']:g}")
    if kind == "set_skipped":
        return copy.text("PROGRESS", event["reason"], name=event["name"])
    if kind == "side_done":
        return copy.text("PROGRESS", "side_done", side=copy.SIDES[event["side"]],
                         count=len(event["results"]))
    if kind == "applied":
        return copy.text("PROGRESS", "applied", bands=", ".join(event["plan"]["lte"] + event["plan"]["nr"]))
    if kind in ("kept_auto", "unchanged", "lock_back", "lock_lost"):
        return copy.text("PROGRESS", kind)
    if kind == "cancelled":
        return copy.text("PROGRESS", "cancelled")
    if kind == "trace_start":
        return copy.text("PROGRESS", "trace_start", minutes=round(event["seconds"] / 60))
    if kind == "trace_sample":
        row = event["sample"]
        return f"{event['at_s']:>4}s  {row['band']}  SINR {row['sinr']:g}  RSRQ {row['rsrq']:g}"
    if kind in ("trace_done", "done"):
        return copy.text("PROGRESS", kind if kind == "trace_done" else "done")
    if kind == "error":
        return copy.text("ERRORS", event.get("code", "crash"), detail=event.get("detail", ""))
    return None


BASE_KEYS = ("rank", "band", "grade", "five_g", "floor", "sinr", "rsrq", "rsrp", "nr_sinr", "carriers")
SPEED_KEYS = ("speed", "ping")
SPEED_AT = 4            # after the 5G column; app.js mirrors both of these, test_parity checks it


def shows_speed(run: dict) -> bool:
    """A blocked probe measured no band: its sentence is still said, but no columns are added."""
    report = run.get("speed")
    return bool(report) and report.get("bypass") != "blocked"


def column_keys(run: dict) -> list[str]:
    keys = list(BASE_KEYS)
    if shows_speed(run):
        keys[SPEED_AT:SPEED_AT] = SPEED_KEYS
    return keys


def _cells(position: int, name: str, row: dict) -> dict:
    probe = row.get("speed") or {}
    answered = bool(probe) and "error" not in probe
    return {"rank": str(position), "band": name, "grade": copy.GRADES[row["grade"]],
            "five_g": "yes" if row["has5g"] else "no",
            "speed": f"{probe['mbps']:g}" if answered else copy.NOTES["probe_no_answer"],
            "ping": str(probe["latency_ms"]) if answered else copy.NOTES["probe_no_answer"],
            "floor": f"{row['floor']:g}", "sinr": f"{row['sinr']:g}", "rsrq": f"{row['rsrq']:g}",
            "rsrp": f"{row['rsrp']:g}", "nr_sinr": f"{row['nrsinr']:g}", "carriers": row["band"]}


def results_table(run: dict) -> str:
    """The same columns the page shows, in the same order, in markdown, best first."""
    keys = column_keys(run)
    header = [copy.COLUMNS[key]["label"] or "-" for key in keys]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(keys)]
    for side, record in run.get("sides", {}).items():
        for position, name in enumerate(record["order"] + [n for n in record["results"]
                                                           if n not in record["order"]], 1):
            cells = _cells(position, name, record["results"][name])
            lines.append("| " + " | ".join(cells[key] for key in keys) + " |")
    return "\n".join(lines)


def speed_note(run: dict) -> str:
    """The sentence that says what the speed and ping columns mean, or nothing."""
    report = run.get("speed")
    return copy.text("NOTES", f"probe_{report['bypass']}") if report else ""


def _print_help() -> int:
    print(f"{copy.APP['name']} — {copy.APP['tagline']}\n")
    rows = [("ui", copy.NOTES["ui_command"]),
            ("scan", copy.FIELDS["scan_scope"]["options"]["all"]["help"]),
            ("scan 4g", copy.FIELDS["scan_scope"]["options"]["lte"]["help"]),
            ("scan 5g", copy.FIELDS["scan_scope"]["options"]["nr"]["help"]),
            ("status", copy.NOTES["status_command"]),
            ("test", copy.ACTIONS["test"]["help"]),
            ("apply <bands>", copy.ACTIONS["apply"]["help"]),
            ("clear", copy.ACTIONS["clear"]["help"]),
            ("runs", copy.NOTES["runs_command"]),
            ("show <id>", copy.NOTES["show_command"])]
    width = max(len(name) for name, _ in rows)
    for name, description in rows:
        print(f"  {name:<{width}}  {description}")
    print(f"\n{copy.NOTES['vpn']}\n{copy.NOTES['password_note']}")
    return 0


def main(argv=None) -> int:
    args = parse(argv)
    command = args.command or "help"
    if command == "help":
        return _print_help()
    if command == "ui":
        from .server import serve
        return serve(port=args.port, open_browser=not args.no_browser)
    if command == "runs":
        rows = store.list_runs()
        if not rows:
            print(copy.NOTES["empty_runs"])
        for row in rows:
            print(f"{row['id']}  {row['name']}  ({row['kind']}, best {row['best'] or '-'})")
        return 0
    if command == "show":
        run = store.load(args.run_id)
        print(run["name"])
        print(results_table(run))
        note = speed_note(run)
        if note:
            print(note)
        return 0

    try:
        router, device = connect(args)
        print(f"{device.model} · firmware {device.firmware} · {device.carrier or '-'}")
        if command == "status":
            print(json.dumps({"lock": lockfreq.read_lock(router), "signal": metrics.sample(router),
                              "visible": metrics.visible_bands(router)}, indent=2, default=str))
        elif command == "clear":
            lockfreq.lock(router)
            print(copy.text("ACTIONS", "clear"))
        elif command == "apply":
            lockfreq.lock(router, lte=args.bands.split(","),
                          lte_scell=[b for b in args.scell.split(",") if b],
                          nr=[b for b in args.nr.split(",") if b])
            print(copy.text("PROGRESS", "lock_written", bands=args.bands))
        elif command == "test":
            run = None
            for event in scanner.trace(router):
                line = render(event)
                if line:
                    print(f"[{datetime.now():%H:%M:%S}] {line}", flush=True)
                if event["type"] == "trace_done":
                    run = event["run"]
            saved = store.save(run, name=store.default_name(device.carrier))
            print(copy.text("PROGRESS", "saved", name=saved["name"]))
        elif command == "scan":
            sides, bands = scan_target(args)
            print(copy.NOTES["before_scan"])
            print(copy.NOTES["vpn"])
            run = None
            speed_probe = speed.SpeedProbe(router.url) if args.speed else None
            for event in scanner.scan(router, device, sides=sides, bands=bands or None, probe=speed_probe):
                line = render(event)
                if line:
                    print(f"[{datetime.now():%H:%M:%S}] {line}", flush=True)
                if event["type"] == "done":
                    run = event["run"]
            print("\n" + results_table(run))
            note = speed_note(run)
            if note:
                print(note)
            saved = store.save(run, name=args.save_name or store.default_name(device.carrier))
            print(copy.text("PROGRESS", "saved", name=saved["name"]))
        return 0
    except RouterError as error:
        print(copy.text("ERRORS", error.code, url=args.url, detail=error.detail), file=sys.stderr)
        return 1
    except ValueError as error:
        print(copy.text("ERRORS", "bad_request", detail=str(error)), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(copy.text("PROGRESS", "cancelled"), file=sys.stderr)
        return 130
    except Exception as error:       # the catalogue has a sentence for this; a traceback is not one
        print(copy.text("ERRORS", "crash", detail=repr(error)), file=sys.stderr)
        return 1
