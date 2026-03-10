#!/bin/bash
# =============================================================================
# migrate_v3_to_v4.sh
# =============================================================================
# Restore an ASCL v3 database backup and migrate it to v4 schema.
#
# This script:
#   1. Prompts for confirmation (type "yesiknow" to proceed)
#   2. Drops and recreates the target database
#   3. Restores the v3 backup (handles .gz or .sql files)
#   4. Runs v3→v4 migrations:
#      - alter_link_type_table.sql (add short_name column)
#      - create_code_note_table.sql (notes → code_note table, ASCLbot user)
#      - create_code_correction_tables.sql (user-submitted corrections)
#      - migrate_serialized_to_links.py (PHP serialized fields → link table)
#      - create_author_table.sql (author, orcid_provenance, code_to_author tables)
#      - migrate_credit_to_authors.py (codes.credit → author table via nameparser)
#   5. Runs validation tests to verify the migration
#
# Usage:
#   ./migrate_v3_to_v4.sh <backup_file> [target_db]
#
# Examples:
#   ./migrate_v3_to_v4.sh ascl_db_2025.09.30_bkup.sql.gz
#   ./migrate_v3_to_v4.sh ascl_db_2025.09.30_bkup.sql.gz ascl_db_v4
#   ./migrate_v3_to_v4.sh /path/to/backup.sql ascl_db_dev
#
# Requirements:
#   - MySQL credentials in ~/.my.cnf under [client_ascl_root] section
#   - Python 3 with phpserialize, mysqlclient, nameparser, and pytest modules
#
# =============================================================================

set -e  # Exit on error

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_TARGET_DB="ascl_db_v4"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

print_header() {
    echo ""
    echo -e "${CYAN}=============================================================================${NC}"
    echo -e "${CYAN}  ASCL Database Restore: v3 → v4 Migration${NC}"
    echo -e "${CYAN}=============================================================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BOLD}${GREEN}[$1]${NC} $2"
}

print_warning() {
    echo -e "${YELLOW}⚠  $1${NC}"
}

print_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓  $1${NC}"
}

usage() {
    echo "Usage: $0 <backup_file> [target_db]"
    echo ""
    echo "Arguments:"
    echo "  backup_file   Path to v3 backup file (.sql or .sql.gz)"
    echo "  target_db     Target database name (default: $DEFAULT_TARGET_DB)"
    echo ""
    echo "Examples:"
    echo "  $0 ascl_db_2025.09.30_bkup.sql.gz"
    echo "  $0 /path/to/backup.sql ascl_db_dev"
    exit 1
}

