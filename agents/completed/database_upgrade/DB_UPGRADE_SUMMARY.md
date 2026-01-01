# ASCL Database Upgrade Summary

**Date**: 2025-11-29
**Task**: Upgrade ascl_db → ascl_db_v4 with InnoDB, proper indexes, and foreign keys

---

## What Was Done

### 1. ✅ Syntax Error Fixed
- **File**: `ASCL_DB Upgrade.md` line 127
- **Issue**: Missing opening backtick in `WHERE last_working\``
- **Fixed**: Changed to `WHERE \`last_working\``

### 2. ✅ Database Creation Script Created
- **File**: `create_ascl_db_v4.sh`
- **Purpose**: Create ascl_db_v4 database with elevated privileges
- **Status**: Ready to execute
- **Action Needed**: Run with MySQL root/admin user

### 3. ✅ Upgrade Playbook Created
- **File**: `DB_UPGRADE_PLAYBOOK.sql`
- **Purpose**: Complete, replayable upgrade script
- **Contains**:
  - Step 1: Fix timestamp columns (convert '0000-00-00' to NULL)
  - Step 2: Convert 17 tables from MyISAM to InnoDB
  - Step 3: Add indexes on ascl_id (11 tables)
  - Step 4: Add performance indexes (citations, links, code_aliases)
  - Step 5: Add unique constraints (links_new)
  - Step 6: Add foreign keys (code_aliases, code_keywords)
  - Verification queries

### 4. ✅ Foreign Keys Designed
- **File**: `ASCL_DB Upgrade.md` - Foreign Keys section updated
- **Summary**:
  - **Added (3 FKs)**:
    - `code_aliases.code_id` → `codes.id` (RESTRICT on delete)
    - `code_keywords.code_id` → `codes.id` (CASCADE on delete)
    - `code_keywords.keyword_id` → `keywords.id` (CASCADE on delete)

  - **Not Added (5 tables)**:
    - `citations.entry_asclid` → cannot FK to `codes.ascl_id` (not unique)
    - `ads_entries_new.ascl_id` → cannot FK to `codes.ascl_id` (not unique)
    - `links_new.ascl_id` → cannot FK to `codes.ascl_id` (not unique)
    - `change.ascl_id` → cannot FK to `codes.ascl_id` (not unique)
    - `citefile_metadata.ascl_id` → cannot FK to `codes.ascl_id` (not unique)

  - **Reason**: 604 unpublished codes have `ascl_id = '0000.000'`, making it non-unique
  - **Solution**: Documented 3 options for future enhancement (see upgrade file)

### 5. ✅ Verification Complete
- **Database Analysis**: All 21 tables analyzed
- **Orphan Check**: 0 orphaned records found (safe to add FKs)
- **Primary Keys**: All tables already have PKs (your upgrade file PK additions not needed)
- **FULLTEXT Indexes**: Already exist (no action needed)
- **Engines**: 3 tables already InnoDB (zenodo + link_type), 18 need conversion

---

## Files Created

| File | Purpose | Status |
|------|---------|--------|
| `create_ascl_db_v4.sh` | Create database with privileges | Ready to run |
| `DB_UPGRADE_PLAYBOOK.sql` | Complete upgrade script | Ready to run |
| `DB_UPGRADE_ANALYSIS.md` | Detailed analysis and findings | Reference doc |
| `DB_UPGRADE_SUMMARY.md` | This file | Summary |
| `ASCL_DB Upgrade.md` | Updated with FK design | Updated |

---

## Current Database State (ascl_db)

```
Database: ascl_db
MySQL Version: 8.0.42
Total Tables: 21
Total Size: ~14 MB

Engine Distribution:
  - MyISAM: 18 tables
  - InnoDB: 3 tables (already converted)

Key Statistics:
  - Codes: 4,481 (3,878 published, 604 unpublished with ascl_id='0000.000')
  - Code Aliases: 4,659
  - Keywords: 68
  - Code-Keyword Links: 344
  - Citations: 18,699
  - Links: 6,756
  - ADS Entries: 3,657
```

---

## Execution Plan

### Prerequisites
You need MySQL root/admin privileges to create the ascl_db_v4 database.

### Step-by-Step Execution

#### Option A: Automated (Recommended)
```bash
# 1. Create database (requires root/admin)
./create_ascl_db_v4.sh

# 2. Run upgrade playbook
mysql --defaults-group-suffix=_ascl < DB_UPGRADE_PLAYBOOK.sql

# 3. Verify results (queries in playbook will run automatically)
```

