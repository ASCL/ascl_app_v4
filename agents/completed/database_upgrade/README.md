# Database Upgrade Documentation (Completed)

This directory contains historical documentation for the ascl_db → ascl_db_v4 database upgrade.

**Status**: ✅ Complete (as of 2025-11-29)

## What Was Done

The database was upgraded from MyISAM to InnoDB with:
- ✅ All tables converted to InnoDB
- ✅ Primary keys defined
- ✅ Foreign keys added (code_aliases, code_keywords)
- ✅ Indexes added for performance
- ✅ PHP-serialized link fields migrated to normalized `link` table
- ✅ Character set standardized to utf8mb4_unicode_ci
- ✅ Legacy tables excluded (7 tables not migrated)

## Files

| File | Purpose |
|------|---------|
| `DB_UPGRADE_SUMMARY.md` | Executive summary of upgrade work |
| `DB_UPGRADE_ANALYSIS.md` | Detailed analysis and planning |
| `ASCL_DB_Upgrade.md` | Original upgrade specification |
| `DB-001_table_audit.md` | Initial table audit findings |
| `DB_CHARSET_ANALYSIS.md` | Character set analysis |
| `CHARSET_RECOMMENDATION.md` | Character set recommendations |
| `ZERO_DATE_AUDIT.md` | Zero date audit and fixes |
| `READY_TO_EXECUTE.md` | Pre-execution checklist |

## Active Script

The repeatable upgrade script is maintained at:
**`../../DB_UPGRADE_PLAYBOOK.sql`**

This script can be re-run on a fresh copy of ascl_db to recreate ascl_db_v4.

## Current Schema

**Production**: ascl_db (MySQL 8.0, MyISAM - original v3)
**Development**: ascl_db_v4 (MySQL 8.0, InnoDB - upgraded for v4)

---

**Completed**: 2025-11-29
**See also**: `../../TODO_MASTER.md` Phase 1 (Database Infrastructure)
