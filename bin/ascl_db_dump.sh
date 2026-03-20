#!/usr/bin/env bash
#
# ascl_db_dump.sh — Dump the ASCL v4 database for import into another MySQL instance.
#
# Produces a portable dump that:
#   - Includes tables, views, triggers, routines, and events
#   - Strips CREATE DATABASE / USE statements (target DB may have a different name)
#   - Strips DEFINER clauses (views/routines run as the importing user)
#   - Strips MySQL 8.0.16+ DEFAULT ENCRYPTION clause (compat with older parsers)
#   - Optionally rewrites the database name in the dump
#
# Usage:
#   ascl_db_dump.sh                          # dump to stdout
#   ascl_db_dump.sh -o backup.sql            # dump to file
#   ascl_db_dump.sh -o backup.sql -t devascl_db_v4   # rewrite DB name
#   ascl_db_dump.sh -h                       # show help
#
# Source database connection uses ~/.my.cnf [client_ascl_root] and connects
# to 127.0.0.1:3307 by default (Docker dev). Override with environment variables:
#   ASCL_DB_HOST, ASCL_DB_PORT, ASCL_DB_NAME, ASCL_MY_CNF_GROUP
#

set -euo pipefail

# -- Defaults (local Docker dev) --
SOURCE_DB="${ASCL_DB_NAME:-ascl_db_v4}"
DB_HOST="${ASCL_DB_HOST:-127.0.0.1}"
DB_PORT="${ASCL_DB_PORT:-3307}"
MY_CNF_GROUP="${ASCL_MY_CNF_GROUP:-_ascl_root}"

TARGET_DB=""
OUTPUT=""

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Dump the ASCL v4 database in a portable format.

Options:
  -s NAME   Source database name (default: $SOURCE_DB)
  -t NAME   Target database name — rewrite all references in the dump
  -o FILE   Output file (default: stdout)
  -H HOST   MySQL host (default: $DB_HOST)
  -P PORT   MySQL port (default: $DB_PORT)
  -h        Show this help

Examples:
  $(basename "$0") -o ascl_db_v4.sql
  $(basename "$0") -o ascl_cpanel.sql -t devascl_db_v4
EOF
    exit 0
}

while getopts "s:t:o:H:P:h" opt; do
    case $opt in
        s) SOURCE_DB="$OPTARG" ;;
        t) TARGET_DB="$OPTARG" ;;
        o) OUTPUT="$OPTARG" ;;
        H) DB_HOST="$OPTARG" ;;
        P) DB_PORT="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

# -- Extract credentials from ~/.my.cnf group --
# We parse the cnf file directly rather than using --defaults-group-suffix
# because mysqldump also reads [client] which may contain unsupported options
# (e.g. "database=") that cause errors.
MY_CNF="$HOME/.my.cnf"
CNF_SECTION="client${MY_CNF_GROUP}"

parse_cnf() {
    local key="$1"
    awk -v section="[$CNF_SECTION]" -v key="$key" '
        $0 == section { found=1; next }
        /^\[/ { found=0 }
        found && $0 ~ "^"key"=" { sub(/^[^=]+=/, ""); print; exit }
    ' "$MY_CNF"
}

CNF_USER="$(parse_cnf user)"
CNF_PASS="$(parse_cnf password)"

if [[ -z "$CNF_USER" ]]; then
    echo "Error: Could not find user in [$CNF_SECTION] section of $MY_CNF" >&2
    exit 1
fi

# -- Build mysqldump command --
DUMP_CMD=(
    mysqldump
    --no-defaults
    -u "$CNF_USER"
    -h "$DB_HOST"
    -P "$DB_PORT"
    --databases "$SOURCE_DB"
    --routines
    --triggers
    --events
    --single-transaction
    --set-gtid-purged=OFF
)

# Pass password via environment to avoid it appearing in ps output
export MYSQL_PWD="$CNF_PASS"

echo "Dumping ${SOURCE_DB} from ${DB_HOST}:${DB_PORT}..." >&2

# -- Dump and clean --
# 1. Strip CREATE DATABASE / USE lines
# 2. Strip DEFINER clauses (so views/routines use the importing user)
# 3. Strip DEFAULT ENCRYPTION (MySQL 8.0.16+ specific)
# 4. Optionally rewrite database name
CLEAN_SED=(
    -e '/^CREATE DATABASE/d'
    -e '/^USE /d'
    -e 's/ \/\*!80016 DEFAULT ENCRYPTION=.'\''N.'\'' \*\///'
    -e 's/\/\*![0-9]* DEFINER=`[^`]*`@`[^`]*`[^*]*\*\///'
)

# Rewrite database name if target specified
if [[ -n "$TARGET_DB" ]]; then
    CLEAN_SED+=(-e "s/\`${SOURCE_DB}\`/\`${TARGET_DB}\`/g")
    echo "Rewriting database name: ${SOURCE_DB} -> ${TARGET_DB}" >&2
fi

if [[ -n "$OUTPUT" ]]; then
    "${DUMP_CMD[@]}" | sed "${CLEAN_SED[@]}" > "$OUTPUT"
    echo "Dump written to: ${OUTPUT}" >&2
else
    "${DUMP_CMD[@]}" | sed "${CLEAN_SED[@]}"
fi
