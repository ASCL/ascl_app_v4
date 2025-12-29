#!/bin/bash
# Restore the WordPress backup into the dev MySQL instance.
# Usage:
#   ./restore_wordpress_backup.sh [target_db] [path_to_sql]
# Defaults:
#   target_db: ascl_wordpress
#   path_to_sql: <repo_root>/ascl_wordpress-backup_2025.11.29.sql
#
# This mirrors the credential handling used in copy_ascl_database.sh and
# drops/recreates the target database before import.

set -euo pipefail

TARGET_DB="${1:-ascl_wordpress}"
SQL_FILE="${2:-}"

if [[ -z "$SQL_FILE" ]]; then
  echo "Usage: $0 [target_db] /path/to/ascl_wordpress-backup.sql" >&2
  exit 2
fi

if [[ ! -f "$SQL_FILE" ]]; then
  echo "❌ SQL backup not found: $SQL_FILE" >&2
  exit 1
fi

echo "Restoring WordPress backup:"
echo "  Target DB : $TARGET_DB"
echo "  SQL file  : $SQL_FILE"

# Create temporary credentials file from ~/.my.cnf ([client_ascl_root] → [client])
tmp=$(mktemp)
trap "rm -f '$tmp'" EXIT

awk '
  /^\[client_ascl_root\]/ { in_section=1; print "[client]"; next }
  /^\[/ && in_section { exit }
  in_section && !/^database=/ { print }
' ~/.my.cnf > "$tmp"

echo "Using temporary credentials file: $tmp"

# Drop and recreate the target database
echo "Dropping and recreating $TARGET_DB..."
mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 \
  -e "DROP DATABASE IF EXISTS \`$TARGET_DB\`; CREATE DATABASE \`$TARGET_DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Import the backup
echo "Importing $SQL_FILE into $TARGET_DB..."
mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 "$TARGET_DB" < "$SQL_FILE"

echo "✓ Restore complete."