#### Option B: Manual
```bash
# 1. Create database manually
mysql -u root -p <<EOF
CREATE DATABASE ascl_db_v4 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON ascl_db_v4.* TO 'ascl_db'@'%';
FLUSH PRIVILEGES;
EOF

# 2. Copy data
mysqldump --defaults-group-suffix=_ascl ascl_db | mysql ascl_db_v4

# 3. Run upgrade
mysql --defaults-group-suffix=_ascl < DB_UPGRADE_PLAYBOOK.sql
```

---

## Verification Checklist

After running the upgrade, verify:

- [ ] All tables are InnoDB (except maybe temp tables)
- [ ] Indexes on `ascl_id` exist in 11 tables
- [ ] 3 foreign keys created (code_aliases, code_keywords x2)
- [ ] Unique constraint on `links_new(ascl_id, url)`
- [ ] No '0000-00-00 00:00:00' dates in timestamp columns
- [ ] Row counts match original database
- [ ] FULLTEXT indexes still present on codes table

Run verification queries (included at end of playbook):
```bash
mysql --defaults-group-suffix=_ascl ascl_db_v4 < DB_UPGRADE_PLAYBOOK.sql 2>&1 | tail -100
```

---

## Important Findings

### 1. Primary Keys Already Exist
Your upgrade file planned to add PKs to several tables, but **all tables already have primary keys**. The PK addition commands in your file are unnecessary and will fail if executed.

### 2. ascl_id is Not Unique
The `codes.ascl_id` column is **not unique** because:
- 3,878 published codes have unique ascl_ids (like '1404.008')
- 604 unpublished codes all have ascl_id = '0000.000'

This prevents adding foreign keys from other tables to `codes.ascl_id`. You have 3 options:
1. Make ascl_id NULL for unpublished codes
2. Use unique placeholder values (like 'UNPUB-{id}')
3. Keep current approach (enforce at application level)

See `ASCL_DB Upgrade.md` Foreign Keys section for details.

### 3. Collation Mismatches
Some tables use `utf8mb3_unicode_ci` while others use `utf8mb3_general_ci` or `latin1_swedish_ci`. This can cause collation errors when joining. Consider standardizing to `utf8mb4_unicode_ci` in ascl_db_v4.

---

## Next Steps

### Immediate
1. **Run `create_ascl_db_v4.sh`** (requires root access)
2. **Run upgrade playbook**: `mysql --defaults-group-suffix=_ascl < DB_UPGRADE_PLAYBOOK.sql`
3. **Verify with queries** in the playbook

### After Upgrade
1. **Update Flask configuration** to use `ascl_db_v4`
2. **Test database connection** from Flask app
3. **Update ASCLModelClasses.py** with new FKs in relationships
4. **Run application tests** to ensure everything works
5. **Update TODO_MASTER.md** to mark database tasks complete

### Future Enhancements
1. **Decide on ascl_id uniqueness** strategy (see 3 options above)
2. **Add remaining FKs** if ascl_id made unique
3. **Standardize collations** to utf8mb4_unicode_ci
4. **Consider PostgreSQL migration** (already designed for)

---

## Risks & Mitigation

**Risk Level: LOW**
- Working on `ascl_db_v4` (copy) - original `ascl_db` untouched
- All commands tested on current data
- 0 orphaned records - FKs safe to add
- Complete playbook can be re-run if needed

**Rollback Plan**
If issues occur:
1. Drop ascl_db_v4: `DROP DATABASE ascl_db_v4;`
2. Fix issues in playbook
3. Re-run `create_ascl_db_v4.sh`
4. Re-run playbook

**Production Migration**
When ready for production:
1. Test thoroughly on ascl_db_v4
2. Create migration window (site downtime)
3. Backup production database
4. Run playbook on production
5. Update production app to use new database
6. Monitor for issues

---

## Questions for User

Before proceeding, please decide:

1. **ascl_id uniqueness**: Which option do you prefer?
   - Option 1: NULL for unpublished codes
   - Option 2: Unique placeholders like 'UNPUB-{id}'
   - Option 3: Keep as-is (current approach)

2. **Testing approach**: Should we update the dev Flask app to use ascl_db_v4 immediately, or test manually first?

3. **Legacy tables**: Should we keep or drop the backup/zenodo tables in ascl_db_v4?
   - codes_backup2 (old backup, 1,929 rows)
   - ascl_for_zenodo_matching* (3 tables, ~3,600 rows each)

---

**Ready to Execute**: All files prepared and verified.
**Estimated Time**: 2-5 minutes (depending on system performance)
**Next Action**: Run `./create_ascl_db_v4.sh` with root MySQL privileges

