# Ready to Execute Database Upgrade

**Status**: ✅ All files prepared and verified
**Date**: 2025-11-29

---

## What Will Happen

### Step 1: Create ascl_db_v4
- Create new database with utf8mb4_unicode_ci default
- Grant privileges to ascl_db user
- Copy data from ascl_db **EXCLUDING 7 legacy tables**:
  - ascl_for_zenodo_matching_two
  - ascl_for_zenodo_matching2
  - ads_entries
  - links
  - citations_new
  - classic_citations
  - codes_backup2

**Result**: 14 tables copied (21 original - 7 excluded)

### Step 2: Run Upgrade Playbook

The playbook will execute in this order:

1. **Fix Timestamp Columns** (codes, links_new)
   - Convert '0000-00-00' dates to NULL
   - Set proper defaults for InnoDB compatibility

2. **Convert to InnoDB** (11 tables)
   - All remaining MyISAM tables → InnoDB

3. **Convert Character Sets** (all 14 tables)
   - Standardize to utf8mb4_unicode_ci
   - Solves collation mismatch errors
   - Enables full Unicode support

4. **Add Indexes on ascl_id** (6 tables)
   - codes (UNIQUE)
   - ads_entries_new, ascl_for_zenodo_matching, citefile_metadata, links_new, change (KEY)

5. **Add Performance Indexes**
   - citations: entry_asclid, (entry_asclid, year)
   - code_aliases: code_id

6. **Add Constraints**
   - links_new: UNIQUE(ascl_id, url)

7. **Add Foreign Keys** (3 FKs)
   - code_aliases.code_id → codes.id
   - code_keywords.code_id → codes.id
   - code_keywords.keyword_id → keywords.id

8. **Verify Results**
   - All tables InnoDB?
   - All tables utf8mb4_unicode_ci?
   - Foreign keys created?
   - No zero dates remaining?

---

## Commands to Execute

```bash
# Step 1: Create database and copy data (excludes legacy tables)
./create_ascl_db_v4.sh

# Step 2: Run upgrade playbook
mysql --defaults-group-suffix=_ascl_root < DB_UPGRADE_PLAYBOOK.sql
```

**Estimated time**: 2-5 minutes

---

## After Execution

1. **Verify results** - queries run automatically at end of playbook
2. **Update Flask connection** to use ascl_db_v4
3. **Update ASCLModelClasses.py** - remove legacy table classes
4. **Test Flask app** with new database
5. **Update TODO_MASTER.md** - mark database tasks complete

---

## Notes

### "pk" Column Standard
Per user request: Use "pk" as the standard primary key column name for **new tables created going forward**.

Existing tables keep their current PK column names:
- codes: `id`
- keywords: `id`
- code_aliases: composite PK (`code_id`, `alias`)
- code_keywords: composite PK (`code_id`, `keyword_id`)
- etc.

### Legacy Tables Removed
These tables are NOT in ascl_db_v4:
- ✂️ ascl_for_zenodo_matching_two (external project, not used)
- ✂️ ascl_for_zenodo_matching2 (external project, not used)
- ✂️ ads_entries (superseded by ads_entries_new)
- ✂️ links (superseded by links_new)
- ✂️ citations_new (intermediate migration table)
- ✂️ classic_citations (deprecated, marked for deletion in v3)
- ✂️ codes_backup2 (old backup, 1,929 rows from earlier date)

ASCLModelClasses.py references to these tables will need to be removed/commented out.

---

**Ready to proceed!** Waiting for your approval to execute.

