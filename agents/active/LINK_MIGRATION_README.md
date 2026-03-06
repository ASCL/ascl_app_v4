# PHP-Serialized Links Migration

## Overview

This migration unpacks PHP-serialized link data from the `codes` table into a normalized `link` table structure.

## Changes Made

### 1. Database Schema Updates (DB_UPGRADE_PLAYBOOK.sql - Step 8)

- **Added columns to `link_type` table**:
  - `short_name VARCHAR(50)` - Machine-readable identifier (e.g., 'code-site')
  - `description TEXT` - Human-readable description of the link type

- **Inserted new link types**:
  | Label | Short Name | Description |
  |-------|-----------|-------------|
  | Code Site | code-site | This should be the URL to a site from where the code can be downloaded or copied. |
  | Described In | described-in | Publication where the code is described. |
  | Used In | used-in | Publications that use the code. |
  | Reference | reference | Paper that uses the code. |

- **Renamed table**: `links_new` → `link` (singular, matching Python class naming convention)
  - All subsequent foreign keys, indexes, and constraints updated to use `link`

### 2. Python Migration Script

**File**: `alt_ascl/agents/migrate_php_links_to_table.py`

**Purpose**: Reads PHP-serialized link fields from `codes` table and creates normalized rows in `link` table.

**Migrated fields**:
- `codes.site_list` → `link` table with `link_type = 'code-site'`
- `codes.described_in` → `link` table with `link_type = 'described-in'`
- `codes.used_in` → `link` table with `link_type = 'used-in'`
- `codes.ref_list` → `link` table with `link_type = 'reference'`

**Features**:
- Uses phpserialize library to unpack PHP arrays
- Checks for existing links before inserting (idempotent)
- Supports `--dry-run` mode for testing
- Supports `--limit N` to process only N codes
- Provides detailed logging and statistics

### 3. SQLAlchemy Model Updates

**File**: `ascl_core/source/ascl_core/database/ascldb/ASCLModelClasses.py`

- Renamed class: `LinkNew` → `Link`
- Updated table reference: `'links_new'` → `'link'`
- Updated relationship: `ASCLCode.links` now references `Link` class

## Testing the Migration

### Prerequisites

1. Ensure phpserialize is installed:
   ```bash
   pip install phpserialize
   ```

2. Verify database connection:
   ```bash
   mysql --defaults-group-suffix=_ascl -e "SELECT 1;"
   ```

### Step 1: Apply Database Schema Changes

```bash
# Run the upgrade playbook (includes Step 8: link_type updates and table rename)
mysql --defaults-group-suffix=_ascl -h 127.0.0.1 -P 3307 < alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql
```

**Verification**:
```sql
-- Check link_type table has new columns and rows
mysql --defaults-group-suffix=_ascl -e "
  SELECT pk, label, short_name, description
  FROM link_type
  WHERE short_name IN ('code-site', 'described-in', 'used-in', 'reference');
" ascl_db_v4

-- Verify table was renamed
mysql --defaults-group-suffix=_ascl -e "SHOW TABLES LIKE 'link%';" ascl_db_v4
-- Should show: link, link_type (NOT links_new)
```

### Step 2: Test Migration Script (Dry Run)

```bash
cd /home/demitri/repositories/ASCL/alt_ascl

# Test with 5 codes, dry-run mode
python3 agents/migrate_php_links_to_table.py --dry-run --limit 5 --verbose

# Example output:
# 2025-12-02 - INFO - Loading link_type table...
# 2025-12-02 - INFO - Loaded 5 link types
# 2025-12-02 - INFO - Processing up to 5 codes (--limit specified)
# 2025-12-02 - INFO - Processing code 1404.008 (pk=1)
# 2025-12-02 - INFO -   site_list: Found 1 URL(s)
# 2025-12-02 - INFO -   [DRY RUN] Would create link: https://dx.doi.org/10.20356/C4WC7Q (type: code-site)
# ...
```

**Verification**:
- Review the output to ensure URLs are being extracted correctly
- Check that link types are mapped correctly
- No database changes should occur in dry-run mode

### Step 3: Run Migration on Sample Data

```bash
# Migrate 10 codes (for testing)
python3 agents/migrate_php_links_to_table.py --limit 10

# Check results
mysql --defaults-group-suffix=_ascl -e "
  SELECT
    l.id,
    l.code_pk,
    c.ascl_id,
    l.url,
    lt.short_name,
    lt.label
  FROM link l
  JOIN codes c ON l.code_pk = c.pk
  JOIN link_type lt ON l.link_type_pk = lt.pk
  WHERE lt.short_name IN ('code-site', 'described-in', 'used-in', 'reference')
  ORDER BY l.code_pk, lt.short_name
  LIMIT 20;
" ascl_db_v4
```

### Step 4: Full Migration

