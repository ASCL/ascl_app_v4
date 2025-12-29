# ASCL Database Character Set Analysis

**Date**: 2025-11-29
**Database**: ascl_db
**Issue**: Inconsistent character sets and collations across tables

---

## Current State Summary

### Table-Level Collations (21 tables)

| Collation | Tables | Notes |
|-----------|--------|-------|
| **latin1_swedish_ci** | 8 | 🔴 Legacy, limited Unicode support |
| **utf8mb3_general_ci** | 6 | 🟡 Deprecated, use utf8mb4 |
| **utf8mb3_unicode_ci** | 7 | 🟡 Deprecated, use utf8mb4 |
| **utf8mb4_general_ci** | 2 | 🟢 Modern, but general_ci is less accurate |

### Breakdown by Collation

#### latin1_swedish_ci (8 tables) - 🔴 NEEDS CONVERSION
```
ascl_for_zenodo_matching
ascl_for_zenodo_matching2
ascl_for_zenodo_matching_two
citefile_metadata
classic_citations
code_keywords
keywords
temp
```

#### utf8mb3_general_ci (6 tables) - 🟡 UPGRADE TO utf8mb4
```
ads_entries
ads_entries_new
citations
citations_new
links
```

#### utf8mb3_unicode_ci (7 tables) - 🟡 UPGRADE TO utf8mb4
```
change
ci_sessions
code_aliases
codes
codes_backup2
users
```

#### utf8mb4_general_ci (2 tables) - 🟢 MODERN (but change to unicode_ci)
```
link_type
links_new
```

---

## Problems This Causes

### 1. JOIN Errors
When joining tables with different collations, MySQL throws errors:
```
ERROR 1267 (HY000): Illegal mix of collations
```

Example: Joining `codes.ascl_id` (utf8mb3_unicode_ci) with `links_new.ascl_id` (latin1_swedish_ci)

### 2. Data Loss Risk
- **latin1** only supports Western European characters (ISO-8859-1)
- Cannot store: Emojis, Chinese/Japanese/Arabic characters, mathematical symbols
- If data contains these characters, conversion could fail

### 3. Inconsistent Sorting
- `utf8mb3_general_ci` vs `utf8mb3_unicode_ci` sort differently
- Example: "ä" sorts differently in general vs unicode collations
- This affects ORDER BY clauses and search results

### 4. Future PostgreSQL Migration
- PostgreSQL uses UTF8 by default
- Migration will be easier if already using utf8mb4

---

## Recommendation: Standardize to utf8mb4_unicode_ci

### Why utf8mb4_unicode_ci?

✅ **Full Unicode Support**
- Supports all Unicode characters (emojis, rare symbols, international text)
- utf8mb4 is MySQL's true UTF-8 (utf8mb3 is limited to 3-byte sequences)

✅ **Accurate Sorting**
- `unicode_ci` follows Unicode collation algorithm
- More accurate for international text than `general_ci`
- Better for scientific names, author names, international characters

✅ **Modern Standard**
- Default for MySQL 8.0+
- What new databases should use
- Prevents future migration headaches

✅ **Foreign Key Compatibility**
- Foreign keys require matching collations
- Prevents collation mismatch errors

✅ **PostgreSQL Migration Ready**
- UTF8 is PostgreSQL's default
- Makes future migration smoother

### Why Not Stay with Current Mix?

❌ **JOIN errors** when combining tables with different collations
❌ **Maintenance burden** - need to remember which table uses which collation
❌ **Data corruption risk** - latin1 can't handle Unicode data
❌ **Performance issues** - MySQL must convert collations during JOINs
❌ **Foreign key restrictions** - can't create FKs across collation boundaries

---

## Conversion Strategy

### Safe Conversion Process

The conversion **must** be done carefully:

1. **Check for data that won't convert**
   - latin1 → utf8mb4: Usually safe
   - But verify no binary data stored in text fields

2. **Convert in correct order**
   - Convert columns first
   - Then convert table default
   - Update foreign key references

3. **Test queries after conversion**
   - Verify JOINs still work
   - Check sorting is correct
   - Ensure searches return same results

### Conversion Commands

#### Method 1: Per-Table Conversion (Recommended)

```sql
-- Example: Convert codes table
ALTER TABLE codes
  CONVERT TO CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

This converts:
- Table default charset/collation
- All text columns in the table
- Preserves data (MySQL handles conversion)

#### Method 2: Column-by-Column (More Control)

```sql
-- Example: Convert specific column
ALTER TABLE codes
  MODIFY ascl_id VARCHAR(8)
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
```

Use this when:
- Some columns need different handling
- Want to verify each column individually
- Table has binary columns that shouldn't convert

---

## Proposed Conversion Plan

### Phase 1: Verify Data Safety (READ-ONLY)

```sql
-- Check for problematic characters in latin1 tables
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'ascl_db'
  AND COLLATION_NAME LIKE 'latin1%'
  AND DATA_TYPE IN ('varchar', 'text', 'mediumtext', 'longtext');

