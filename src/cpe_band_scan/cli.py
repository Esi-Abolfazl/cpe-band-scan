"""The terminal front end. It prints what the engine yields and nothing else."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from . import copy, lockfreq, metrics, scanner, store
from .device import probe
from .router import Router, RouterError

DEFAULT_URL = "http://192.168.8.1/"


def parse(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="cpe-band-scan", description=copy.APP["tagline"], add_help=False)
    parser.add_argument("--url", default=os.environ.get("CPE_BAND_SCAN_URL", DEFAULT_URL))
    parser.add_argument("--user", default=os.environ.get("CPE_BAND_SCAN_USER", "admin"))
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
    from_env = os.environ.get("CPE_BAND_SCAN_PASSWORD")
    if from_env:
        return from_env
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "PASSWORD" and value.strip():
                return value.strip().strip("'\"")
    return getpass.getpass(f"{copy.FIELDS['password']['label']}: ")


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
        return copy.text("PROGRESS", "run_start", count=len(event.get("sides", [])))
    if kind == "side_start":
        return copy.text("PROGRESS", "side_start", side=copy.SIDES[event["side"]],
                         count=event["total"], minutes=max(1, round(event["eta_s"] / 60)))
    if kind == "set_start":
        return copy.text("PROGRESS", "set_start", name=event["name"], index=event["index"],
                         total=event["total"], minutes=max(1, round(event["eta_s"] / 60)))
    if kind == "set_result":
        result = event["result"]
        return copy.text("PROGRESS", "set_result", name=event["name"],
                         grade=copy.GRADES[result["grade"]], floor=f"{result['floor']:g}")
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


def results_table(run: dict) -> str:
    """The same columns the page shows, in the same order, in markdown, best first."""
    keys = ("rank", "band", "grade", "five_g", "floor", "sinr", "rsrq", "rsrp", "nr_sinr", "carriers")
    header = [copy.COLUMNS[key]["label"] or "-" for key in keys]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(keys)]
    for side, record in run.get("sides", {}).items():
        for position, name in enumerate(record["order"] + [n for n in record["results"]
                                                           if n not in record["order"]], 1):
            row = record["results"][name]
            lines.append("| " + " | ".join([
                str(position), name, copy.GRADES[row["grade"]], "yes" if row["has5g"] else "no",
                f"{row['floor']:g}", f"{row['sinr']:g}", f"{row['rsrq']:g}", f"{row['rsrp']:g}",
                f"{row['nrsinr']:g}", row["band"],
            ]) + " |")
    return "\n".join(lines)


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
            for event in scanner.scan(router, device, sides=sides, bands=bands or None):
                line = render(event)
                if line:
                    print(f"[{datetime.now():%H:%M:%S}] {line}", flush=True)
                if event["type"] == "done":
                    run = event["run"]
            print("\n" + results_table(run))
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