```bash
# Migrate all codes
python3 agents/migrate_php_links_to_table.py

# Expected output:
# ============================================================
# Migration Summary:
# ============================================================
# Codes processed:      XXXX
# Links created:        XXXX
# Skipped (empty):      XXX
# Skipped (existing):   X
# Errors:               0
# ============================================================
```

**Verification Queries**:

```sql
-- Count links by type
mysql --defaults-group-suffix=_ascl -e "
  SELECT
    lt.label,
    lt.short_name,
    COUNT(*) as count
  FROM link l
  JOIN link_type lt ON l.link_type_pk = lt.pk
  WHERE lt.short_name IN ('code-site', 'described-in', 'used-in', 'reference')
  GROUP BY lt.pk, lt.label, lt.short_name
  ORDER BY count DESC;
" ascl_db_v4

-- Find codes with the most links
mysql --defaults-group-suffix=_ascl -e "
  SELECT
    c.ascl_id,
    c.title,
    COUNT(*) as link_count
  FROM link l
  JOIN codes c ON l.code_pk = c.pk
  JOIN link_type lt ON l.link_type_pk = lt.pk
  WHERE lt.short_name IN ('code-site', 'described-in', 'used-in', 'reference')
  GROUP BY c.pk, c.ascl_id, c.title
  ORDER BY link_count DESC
  LIMIT 10;
" ascl_db_v4

-- Check for any NULL code_pk values
mysql --defaults-group-suffix=_ascl -e "
  SELECT COUNT(*) as null_code_pk_count
  FROM link
  WHERE code_pk IS NULL;
" ascl_db_v4
-- Should be 0

-- Sample random links to verify data quality
mysql --defaults-group-suffix=_ascl -e "
  SELECT
    c.ascl_id,
    c.title,
    l.url,
    lt.short_name
  FROM link l
  JOIN codes c ON l.code_pk = c.pk
  JOIN link_type lt ON l.link_type_pk = lt.pk
  WHERE lt.short_name IN ('code-site', 'described-in', 'used-in', 'reference')
  ORDER BY RAND()
  LIMIT 20;
" ascl_db_v4
```

## Troubleshooting

### Issue: "phpserialize not found"
**Solution**: Install the library
```bash
pip install phpserialize
```

### Issue: "Access denied" database error
**Solution**: Check MySQL credentials in `~/.my.cnf` under `[client_ascl]` section

### Issue: "Duplicate entry" error
**Solution**: The script checks for existing links before inserting. This error means:
- The migration was run twice, OR
- There's a unique constraint violation

To fix:
```sql
-- Check for duplicates
SELECT code_pk, url, COUNT(*) as count
FROM link
GROUP BY code_pk, url
HAVING count > 1;

-- Delete duplicates (keep lowest id)
DELETE l1 FROM link l1
INNER JOIN link l2
WHERE l1.id > l2.id
  AND l1.code_pk = l2.code_pk
  AND l1.url = l2.url;
```

### Issue: Some URLs not migrated
**Solution**: Check for PHP serialization errors in logs
```bash
# Run with verbose logging
python3 agents/migrate_php_links_to_table.py --verbose | grep -i "failed to unserialize"
```

## Rollback

If you need to rollback the migration:

```sql
-- Delete migrated links
DELETE FROM link
WHERE link_type_pk IN (
  SELECT pk FROM link_type
  WHERE short_name IN ('code-site', 'described-in', 'used-in', 'reference')
);

-- Verify deletion
SELECT COUNT(*) FROM link
WHERE link_type_pk IN (
  SELECT pk FROM link_type
  WHERE short_name IN ('code-site', 'described-in', 'used-in', 'reference')
);
-- Should be 0
```

## Next Steps

After successful migration:

1. **Update Flask application** to use the `link` table instead of parsing PHP-serialized fields
   - Read links via `ASCLCode.links` relationship
   - Filter by `link_type.short_name` to get specific link types

2. **Verify application functionality** with new data structure

3. **Drop PHP-serialized columns** (after thorough testing):
   ```sql
   ALTER TABLE codes
     DROP COLUMN site_list,
     DROP COLUMN ref_list,
     DROP COLUMN described_in,
     DROP COLUMN used_in;
   ```
   **⚠️ WARNING**: Only do this after verifying all data is migrated correctly!

## Files Modified

- `alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql` - Added Step 8 (link_type updates, table rename)
- `alt_ascl/agents/migrate_php_links_to_table.py` - New migration script
- `ascl_core/source/ascl_core/database/ascldb/ASCLModelClasses.py` - Renamed LinkNew → Link
- `alt_ascl/agents/TODO_MASTER.md` - Documented migration task (DATA-011)
- `~/.my.cnf` - Fixed MySQL credentials (user: ascl_db, database: ascl_db_v4)

## References

- TODO_MASTER.md: Phase 4 (Data Migration & Handling) → DATA-011
- DB_UPGRADE_PLAYBOOK.sql: Step 8
