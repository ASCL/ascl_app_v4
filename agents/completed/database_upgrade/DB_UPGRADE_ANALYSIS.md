# ASCL Database Upgrade Analysis
**Date**: 2025-11-29
**Current Database**: `ascl_db` (MySQL 8.0.42)
**Target Database**: `ascl_db_v4`
**Status**: Analysis Complete, Ready for Execution

---

## Current State Summary

### Table Count: 21 tables

### Engine Distribution:
- **MyISAM**: 18 tables (need conversion to InnoDB)
- **InnoDB**: 3 tables (already converted: zenodo matching tables + link_type)

### Primary Keys Status:
✅ **ALL TABLES HAVE PRIMARY KEYS** - No PKs need to be added
- Note: Your upgrade file planned to add PKs to zenodo tables and code_keywords, but they already exist

### FULLTEXT Indexes (Already Exist):
✅ Already implemented:
- `code_aliases.alias` (FULLTEXT)
- `codes.title` (FULLTEXT)
- `codes.abstract` (FULLTEXT)
- `codes.credit_old` (FULLTEXT)
- `codes_backup2.title` (FULLTEXT)
- `codes_backup2.abstract` (FULLTEXT)
- `codes_backup2.credit_old` (FULLTEXT)

### Foreign Keys:
❌ **NO FOREIGN KEYS EXIST** - All need to be created

---

## Issues Found in Upgrade File

### 1. Syntax Error (Line 127)
**Current:**
```sql
WHERE last_working` = '0000-00-00 00:00:00';
```

**Should be:**
```sql
WHERE `last_working` = '0000-00-00 00:00:00';
```
Missing opening backtick.

### 2. Primary Key Commands Not Needed
The following commands in your file are unnecessary (PKs already exist):
- `ascl_for_zenodo_matching` - already has `id` PK
- `ascl_for_zenodo_matching2` - already has `id` PK
- `ascl_for_zenodo_matching_two` - already has `id` PK
- `code_keywords` - already has composite PK on (code_id, keyword_id)

---

## Upgrade Plan: Step-by-Step Execution

### Step 0: Create New Database
```sql
CREATE DATABASE ascl_db_v4 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Copy data from `ascl_db` to `ascl_db_v4`:
```bash
mysqldump --defaults-group-suffix=_ascl ascl_db | mysql --defaults-group-suffix=_ascl ascl_db_v4
```

### Step 1: Fix Timestamp Columns (Required for InnoDB)
**Why**: InnoDB doesn't allow '0000-00-00 00:00:00' default values in strict mode

Tables affected:
- `codes` (time_added, time_updated)
- `codes_backup2` (time_added, time_updated)
- `links` (created_at, updated_at, last_working)
- `links_new` (created_at, updated_at, last_working) ⚠️ **FIX SYNTAX ERROR**

**Status**: Ready to execute (after fixing syntax error in line 127)

### Step 2: Convert Tables to InnoDB
Tables to convert (18 tables):
```sql
ALTER TABLE `ads_entries` ENGINE = InnoDB;
ALTER TABLE `ads_entries_new` ENGINE = InnoDB;
ALTER TABLE `change` ENGINE = InnoDB;
ALTER TABLE `citations` ENGINE = InnoDB;
ALTER TABLE `citations_new` ENGINE = InnoDB;
ALTER TABLE `citefile_metadata` ENGINE = InnoDB;
ALTER TABLE `ci_sessions` ENGINE = InnoDB;
ALTER TABLE `classic_citations` ENGINE = InnoDB;
ALTER TABLE `codes` ENGINE = InnoDB;
ALTER TABLE `codes_backup2` ENGINE = InnoDB;
ALTER TABLE `code_aliases` ENGINE = InnoDB;
ALTER TABLE `code_keywords` ENGINE = InnoDB;
ALTER TABLE `keywords` ENGINE = InnoDB;
ALTER TABLE `links` ENGINE = InnoDB;
ALTER TABLE `links_new` ENGINE = InnoDB;
ALTER TABLE `temp` ENGINE = InnoDB;
ALTER TABLE `users` ENGINE = InnoDB;
```

