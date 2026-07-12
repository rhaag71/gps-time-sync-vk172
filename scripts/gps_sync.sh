#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
VENV_DIR="$REPO_DIR/.venv"

PORT="${GPS_PORT-/dev/ttyACM0}"
BAUDRATE="${GPS_BAUDRATE-9600}"
TIMEOUT="${GPS_TIMEOUT-60}"
WARMUP="${GPS_WARMUP-2}"
STATUS_WINDOW="${GPS_STATUS_WINDOW-2}"
STATUS=false
NO_SET=false
VERBOSE=false

usage() {
  cat <<'EOF'
Usage: gps_sync.sh [OPTIONS]

Run the repository virtual environment's gps-time-sync command.

Options:
  --port PATH              GPS device path (default: /dev/ttyACM0)
  --baudrate RATE          Positive integer baud rate (default: 9600)
  --timeout SECONDS        Non-negative acquisition timeout (default: 60)
  --warmup SECONDS         Non-negative serial warmup (default: 2)
  --status-window SECONDS  Non-negative post-fix status window (default: 2)
  --status                 Display detailed status without setting the clock
  --no-set                 Display GPS time without setting the clock
  --verbose                Enable verbose CLI logging
  --help                   Show this help and exit

Environment overrides:
  GPS_PORT                 GPS device path
  GPS_BAUDRATE             Baud rate
  GPS_TIMEOUT              Acquisition timeout
  GPS_WARMUP               Serial warmup
  GPS_STATUS_WINDOW        Post-fix status collection window

Precedence: command-line options > environment variables > built-in defaults.
EOF
}

die() {
  echo "gps_sync.sh: $*" >&2
  exit 64
}

option_value() {
  local option="$1"
  local value="${2-}"
  [[ -n "$value" && "$value" != --* ]] || die "$option requires a value"
  printf '%s' "$value"
}

is_non_negative_number() {
  [[ "$1" =~ ^([0-9]+([.][0-9]*)?|[.][0-9]+)$ ]]
}

while (($# > 0)); do
  case "$1" in
    --port)
      PORT="$(option_value "$1" "${2-}")"
      shift 2
      ;;
    --baudrate)
      BAUDRATE="$(option_value "$1" "${2-}")"
      shift 2
      ;;
    --timeout)
      TIMEOUT="$(option_value "$1" "${2-}")"
      shift 2
      ;;
    --warmup)
      WARMUP="$(option_value "$1" "${2-}")"
      shift 2
      ;;
    --status-window)
      STATUS_WINDOW="$(option_value "$1" "${2-}")"
      shift 2
      ;;
    --status)
      STATUS=true
      shift
      ;;
    --no-set)
      NO_SET=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
done

[[ "$BAUDRATE" =~ ^[0-9]+$ && ! "$BAUDRATE" =~ ^0+$ ]] \
  || die "baud rate must be a positive integer: $BAUDRATE"
is_non_negative_number "$TIMEOUT" \
  || die "timeout must be a non-negative number: $TIMEOUT"
is_non_negative_number "$WARMUP" \
  || die "warmup must be a non-negative number: $WARMUP"
is_non_negative_number "$STATUS_WINDOW" \
  || die "status window must be a non-negative number: $STATUS_WINDOW"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "Virtual environment not found at $VENV_DIR" >&2
  exit 1
fi

BIN="$VENV_DIR/bin/gps-time-sync"
if [[ ! -x "$BIN" ]]; then
  echo "gps-time-sync executable not found at $BIN" >&2
  exit 2
fi

args=(
  --port "$PORT"
  --baudrate "$BAUDRATE"
  --timeout "$TIMEOUT"
  --warmup "$WARMUP"
  --status-window "$STATUS_WINDOW"
)

$STATUS && args+=(--status)
$NO_SET && args+=(--no-set)
$VERBOSE && args+=(--verbose)

echo "[gps-sync] Using port $PORT (baud $BAUDRATE, timeout ${TIMEOUT}s, warmup ${WARMUP}s, status window ${STATUS_WINDOW}s)"
exec "$BIN" "${args[@]}"
