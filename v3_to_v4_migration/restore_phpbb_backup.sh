#!/bin/bash
# Restore the phpBB backup into the dev MySQL instance.
# Usage:
#   ./restore_phpbb_backup.sh [target_db] [path_to_sql_gz]
# Defaults:
#   target_db: ascl_phpbb
#   path_to_sql_gz: <repo_root>/db_backups/ascl_phpbb-database-backup-2025.12.02.sql.gz
#
# This mirrors the credential handling used in copy_ascl_database.sh and
# drops/recreates the target database before import.

set -euo pipefail

TARGET_DB="${1:-ascl_phpbb}"
SQL_FILE="${2:-}"

# Default to the backup in db_backups if not specified
if [[ -z "$SQL_FILE" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
  SQL_FILE="$REPO_ROOT/db_backups/ascl_phpbb-database-backup-2025.12.02.sql.gz"
fi

if [[ ! -f "$SQL_FILE" ]]; then
  echo "❌ SQL backup not found: $SQL_FILE" >&2
  echo "Usage: $0 [target_db] /path/to/ascl_phpbb-backup.sql.gz" >&2
  exit 1
fi

echo "Restoring phpBB backup:"
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

# Import the backup (handle gzipped files)
echo "Importing $SQL_FILE into $TARGET_DB..."
if [[ "$SQL_FILE" == *.gz ]]; then
  echo "Detected gzipped file, decompressing on the fly..."
  gunzip -c "$SQL_FILE" | mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 "$TARGET_DB"
else
  mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 "$TARGET_DB" < "$SQL_FILE"
fi

echo "✓ phpBB database restore complete."
echo ""
echo "Database: $TARGET_DB"
echo "Host: 127.0.0.1:3307"
echo ""
echo "Next steps:"
echo "  1. Extract phpBB files: tar -xjf db_backups/ascl_phpBB3_files-2025.12.03-backup.bzip2"
echo "  2. Update phpBB3/config.php with database credentials"
echo "  3. Run phpBB via PHP built-in server or Nginx"
