# ASCL.net Flask v4 Application - Development Status

**Last Updated**: 2026-01-01

For complete project documentation, see:
- **Project Overview**: `../../CLAUDE.md` (root of alt_ascl)
- **Master TODO & Roadmap**: `../../agents/TODO_MASTER.md`
- **Deployment Guide**: `PRODUCTION_DEPLOYMENT.md` (this directory)

## Quick Status Summary

### ✅ Completed Features

**Phase 1: Database Infrastructure**
- [x] MySQL database upgraded to InnoDB with foreign keys
- [x] Schema: ascl_db_v4 with proper relationships
- [x] PHP-serialized links migrated to normalized link table

**Phase 2: Core Pages**
- [x] Homepage (/)
- [x] About, Resources, Submissions, Explain (WordPress-backed)
- [x] Browse (/browse)
- [x] Search (/search) with Typesense + MySQL fallback
- [x] Code detail pages (/code/<ascl_id>)
- [x] News/blog (/news) - Flask-rendered from WordPress DB

**Phase 3: Admin & Security**
- [x] Admin authentication with bcrypt password hashing
- [x] Public dashboard (/dashboard) with statistics
- [x] Admin interface for unpublished/archived codes
- [x] Session-based auth with login attempt tracking

**Phase 4: Search Enhancement**
- [x] Typesense integration (Phases 1 & 2)
- [x] MySQL fallback for reliability
- [x] Credit search (author search)

**Phase 5: Logging & Monitoring**
- [x] Comprehensive logging system
- [x] Color-coded console output
- [x] File logging with rotation

### 🚧 In Progress / TODO

See `../../agents/TODO_MASTER.md` for complete roadmap.

**High Priority**:
- Admin code editing/insertion
- CSRF protection for admin forms
- Role-based access control
- Pagination for admin lists

**Medium Priority**:
- Homepage fixes (date grouping, [submitted] display)
- Author search improvements (name parsing, fuzzy matching)
- Advanced search features (faceted search, filters)
- Instant search UI (Typesense Phase 3)

**Future**:
- REST API
- MySQL → PostgreSQL migration (optional)
- Link checking automation
- Citation export formats

## How to Run

**Development**:
```bash
cd /home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home
python run_ascl_net_app.py --debug --port 5000
```

**Production**:
See `PRODUCTION_DEPLOYMENT.md`

## Database

- **Development**: `ascl_db_v4` on Docker MySQL (port 3307)
- **Connection**: Configured via `~/.my.cnf` section `[client_ascl]`
- **Schema**: See `../../agents/DB_UPGRADE_PLAYBOOK.sql`

## Key Technologies

- Python 3.x + Flask 3.0+
- SQLAlchemy 2.0
- MySQL 8.0 (with PostgreSQL support built-in)
- Uvicorn ASGI server
- Typesense search engine
- WordPress database integration

## Documentation Archive

Historical development notes have been moved to `archived_docs/`:
- Old development summary (Oct 2025)
- Logging implementation notes (6 files)
- Debugging notes

---

For detailed implementation notes, see `../../CLAUDE.md` and `../../agents/TODO_MASTER.md`.
