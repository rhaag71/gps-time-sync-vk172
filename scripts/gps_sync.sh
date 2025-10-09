#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
VENV_DIR="$REPO_DIR/.venv"
PORT="/dev/ttyACM0"
TIMEOUT="60"
WARMUP="2"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found at $VENV_DIR" >&2
  exit 1
fi

source "$VENV_DIR/bin/activate"

BIN="$VENV_DIR/bin/gps-time-sync"
if [[ ! -x "$BIN" ]]; then
  echo "gps-time-sync executable not found at $BIN" >&2
  exit 2
fi

echo "[gps-sync] Using port $PORT (timeout ${TIMEOUT}s, warmup ${WARMUP}s)"
exec "$BIN" --port "$PORT" --timeout "$TIMEOUT" --warmup "$WARMUP"
