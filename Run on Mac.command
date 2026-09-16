#!/bin/sh
# First run: make a private Python environment next to the app and install into it.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/cpe-band-scan ]; then
  # this runs before Python exists, so copy.py cannot serve this sentence
  python3 -m venv .venv && .venv/bin/pip install -q . || {
    echo "CPE Band Scan needs Python 3.10 or newer. Install it from python.org, then double-click again."; exit 1; }
fi
exec .venv/bin/cpe-band-scan ui
