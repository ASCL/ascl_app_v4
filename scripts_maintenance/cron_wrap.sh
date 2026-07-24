#!/usr/bin/env bash
#
# cron_wrap.sh — Run a maintenance job under cron and keep a rolling log of it.
#
# Wraps any command so that every scheduled run leaves a trace, whether or not
# the command itself ever starts. This matters: the common cron failure is that
# the interpreter is not on cron's minimal PATH, so the Python script never runs
# and therefore cannot log anything about itself. The wrapper is shell, runs
# first, and records that case too.
#
# Usage:
#   cron_wrap.sh JOB_NAME COMMAND [ARGS...]
#
# Example crontab:
#   PATH=/usr/local/bin:/usr/bin:/bin
#   SCRIPTS=/itss/home/ascl/repositories/ascl_app_v4/scripts_maintenance
#   PY=/itss/home/ascl/venv/bin/python3
#   0 3 * * 2,5 $SCRIPTS/cron_wrap.sh link-check $PY $SCRIPTS/link_checker_async.py
#
# Output:
#   cron_history.log   one START and one END line per run — the "did it run?" file
#   <job>.log          full stdout/stderr of each run, with a per-run banner
#
# Quiet on success, loud on failure: a failed run prints a summary and the tail
# of its output to stderr, so cron still sends its usual MAILTO email. A
# successful run prints nothing and sends no mail.
#
# Environment overrides:
#   ASCL_CRON_LOG_DIR        log directory (default: <this script's dir>/logs)
#   ASCL_CRON_LOG_MAX_BYTES  rotate a log once it exceeds this (default: 5242880)
#   ASCL_CRON_LOG_KEEP       rotations to retain (default: 5)
#   ASCL_CRON_FAIL_LINES     lines of output to email on failure (default: 40)
#   ASCL_CRON_NO_LOCK        set to 1 to allow overlapping runs of the same job
#

set -uo pipefail

# Logs live beside this script, not under $HOME, so they stay with the checkout
# they belong to. Resolved from BASH_SOURCE rather than $PWD because cron runs
# jobs from the home directory regardless of where the script lives.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

LOG_DIR="${ASCL_CRON_LOG_DIR:-$SCRIPT_DIR/logs}"
MAX_BYTES="${ASCL_CRON_LOG_MAX_BYTES:-5242880}"
KEEP="${ASCL_CRON_LOG_KEEP:-5}"
FAIL_LINES="${ASCL_CRON_FAIL_LINES:-40}"

if [[ $# -lt 2 ]]; then
    echo "Usage: $(basename "$0") JOB_NAME COMMAND [ARGS...]" >&2
    exit 2
fi

JOB_NAME="$1"
shift

# -- Log setup --------------------------------------------------------------

if ! mkdir -p "$LOG_DIR"; then
    echo "cron_wrap: cannot create log directory $LOG_DIR" >&2
    exit 2
fi

HISTORY_LOG="$LOG_DIR/cron_history.log"
JOB_LOG="$LOG_DIR/${JOB_NAME}.log"

# Rotate FILE to FILE.1 (and shift existing rotations down) once it grows past
# MAX_BYTES. Size-based rather than time-based so a chatty job cannot fill the
# disk between runs.
rotate() {
    local file="$1" size=0 i

    [[ -f "$file" ]] || return 0

    size=$(wc -c < "$file" 2>/dev/null || echo 0)
    (( size > MAX_BYTES )) || return 0

    for (( i = KEEP - 1; i >= 1; i-- )); do
        [[ -f "$file.$i" ]] && mv -f "$file.$i" "$file.$((i + 1))"
    done
    mv -f "$file" "$file.1"

    # Drop anything past the retention window.
    for (( i = KEEP + 1; i <= KEEP + 10; i++ )); do
        [[ -f "$file.$i" ]] && rm -f "$file.$i"
    done
    return 0
}

rotate "$HISTORY_LOG"
rotate "$JOB_LOG"

history_line() {
    printf '%s  %-14s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$JOB_NAME" "$*" \
        >> "$HISTORY_LOG"
}

# -- Resolve the command ----------------------------------------------------
# Reported explicitly because "which python did cron actually use?" is the
# question this wrapper exists to answer.

COMMAND="$1"
RESOLVED="$(command -v "$COMMAND" 2>/dev/null || true)"

if [[ -z "$RESOLVED" ]]; then
    history_line "FAIL   command not found: $COMMAND"
    {
        echo "cron_wrap: job '$JOB_NAME' could not start."
        echo "  command not found: $COMMAND"
        echo "  PATH=$PATH"
        echo "  Set PATH (and an absolute interpreter path) in the crontab —"
        echo "  cron does not read your shell profile."
    } >&2
    exit 127
fi

# -- Single-instance lock ---------------------------------------------------
# The link checker can outlive its schedule interval; overlapping runs would
# fight over the same rows. Skipped silently if flock is unavailable.

LOCK_FILE="$LOG_DIR/.${JOB_NAME}.lock"

if [[ "${ASCL_CRON_NO_LOCK:-0}" != "1" ]] && command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK_FILE"
    if ! flock -n 9; then
        history_line "SKIP   previous run still in progress"
        exit 0
    fi
fi

# -- Run --------------------------------------------------------------------

START_EPOCH=$(date '+%s')
START_HUMAN=$(date '+%Y-%m-%d %H:%M:%S')

history_line "START  $RESOLVED $(printf '%s ' "${@:2}")"

{
    echo
    echo "=============================================================="
    echo "job     : $JOB_NAME"
    echo "started : $START_HUMAN"
    echo "host    : $(hostname 2>/dev/null || echo unknown)"
    echo "user    : $(id -un 2>/dev/null || echo unknown)"
    echo "cwd     : $PWD"
    echo "command : $RESOLVED ${*:2}"
    echo "version : $("$RESOLVED" --version 2>&1 | head -1 || echo 'n/a')"
    echo "=============================================================="
} >> "$JOB_LOG"

# Merge stdout and stderr into the job log. Output is captured, not passed
# through, so a successful run generates no cron mail.
"$@" >> "$JOB_LOG" 2>&1
EXIT_CODE=$?

END_EPOCH=$(date '+%s')
DURATION=$(( END_EPOCH - START_EPOCH ))

{
    echo "-- finished $(date '+%Y-%m-%d %H:%M:%S') exit=$EXIT_CODE duration=${DURATION}s"
} >> "$JOB_LOG"

if [[ $EXIT_CODE -eq 0 ]]; then
    history_line "OK     exit=0 duration=${DURATION}s"
else
    history_line "FAIL   exit=$EXIT_CODE duration=${DURATION}s"
    {
        echo "cron_wrap: job '$JOB_NAME' failed with exit code $EXIT_CODE after ${DURATION}s."
        echo "  command : $RESOLVED ${*:2}"
        echo "  log     : $JOB_LOG"
        echo
        echo "  --- last $FAIL_LINES lines ---"
        tail -n "$FAIL_LINES" "$JOB_LOG"
    } >&2
fi

exit $EXIT_CODE