create_temp_credentials() {
    # Create temporary credentials file from ~/.my.cnf
    # Extract [client_ascl_root] section, rename to [client], remove database= line
    local tmp_file
    tmp_file=$(mktemp)

    if [[ ! -f ~/.my.cnf ]]; then
        print_error "~/.my.cnf not found. Create it with [client_ascl_root] section."
        exit 1
    fi

    awk '
      /^\[client_ascl_root\]/ { in_section=1; print "[client]"; next }
      /^\[/ && in_section { exit }
      in_section && !/^database=/ { print }
    ' ~/.my.cnf > "$tmp_file"

    if [[ ! -s "$tmp_file" ]]; then
        print_error "[client_ascl_root] section not found in ~/.my.cnf"
        rm -f "$tmp_file"
        exit 1
    fi

    echo "$tmp_file"
}

# -----------------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------------

if [[ $# -lt 1 ]]; then
    usage
fi

BACKUP_FILE="$1"
TARGET_DB="${2:-$DEFAULT_TARGET_DB}"

# Validate backup file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    print_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Determine if file is gzipped
IS_GZIPPED=false
if [[ "$BACKUP_FILE" == *.gz ]]; then
    IS_GZIPPED=true
fi

# Get absolute path to backup file
BACKUP_FILE="$(cd "$(dirname "$BACKUP_FILE")" && pwd)/$(basename "$BACKUP_FILE")"

# -----------------------------------------------------------------------------
# Main script
# -----------------------------------------------------------------------------

print_header

echo -e "Backup file:     ${BOLD}$BACKUP_FILE${NC}"
echo -e "Target database: ${BOLD}$TARGET_DB${NC}"
echo -e "File type:       ${BOLD}$(if $IS_GZIPPED; then echo "gzipped SQL"; else echo "plain SQL"; fi)${NC}"
echo ""

# Get file size
if $IS_GZIPPED; then
    FILE_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo -e "Compressed size: ${BOLD}$FILE_SIZE${NC}"
else
    FILE_SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    echo -e "File size:       ${BOLD}$FILE_SIZE${NC}"
fi
echo ""

# Warning banner
echo -e "${RED}=============================================================================${NC}"
echo -e "${RED}  WARNING: This will PERMANENTLY DELETE all data in '$TARGET_DB'${NC}"
echo -e "${RED}=============================================================================${NC}"
echo ""

# Confirmation prompt
echo -e "To proceed, type ${BOLD}yesiknow${NC} and press Enter:"
read -r confirmation

if [[ "$confirmation" != "yesiknow" ]]; then
    echo ""
    print_warning "Aborted. You typed: '$confirmation'"
    exit 1
fi

echo ""
echo -e "${GREEN}Confirmation received. Starting restore...${NC}"
echo ""

# Create temporary credentials file
print_step "1/16" "Setting up MySQL credentials..."
TMP_CREDS=$(create_temp_credentials)
trap "rm -f '$TMP_CREDS'" EXIT
print_success "Temporary credentials file created"

# MySQL connection options
MYSQL_OPTS="--defaults-file=$TMP_CREDS --protocol=TCP --host=127.0.0.1 --port=3307"

# Drop and recreate database
print_step "2/16" "Dropping and recreating database '$TARGET_DB'..."
mysql $MYSQL_OPTS -e "DROP DATABASE IF EXISTS $TARGET_DB;"
mysql $MYSQL_OPTS -e "CREATE DATABASE $TARGET_DB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
print_success "Database '$TARGET_DB' created"

# Restore backup
# Note: Replace SQL_MODE line to disable strict mode and allow zero dates in TIMESTAMP columns
print_step "3/16" "Restoring backup (this may take a while)..."
if $IS_GZIPPED; then
    gunzip -c "$BACKUP_FILE" | sed 's/^SET SQL_MODE = .*/SET SQL_MODE = "";/' | mysql $MYSQL_OPTS "$TARGET_DB"
else
    sed 's/^SET SQL_MODE = .*/SET SQL_MODE = "";/' "$BACKUP_FILE" | mysql $MYSQL_OPTS "$TARGET_DB"
fi
print_success "Backup restored"

# Verify table count
TABLE_COUNT=$(mysql $MYSQL_OPTS -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$TARGET_DB';")
print_success "$TARGET_DB now has $TABLE_COUNT tables"

# Convert tables to InnoDB (required for foreign keys)
print_step "4/16" "Converting tables to InnoDB..."
INNODB_MIGRATION="$SCRIPT_DIR/convert_to_innodb.sql"
if [[ -f "$INNODB_MIGRATION" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$INNODB_MIGRATION"
    print_success "Tables converted to InnoDB"
else
    print_warning "Migration script not found: $INNODB_MIGRATION"
fi

# Rename id columns to pk and update table names for v4
print_step "5/16" "Renaming columns and tables for v4 schema..."
PK_MIGRATION="$SCRIPT_DIR/rename_pk_columns.sql"
if [[ -f "$PK_MIGRATION" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$PK_MIGRATION"
    print_success "Columns and tables renamed"
else
    print_warning "Migration script not found: $PK_MIGRATION"
fi

# Update link_type table schema
print_step "6/16" "Updating link_type table schema..."
LINK_TYPE_MIGRATION="$SCRIPT_DIR/alter_link_type_table.sql"
if [[ -f "$LINK_TYPE_MIGRATION" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$LINK_TYPE_MIGRATION"
    print_success "link_type table schema updated"
else
    print_warning "Migration script not found: $LINK_TYPE_MIGRATION"
    print_warning "Skipping link_type table update"
fi

# Create code_note table (before Python migration so models can load)
print_step "7/16" "Creating code_note table and migrating notes..."
NOTE_MIGRATION="$SCRIPT_DIR/create_code_note_table.sql"
if [[ -f "$NOTE_MIGRATION" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$NOTE_MIGRATION"
    print_success "code_note table created and notes migrated"
else
    print_warning "Migration script not found: $NOTE_MIGRATION"
    print_warning "Skipping code_note table creation"
fi

# Create code_correction tables (for user-submitted corrections)
print_step "8/16" "Creating code_correction tables..."
CORRECTION_MIGRATION="$SCRIPT_DIR/create_code_correction_tables.sql"
if [[ -f "$CORRECTION_MIGRATION" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$CORRECTION_MIGRATION"
    print_success "code_correction tables created"
else
    print_warning "Migration script not found: $CORRECTION_MIGRATION"
    print_warning "Skipping code_correction table creation"
fi

# Run PHP serialization migration
print_step "9/16" "Migrating PHP-serialized fields to link table..."
MIGRATE_SCRIPT="$SCRIPT_DIR/migrate_serialized_to_links.py"
if [[ -f "$MIGRATE_SCRIPT" ]]; then
    python3 "$MIGRATE_SCRIPT" "$TARGET_DB"
    print_success "PHP-serialized fields migrated"
else
    print_warning "Migration script not found: $MIGRATE_SCRIPT"
    print_warning "Skipping PHP-serialized field migration"
fi

# Create author tables and migrate credit field
print_step "10/16" "Creating author, orcid_provenance, and code_to_author tables..."
AUTHOR_MIGRATION="$SCRIPT_DIR/create_author_table.sql"
if [[ -f "$AUTHOR_MIGRATION" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$AUTHOR_MIGRATION"
    print_success "Author tables created"
else
    print_warning "Migration script not found: $AUTHOR_MIGRATION"
fi

print_step "11/16" "Migrating codes.credit to author table..."
AUTHOR_MIGRATE_SCRIPT="$SCRIPT_DIR/migrate_credit_to_authors.py"
if [[ -f "$AUTHOR_MIGRATE_SCRIPT" ]]; then
    python3 "$AUTHOR_MIGRATE_SCRIPT" "$TARGET_DB"
    print_success "Credit field migrated to authors"
else
    print_warning "Migration script not found: $AUTHOR_MIGRATE_SCRIPT"
fi

# Drop PHP-serialized columns from codes table (data now in link table)
print_step "12/16" "Dropping migrated PHP-serialized columns..."
DROP_COLS_SQL="$SCRIPT_DIR/drop_serialized_columns.sql"
if [[ -f "$DROP_COLS_SQL" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$DROP_COLS_SQL"
    print_success "PHP-serialized columns dropped"
else
    print_warning "Migration script not found: $DROP_COLS_SQL"
fi

# Add fulltext index for search (moved to end - slow operation)
print_step "13/16" "Adding fulltext search index..."
FT_MIGRATION="$SCRIPT_DIR/create_fulltext_index.sql"
if [[ -f "$FT_MIGRATION" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$FT_MIGRATION"
    print_success "Fulltext index created"
else
    print_warning "Migration script not found: $FT_MIGRATION"
fi

# Create public_codes view
print_step "14/16" "Creating public_codes view..."
VIEW_SQL="$SCRIPT_DIR/create_public_codes_view.sql"
if [[ -f "$VIEW_SQL" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$VIEW_SQL"
    print_success "public_codes view created"
else
    print_warning "Migration script not found: $VIEW_SQL"
fi

# Seed mission/survey keywords not in v3
print_step "15/16" "Seeding mission/survey keywords..."
SEED_SQL="$SCRIPT_DIR/seed_mission_keywords.sql"
if [[ -f "$SEED_SQL" ]]; then
    mysql $MYSQL_OPTS "$TARGET_DB" < "$SEED_SQL"
    print_success "Mission/survey keywords seeded"
else
    print_warning "Migration script not found: $SEED_SQL"
fi

# Run validation tests
print_step "16/16" "Running migration validation tests..."
APP_DIR="$SCRIPT_DIR/../source/ascl_net_app_project_home"
TEST_FILE="$APP_DIR/ascl_net_app/tests/test_db_schema_v4.py"

if [[ -f "$TEST_FILE" ]]; then
    # Set environment variable so tests connect to the migrated database
    export ASCLDB_DATABASE="$TARGET_DB"

    echo ""
    cd "$APP_DIR"
    if python3 -m pytest "$TEST_FILE" -v --tb=short 2>&1; then
        print_success "All validation tests passed!"
    else
        echo ""
        print_warning "Some tests failed. Review the output above."
        print_warning "This may indicate incomplete migration or schema differences."
    fi
else
    print_warning "Test file not found: $TEST_FILE"
    print_warning "Skipping validation tests"
fi

# Final summary
echo ""
echo -e "${GREEN}=============================================================================${NC}"
echo -e "${GREEN}  Restore and Migration Complete!${NC}"
echo -e "${GREEN}=============================================================================${NC}"
echo ""
echo -e "Database:    ${BOLD}$TARGET_DB${NC}"
echo -e "Tables:      ${BOLD}$TABLE_COUNT${NC}"
echo ""

# Show table counts for key tables
echo "Key table row counts:"
for table in codes keyword link code_note author code_to_author users; do
    count=$(mysql $MYSQL_OPTS -N -e "SELECT COUNT(*) FROM $TARGET_DB.$table;" 2>/dev/null || echo "N/A")
    printf "  %-20s %s\n" "$table:" "$count"
done

echo ""
print_success "Done!"
