# DB-001: Database Table Audit - ascl_db_v4

**Date**: 2025-11-30
**Database**: `ascl_db_v4` (development copy on Docker MySQL port 3307)
**Task**: Audit current table structure and engine types

---

## Summary

- **Total Tables**: 21
- **MyISAM Tables**: 17 (81%)
- **InnoDB Tables**: 4 (19%)
- **Total Data Size**: ~24 MB

---

## Tables by Engine Type

### MyISAM Tables (Need Conversion)

| Table Name | Rows | Size (MB) | Category | Notes |
|------------|------|-----------|----------|-------|
| `codes` | 4,481 | 8.64 | **CORE** | Main codes table - HIGHEST PRIORITY |
| `code_aliases` | 4,659 | 0.25 | **CORE** | Code aliases - needed for relationships |
| `code_keywords` | 344 | 0.01 | **CORE** | M2M relationship table |
| `keywords` | 68 | 0.00 | **CORE** | Keywords table - needed for relationships |
| `users` | 6 | 0.00 | **CORE** | User accounts |
| `citations` | 18,699 | 1.40 | **ACTIVE** | Legacy citations table (large) |
| `citations_new` | 3,605 | 0.24 | **ACTIVE** | Current citations table |
| `ads_entries` | 1,420 | 0.07 | **LEGACY** | Old ADS entries |
| `ads_entries_new` | 3,657 | 0.18 | **ACTIVE** | Current ADS entries |
| `links` | 4,669 | 0.42 | **LEGACY** | Old links table |
| `links_new` | 6,756 | 0.64 | **ACTIVE** | Current links table |
| `citefile_metadata` | 1,216 | 0.04 | **ACTIVE** | CITATION.cff metadata |
| `change` | 319 | 0.66 | **ACTIVE** | Change tracking/audit log |
| `ci_sessions` | 8,328 | 1.90 | **ACTIVE** | CodeIgniter sessions (WordPress) |
| `classic_citations` | 1,605 | 0.08 | **LEGACY** | Marked "should probably delete this" |
| `codes_backup2` | 1,929 | 3.54 | **BACKUP** | Old backup table |
| `temp` | 854 | 0.03 | **TEMP** | Temporary data |

### InnoDB Tables (Already Converted)

| Table Name | Rows | Size (MB) | Category | Notes |
|------------|------|-----------|----------|-------|
| `ascl_for_zenodo_matching` | 3,706 | 1.52 | **ZENODO** | Zenodo matching data |
| `ascl_for_zenodo_matching2` | 3,374 | 1.52 | **ZENODO** | Zenodo matching data |
| `ascl_for_zenodo_matching_two` | 3,512 | 1.52 | **ZENODO** | Zenodo matching data |
| `link_type` | 0 | 0.03 | **REFERENCE** | Link type lookup table |

---

## Table Categories

### CORE Tables (6) - Highest Priority
These tables form the foundation of the application and **must** be converted:
- `codes` - Main software entries
- `code_aliases` - Alternative names
- `code_keywords` - M2M relationship
- `keywords` - Keyword taxonomy
- `users` - User accounts

**Priority**: Convert these first to enable FK relationships

### ACTIVE Tables (8) - High Priority
Currently used by the application:
- `citations_new` (prefer over `citations`)
- `ads_entries_new` (prefer over `ads_entries`)
- `links_new` (prefer over `links`)
- `citefile_metadata`
- `change`
- `ci_sessions`

**Priority**: Convert after CORE tables

### LEGACY Tables (4) - Consider Archiving
Superseded by newer versions:
- `citations` → superseded by `citations_new`
- `ads_entries` → superseded by `ads_entries_new`
- `links` → superseded by `links_new`
- `classic_citations` → marked "should probably delete this"

**Decision Needed**: Archive or convert?

### BACKUP Tables (1) - Archive
- `codes_backup2` - Old backup (1,929 rows from unknown date)

**Recommendation**: Archive to separate database or export to file

### TEMP Tables (1) - Evaluate
- `temp` - Temporary data (854 rows)

**Decision Needed**: Can this be dropped or does it contain needed data?

### ZENODO Tables (3) - Already InnoDB
- Already converted, no action needed

---

## Conversion Priority Order

### Phase 1: Core Tables (Enable FK Relationships)
1. `codes` - Largest table, primary key needed first
2. `keywords` - Small, quick conversion
3. `code_keywords` - Junction table for M2M
4. `code_aliases` - Related to codes
5. `users` - User management

### Phase 2: Active Tables (Current Features)
6. `citations_new` - Current citation system
7. `ads_entries_new` - Current ADS integration
8. `links_new` - Current links
9. `citefile_metadata` - Citation file metadata
10. `change` - Audit trail
11. `ci_sessions` - Session management

### Phase 3: Legacy Tables (Based on Decision)
12. `citations` - If keeping for historical data
13. `ads_entries` - If keeping for historical data
14. `links` - If keeping for historical data

---

## Next Steps

1. **Create backup** of `ascl_db_v4` before any conversions
2. **Write conversion script** to ALTER tables from MyISAM to InnoDB
3. **Test conversion** on Phase 1 tables (core tables)
4. **Verify data integrity** after conversion
5. **Proceed with Phase 2** conversions
6. **Make decisions** on legacy/backup/temp tables

---

## Important Notes

- **Database**: Working on `ascl_db_v4` (development copy)
- **Safe to experiment**: This is a copy, production data is safe in `ascl_db`
- **No downtime concerns**: Development environment, can break and rebuild
- **Connection**: MySQL 8.0 on Docker port 3307
- **Credentials**: From `~/.my.cnf` section `[client_ascl]`

---

## Risks & Considerations

### MyISAM → InnoDB Conversion Risks
- **Row-level locking**: InnoDB uses row-level vs table-level (usually better)
- **Foreign keys**: InnoDB required for FK constraints (our goal)
- **AUTO_INCREMENT**: May behave slightly differently
- **Full-text search**: If used, need to verify InnoDB support (MySQL 5.6+)
- **Table size**: InnoDB tables may be slightly larger on disk

### Mitigation
- Test on dev database first (✓ we're doing this)
- Backup before conversion (next step)
- Verify data integrity after conversion
- Check application functionality after conversion

---

**Status**: Audit complete, ready for conversion planning
