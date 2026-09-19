#!/bin/sh
# First run: uv builds a private Python environment next to the app and installs into it.
cd "$(dirname "$0")" || exit 1
PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  # this runs before the app's Python exists, so copy.py cannot serve these sentences
  echo "CPE Band Scan needs uv, which sets up everything else for you."
  echo "Install it with:  brew install uv"
  echo "Then double-click this file again."
  exit 1
fi
exec uv run cpe-band-scan ui
