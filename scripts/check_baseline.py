"""The ratchet (AGENTS.md § Baseline): a rule the repo violates today may not gain a new hit.

Each counter in gates-baseline.json is a regex over a set of files and the count committed at
adoption. This exits 1 when any count grew, and asks for the file to be lowered when one fell,
so the baseline only ever moves down. `--write` records the current counts.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "gates-baseline.json"


def count(counter: dict) -> int:
    pattern = re.compile(counter["pattern"], re.M)
    files = [path for glob in counter["files"] for path in ROOT.glob(glob) if path.is_file()]
    return sum(len(pattern.findall(path.read_text(encoding="utf-8"))) for path in sorted(files))


def main(argv: list[str]) -> int:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    grew, fell = [], []
    for name, counter in baseline.items():
        now = count(counter)
        if "--write" in argv:
            counter["count"] = now
        elif now > counter["count"]:
            grew.append(f"{name}: {now} > baseline {counter['count']} ({counter['rule']})")
        elif now < counter["count"]:
            fell.append(f"{name}: {now} < baseline {counter['count']} — lower it: uv run scripts/check_baseline.py --write")
    if "--write" in argv:
        BASELINE.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print("check-baseline: written")
        return 0
    for line in grew + fell:
        print(line, file=sys.stderr)
    if grew or fell:
        return 1
    print("check-baseline: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