-- Sample data from each latin1 column
-- Look for non-ASCII characters that might not convert cleanly
```

### Phase 2: Convert All Tables to utf8mb4_unicode_ci

Execute in this order (dependencies matter):

```sql
-- ============================================================================
-- STEP 1: Convert tables without foreign keys first
-- ============================================================================

-- Zenodo tables (no FKs, can convert independently)
ALTER TABLE ascl_for_zenodo_matching
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE ascl_for_zenodo_matching2
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE ascl_for_zenodo_matching_two
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Other independent tables
ALTER TABLE temp
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE classic_citations
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE citefile_metadata
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================================
-- STEP 2: Convert core tables (will have FKs referencing them)
-- ============================================================================

-- Keywords table (referenced by code_keywords)
ALTER TABLE keywords
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Codes table (referenced by code_aliases, code_keywords)
ALTER TABLE codes
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE codes_backup2
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================================
-- STEP 3: Convert junction/reference tables
-- ============================================================================

ALTER TABLE code_keywords
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE code_aliases
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================================
-- STEP 4: Convert citation/link tables
-- ============================================================================

ALTER TABLE citations
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE citations_new
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE ads_entries
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE ads_entries_new
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE links
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE links_new
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Note: link_type already utf8mb4, just change to unicode_ci
ALTER TABLE link_type
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- ============================================================================
-- STEP 5: Convert remaining tables
-- ============================================================================

ALTER TABLE change
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE ci_sessions
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

ALTER TABLE users
  CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Phase 3: Verify Conversion

```sql
-- Verify all tables are utf8mb4_unicode_ci
SELECT
    TABLE_NAME,
    TABLE_COLLATION,
    ENGINE
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND TABLE_COLLATION != 'utf8mb4_unicode_ci'
ORDER BY TABLE_NAME;

-- Should return 0 rows if successful

-- Verify all text columns are utf8mb4
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    CHARACTER_SET_NAME,
    COLLATION_NAME
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'ascl_db_v4'
  AND CHARACTER_SET_NAME IS NOT NULL
  AND CHARACTER_SET_NAME != 'utf8mb4'
ORDER BY TABLE_NAME, COLUMN_NAME;

-- Should return 0 rows if successful
```

---

## Integration with InnoDB Upgrade

The charset conversion should be done **AFTER** the InnoDB conversion but **BEFORE** adding foreign keys:

### Updated Upgrade Order

1. ✅ Create ascl_db_v4 and copy data
2. ✅ Fix timestamp columns
3. ✅ Convert to InnoDB
4. **NEW: Convert to utf8mb4_unicode_ci** ← Add this step
5. ✅ Add indexes
6. ✅ Add constraints
7. ✅ Add foreign keys

**Why this order?**
- InnoDB first: No charset restrictions on engine type
- Charset before FKs: Foreign keys require matching collations
- Indexes after charset: Some indexes may need rebuilding

---

## Risks & Mitigation

### Low Risk
- ✅ Working on ascl_db_v4 (copy), not production
- ✅ Can retry if conversion fails
- ✅ MySQL handles character encoding conversion automatically

### Medium Risk
- ⚠️ **Table size may increase** (utf8mb4 uses up to 4 bytes per character vs 3 for utf8mb3)
- ⚠️ **Index key length limits** (utf8mb4 requires more space)
  - MySQL limit: 3072 bytes per index key
  - Unlikely to hit this with current schema

### Mitigation
- Test conversion on ascl_db_v4 first
- Check table sizes before/after
- Verify all queries still work
- Keep ascl_db as fallback

---

## Alternative: Minimal Approach

If you want to minimize changes:

1. **Keep utf8mb3** (don't upgrade to utf8mb4)
2. **Just fix latin1 tables** (convert to utf8mb3_unicode_ci)
3. **Standardize utf8mb3 collation** (all to unicode_ci)

This avoids:
- Table size increases
- Extensive testing of utf8mb4 compatibility

But you lose:
- Full Unicode support (emojis, rare characters)
- PostgreSQL migration readiness
- Modern standard compliance

**Not recommended** - the full utf8mb4 conversion is worth it.

---

## Recommendation

**Proceed with full utf8mb4_unicode_ci conversion** for ascl_db_v4:

✅ Do this as part of the v4 upgrade
✅ Test thoroughly on v4 before production
✅ Document any query changes needed
✅ Update application code if needed (unlikely)

**Benefits outweigh risks:**
- Solves current JOIN errors
- Prevents future data loss
- Simplifies maintenance
- Enables full foreign key support
- Prepares for PostgreSQL migration

---

**Next Steps:**
1. Add charset conversion to `DB_UPGRADE_PLAYBOOK.sql`
2. Test on ascl_db_v4
3. Verify queries still work
4. Update TODO_MASTER.md