**Note**: `ascl_for_zenodo_matching*` tables already InnoDB, skip those.

### Step 3: Add Indexes on ascl_id
All commands in your file are valid and ready to execute:
- `codes` - Add UNIQUE KEY on ascl_id
- `codes_backup2` - Add UNIQUE KEY on ascl_id
- `ads_entries` - Add KEY on ascl_id
- `ads_entries_new` - Add KEY on ascl_id
- `ascl_for_zenodo_matching*` (3 tables) - Add KEY on ascl_id
- `citefile_metadata` - Add KEY on ascl_id
- `links` - Add KEY on ascl_id
- `links_new` - Add KEY on ascl_id
- `change` - Add KEY on ascl_id

### Step 4: Add Other Performance Indexes
```sql
-- citations tables
ALTER TABLE citations
  ADD KEY idx_citations_entry_asclid (entry_asclid),
  ADD KEY idx_citations_entry_year (entry_asclid, year);

ALTER TABLE citations_new
  ADD KEY idx_citations_new_entry_asclid (entry_asclid),
  ADD KEY idx_citations_new_entry_year (entry_asclid, year);

-- links table
ALTER TABLE links
  ADD KEY idx_links_url (url),
  ADD KEY idx_links_ascl_working (ascl_id, is_working);

-- code_aliases
ALTER TABLE code_aliases
  ADD KEY idx_code_aliases_code_id (code_id);
```

### Step 5: Add Constraints
```sql
-- Unique constraint on links_new
ALTER TABLE `links_new`
  ADD UNIQUE KEY `uniq_links_new_asclid_url` (`ascl_id`, `url`);
```

### Step 6: Add Foreign Keys
**Status**: ❌ NOT YET DEFINED in your upgrade file

Need to define FKs for:
- `code_aliases.code_id` → `codes.id`
- `code_keywords.code_id` → `codes.id`
- `code_keywords.keyword_id` → `keywords.id`
- Others TBD based on schema analysis

---

## Recommended Order of Execution

1. ✅ **Create ascl_db_v4 and copy data**
2. ✅ **Fix timestamp columns** (Step 1)
3. ✅ **Convert to InnoDB** (Step 2)
4. ✅ **Add ascl_id indexes** (Step 3)
5. ✅ **Add other indexes** (Step 4)
6. ✅ **Add constraints** (Step 5)
7. ⏳ **Define and add foreign keys** (Step 6 - needs design)

---

## Verification Queries

After each step, verify:

```sql
-- Check engine conversion
SELECT TABLE_NAME, ENGINE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'ascl_db_v4'
ORDER BY ENGINE, TABLE_NAME;

-- Check indexes
SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE
FROM information_schema.STATISTICS
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND TABLE_NAME = 'codes'
ORDER BY INDEX_NAME;

-- Check foreign keys (after Step 6)
SELECT
    TABLE_NAME,
    CONSTRAINT_NAME,
    REFERENCED_TABLE_NAME,
    REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND REFERENCED_TABLE_NAME IS NOT NULL;
```

---

## Next Steps

1. Fix syntax error in ASCL_DB Upgrade.md line 127
2. Design foreign key relationships
3. Execute steps on ascl_db_v4 database
4. Verify each step before proceeding to next
5. Update TODO_MASTER.md as steps complete

---

## Risk Assessment

**Low Risk**:
- Creating new database (ascl_db_v4 keeps original intact)
- Adding indexes (can be dropped if issues)
- Adding constraints (can be dropped if issues)

**Medium Risk**:
- Converting to InnoDB (changes storage engine, but v4 is separate)
- Timestamp column changes (data modification, but tested in your file)

**High Risk Items** (design carefully):
- Foreign keys (can cause issues if orphaned records exist)
- Must verify data integrity before adding FKs

**Mitigation**:
- Work on ascl_db_v4 (leaves original intact)
- Test each FK before adding (check for orphaned records)
- Create migration script that can be re-run

---

**Analysis Complete**: Ready to proceed with execution.
