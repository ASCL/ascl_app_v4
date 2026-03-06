#!/bin/bash
# Script to copy ascl_db to ascl_db_v4
# This script works around the mysqldump issue with 'database=' in ~/.my.cnf
# It also excludes legacy tables that should not be migrated to v4.
#
# Usage: ./copy_ascl_database.sh [source_db] [target_db]
# Default: ./copy_ascl_database.sh ascl_db ascl_db_v4

set -e  # Exit on error

SOURCE_DB="${1:-ascl_db}"
TARGET_DB="${2:-ascl_db_v4}"

echo "Copying $SOURCE_DB to $TARGET_DB..."

# Legacy tables to exclude from the copy
LEGACY_TABLES=(
  "ascl_for_zenodo_matching_two"
  "ascl_for_zenodo_matching2"
  "ads_entries"
  "codes_backup2"
  "classic_citations"
  "citations_new"
  "links"
)

# Create temporary credentials file
# We manually extract the [client_ascl_root] section, rename to [client], and remove database= line
tmp=$(mktemp)
trap "rm -f '$tmp'" EXIT  # Clean up temp file on exit

# Extract credentials from ~/.my.cnf
# Find the [client_ascl_root] section and copy until the next section
awk '
  /^\[client_ascl_root\]/ { in_section=1; print "[client]"; next }
  /^\[/ && in_section { exit }
  in_section && !/^database=/ { print }
' ~/.my.cnf > "$tmp"

echo "Created temporary credentials file"

# Note: The --protocol=TCP --host=127.0.0.1 --port=3307 flags can be omitted
# if they are already contained in the temporary defaults file

# Drop and recreate target database
echo "Dropping and recreating $TARGET_DB..."
mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 \
  -e "DROP DATABASE IF EXISTS $TARGET_DB; CREATE DATABASE $TARGET_DB;"

# Build mysqldump ignore-table flags
IGNORE_FLAGS=()
for tbl in "${LEGACY_TABLES[@]}"; do
  IGNORE_FLAGS+=(--ignore-table="$SOURCE_DB.$tbl")
done

# Copy database
echo "Copying data from $SOURCE_DB to $TARGET_DB (excluding legacy tables)..."
mysqldump --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 "${IGNORE_FLAGS[@]}" "$SOURCE_DB" \
  | mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 "$TARGET_DB"

echo "✓ Database copy completed successfully!"
echo "✓ Copied $SOURCE_DB → $TARGET_DB"

# Verify
echo ""
echo "Verifying table count..."
TABLE_COUNT=$(mysql --defaults-file="$tmp" --protocol=TCP --host=127.0.0.1 --port=3307 \
  -D "$TARGET_DB" -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$TARGET_DB';")
echo "✓ $TARGET_DB has $TABLE_COUNT tables"

# Run migration to normalize PHP-serialized fields
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATE_SCRIPT="$SCRIPT_DIR/migrate_serialized_to_links.py"

if [ -f "$MIGRATE_SCRIPT" ]; then
  echo ""
  echo "Running PHP-serialized field migration..."
  python3 "$MIGRATE_SCRIPT" "$TARGET_DB"
  echo "✓ Field migration completed"
else
  echo ""
  echo "⚠ Migration script not found: $MIGRATE_SCRIPT"
  echo "  Skipping PHP-serialized field migration"
fi
