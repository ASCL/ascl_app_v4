# Agent Documentation

This directory contains documentation for AI agents working on the ASCL.net v3 → v4 migration.

## 📋 Master Planning

- **`TODO_MASTER.md`** - The definitive TODO list and project roadmap
- **`CONSOLIDATION_PLAN.md`** - Documentation reorganization plan (executed 2026-01-01)

## 🗄️ Database

- **`DB_UPGRADE_PLAYBOOK.sql`** - Repeatable database upgrade script (v3 → v4)

## 📂 Directory Structure

- **`active/`** - Current agent instructions for ongoing work
- **`completed/`** - Completed work documentation (historical reference)
- **`obsolete/`** - Obsolete files kept for reference only

## 🔍 Finding What You Need

**"What should I work on next?"**
→ See `TODO_MASTER.md`

**"How do I fix the homepage?"**
→ See `active/HOMEPAGE_FIXES_NEEDED.md`

**"How does search work?"**
→ See `active/SEARCH_ANALYSIS_AND_RECOMMENDATIONS.md`

**"How do I set up Typesense?"**
→ See `active/TYPESENSE_SETUP_GUIDE.md`

**"How do I rebuild the search index?"**
→ Run `ascl typesense reset` (see Typesense Management section below)

**"How was the database upgraded?"**
→ See `completed/database_upgrade/DB_UPGRADE_SUMMARY.md`

**"What logging work was done?"**
→ See `completed/logging/LOGGING_FINAL_STATUS.md`

## 🔎 Typesense Management

Typesense search index management has moved to the `ascl` CLI (`bin/ascl`):

```
ascl typesense reset     # Drop collection, recreate schema, re-index all codes
ascl typesense index     # (Re-)index all published codes (idempotent upsert)
ascl typesense status    # Show collection health, document count
```

Requires `TYPESENSE_API_KEY` env var. URL and collection name come from `~/.config/ascl/config.toml`.

The standalone scripts `typesense_setup_collection.py` and `typesense_import_data.py` in this directory are **superseded** by the CLI commands above.

## 🔬 Discovery Bar (Random Code Browser)

The discovery bar appears on code detail pages and lets users browse related codes.
All logic is in `controllers/code_detail.py`.

- **Domain terms** (`DOMAIN_TERMS` list, ~line 210): Tuples of `(match_pattern, display_label)` scanned against the code's abstract. Patterns ending with `*` match as prefix. Matched terms become "More X" pills linking to `/discover/domain/`.
- **Mission/survey pills** (~line 303): Primary source is the code's keywords from DB. Fallback: `MISSION_FALLBACKS` list scans the abstract for well-known mission names (case-sensitive).
- **Language pills** (`LANGUAGE_TERMS`, ~line 344): Programming languages/tools matched in abstract, shown as "More X" pills linking to `/discover/language/`.
- **Other pills**: "Similar" (keyword overlap), "Referenced by" (citation links), "By same author", "Surprise me" (random).
- **CSS**: `static/css/style.css` lines 956-1029 (`.discovery-bar`, `.discovery-pill`, etc.)
- **Template**: `templates/code_detail.html` lines 6-66 (`#discovery-bar`)

## 📝 File Organization

As of 2026-01-01, agent documentation has been reorganized:
- **Active work** → `active/` subdirectory
- **Completed projects** → `completed/` subdirectory (by topic)
- **Obsolete files** → `obsolete/` subdirectory (kept for reference)

See `CONSOLIDATION_PLAN.md` for details on the reorganization.

---

**Last Updated**: 2026-03-20
