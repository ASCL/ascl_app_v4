# ASCL.net v3 → v4 Migration - Master TODO

**Project**: Migrate ascl.net from PHP+CodeIgniter+MySQL to Python+Flask+MySQL/PostgreSQL
**Started**: 2025-11-29
**Status**: In Progress

---

## Development Environment

**Current Setup**:
- **Environment**: Development server (local)
- **MySQL Containers**: Two separate Docker MySQL instances running on this server:

  **⚠️ IMPORTANT**: There are TWO MySQL containers on this server:

  1. **Port 3306** (`mysql` container) - **DO NOT TOUCH** - Not for ASCL work
     - Used for other projects on this server
     - Do not modify, do not use for ASCL development

  2. **Port 3307** (`mysql_ascl_dev` container) - **ASCL Development Database**
     - Container: `mysql_ascl_dev` (MySQL 8.0.42)
     - Port: 3307 (mapped from container's 3306)
     - Databases: `ascl_db_v4`, `ascl_phpbb`, `ascl_wordpress`
     - Credentials: `~/.my.cnf` section `[client_ascl_root]`
     - Root password: (matches `[client_ascl_root]` in `~/.my.cnf`)
     - This is the ONLY MySQL instance for ASCL development

- **Database Name**: `ascl_db_v4` (copy of production database)
- **Connection Config**: `alt_ascl/ascl_core/database/connections/Trillian2DBConnection.py`
- **Approach**: Work freely on dev database copy - breaking changes OK, no production downtime concerns

**Production Setup** (future):
- **Environment**: Production server (TBD)
- **Database**: MySQL 8.0 (or PostgreSQL after migration)
- **Database Port**: 3306 (standard MySQL) or 5432 (PostgreSQL)
- **Connection Config**: Need to create separate production connection class

**Key Notes**:
- Development database is a full copy of production data
- All schema changes should be tested on dev database first
- Migration scripts should be created for applying changes to production
- No need to worry about downtime during dev database changes

---

## Table of Contents
1. [Database Infrastructure](#database-infrastructure)
2. [Core Framework Setup](#core-framework-setup)
3. [Database Models & Relationships](#database-models--relationships)
4. [Data Migration & Handling](#data-migration--handling)
5. [Web Application - Core Pages](#web-application---core-pages)
6. [Web Application - Code Management](#web-application---code-management)
7. [Web Application - Search & Browse](#web-application---search--browse)
8. [Web Application - Export Formats](#web-application---export-formats)
9. [WordPress Integration](#wordpress-integration)
10. [Authentication & Authorization](#authentication--authorization)
11. [API Development](#api-development)
12. [Admin Interface](#admin-interface)
13. [Template System](#template-system)
14. [Testing & Quality](#testing--quality)
15. [Deployment & DevOps](#deployment--devops)
16. [Documentation](#documentation)

---

## Dependency Legend
- 🔴 **BLOCKED** - Cannot start until dependencies complete
- 🟡 **READY** - Dependencies met, can start anytime
- 🟢 **IN PROGRESS** - Currently being worked on
- ✅ **DONE** - Completed

---

## Phase 1: Database Infrastructure

**Goal**: Convert MySQL schema to use InnoDB, define proper primary/foreign keys

### 1.1 Database Engine Conversion
**Dependencies**: None
**Status**: 🟢 IN PROGRESS

- [x] **DB-001**: Audit current table structure
  - [x] List all tables in `ascl_db_v4` database
  - [x] Document current engine type for each table (MyISAM vs InnoDB)
  - [x] Document row counts and table sizes
  - [x] Identify tables actively used vs legacy/backup tables

- [ ] **DB-002**: Convert tables from MyISAM to InnoDB
  - [ ] Create backup of database before conversion
  - [x] Write conversion script for each active table (DB_UPGRADE_PLAYBOOK.sql)
  - [x] Test conversion on development copy (`ascl_db_v4`)
  - [ ] Convert production tables (requires downtime planning)
  - [x] Verify data integrity after conversion (all remaining tables InnoDB)

- [x] **DB-003**: Remove or archive legacy tables
  - [x] Drop/exclude `codes_backup2` (old backup, 1,929 rows)
  - [x] Drop/exclude `classic_citations` (marked "should probably delete this")
  - [x] Drop/exclude `citations_new` (intermediate migration table, 3,605 rows)
  - [x] Drop/exclude `links` (superseded by `links_new`, 4,669 rows)
  - [x] Drop/exclude `ads_entries` (superseded by `ads_entries_new`, 1,420 rows)
  - [x] Drop/exclude `ascl_for_zenodo_matching_two`, `ascl_for_zenodo_matching2`

### 1.2 Primary Keys Definition
**Dependencies**: DB-001 complete
**Status**: 🟢 IN PROGRESS

- [x] **DB-004**: Define primary keys for all tables
  - [x] `codes` - Renamed `id` → `pk` (MEDIUMINT UNSIGNED PK)
  - [x] `code_aliases` - Composite PK
  - [x] `code_keywords` - Composite PK (`code_id`, `keyword_id`)
  - [x] `keywords` - PK
  - [x] `citations` - PK
  - [x] `ads_entries_new` - PK
  - [x] `links_new` - PK
  - [x] `users` - PK
  - [x] `change` - PK
  - [x] `citefile_metadata` - PK
  - [x] `ci_sessions` - PK
  - [x] `temp` - PK

### 1.3 Foreign Keys Definition
**Dependencies**: DB-004 complete
**Status**: ✅ DONE

- [x] **DB-005**: Document foreign key relationships
  - [ ] Create ER diagram showing table relationships
  - [x] Document FK constraints needed:
    - [x] `code_aliases.code_id` → `codes.pk`
    - [x] `code_keywords.code_id` → `codes.pk`
    - [x] `code_keywords.keyword_id` → `keywords.id`
    - [x] `citations.code_pk` → `codes.pk` (migrated from entry_asclid)
    - [x] `ads_entries_new.code_pk` → `codes.pk`
    - [x] `links_new.code_pk` → `codes.pk`
    - [x] `change.code_pk` → `codes.pk`
    - [x] `citefile_metadata.code_pk` → `codes.pk`
    - [x] `ascl_for_zenodo_matching.code_pk` → `codes.pk`
  - [x] Deprecated `ascl_id` as a foreign key; all joins now use `codes.pk`/`code_pk`, `ascl_id` kept only in codes table for display/search

- [x] **DB-006**: Implement foreign key constraints
  - [x] Add FK constraints in development database (code_aliases, code_keywords, ads_entries_new, links_new, change, citefile_metadata, ascl_for_zenodo_matching, citations → codes.pk)
  - [x] Test data integrity with constraints enabled
  - [ ] Fix any orphaned records or data integrity issues (placeholder `0000.000` remains)
  - [ ] Apply FK constraints to production database
  - [x] Set up ON DELETE/UPDATE rules (mostly SET NULL/CASCADE where applicable)

- [x] **DB-008**: Migrate all tables from ascl_id to code_pk (Step 16 in DB_UPGRADE_PLAYBOOK.sql)
  - [x] `citations` - Added code_pk, populated from entry_asclid, dropped entry_asclid
  - [x] `ads_entries_new` - Populated code_pk from ascl_id, dropped ascl_id
  - [x] `links_new` - Populated code_pk, updated unique constraint (ascl_id,url) → (code_pk,url), dropped ascl_id
  - [x] `change` - Dropped ascl_id (code_pk already populated)
  - [x] `citefile_metadata` - Populated code_pk, dropped ascl_id
  - [x] `ascl_for_zenodo_matching` - Populated code_pk, dropped ascl_id
  - [x] Verified all foreign keys point to codes.pk (8 total FK constraints)
  - [x] Result: Only codes.ascl_id remains (for display/search), all joins use integer code_pk

### 1.4 Database Optimization
**Dependencies**: DB-002, DB-004, DB-005 complete
**Status**: 🔴 BLOCKED

- [ ] **DB-007**: Create indexes for performance
  - [ ] Index `codes.ascl_id` (likely already indexed as PK)
  - [ ] Index `codes.title` (for search)
  - [ ] Index `codes.time_added` (for sorting by date)
  - [ ] Index `code_keywords.code_id` and `code_keywords.keyword_id`
  - [ ] Index `citations.ascl_id`
  - [ ] Index `links_new.code` and `links_new.is_working`
  - [ ] Profile slow queries and add indexes as needed

---

## Phase 2: Core Framework Setup

**Goal**: Ensure dm-dbcore and ascl_core modules are properly configured

### 2.1 dm-dbcore Module
**Dependencies**: None
**Status**: 🟡 READY

- [ ] **CORE-001**: Verify dm-dbcore functionality
  - [ ] Test DatabaseConnection class with MySQL
  - [ ] Test MetadataCache functionality
  - [ ] Test session_scope context manager
  - [ ] Verify MySQL credential reading from `~/.my.cnf` section `[client_ascl]`
  - [ ] Document usage patterns for the project

- [ ] **CORE-002**: Add ASCL-specific configuration
  - [ ] Create connection preset for ascl_db_v4 database
  - [ ] Configure connection pooling parameters
  - [ ] Set up metadata cache location and naming

- [ ] **CORE-002a**: Create production database connection class
  - [ ] Create `ProductionDBConnection.py` in `ascl_core/database/connections/`
  - [ ] Configure for production MySQL (port 3306) or PostgreSQL (port 5432)
  - [ ] Set up environment-based configuration (avoid hardcoded credentials)
  - [ ] Use `~/.my.cnf` section `[client_ascl]` for MySQL or `~/.pgpass` for PostgreSQL
  - [ ] Document connection class usage for production deployment
  - [ ] Note: Development uses `Trillian2DBConnection.py` (Docker MySQL on port 3307)

### 2.2 ascl_core Module
**Dependencies**: CORE-001 complete
**Status**: 🔴 BLOCKED

- [ ] **CORE-003**: Verify ascl_core database connection
  - [ ] Test connection to ascl_db_v4 database
  - [ ] Verify schema reflection works correctly
  - [ ] Test with both MySQL and PostgreSQL (for future migration)
  - [ ] Verify metadata caching works

- [ ] **CORE-004**: Package and distribution setup
  - [ ] Verify pyproject.toml is correctly configured
  - [ ] Test installation with `pip install -e .`
  - [ ] Document installation process in README
  - [ ] Consider publishing to PyPI (optional)

---

## Phase 3: Database Models & Relationships

**Goal**: Complete ASCLModelClasses.py with all relationships defined

### 3.1 Model Class Definitions
**Dependencies**: DB-004 complete (PKs defined), CORE-003 complete
**Status**: 🔴 BLOCKED

- [ ] **MODEL-001**: Verify all table classes exist in ASCLModelClasses.py
  - [x] `ASCLCode` (codes table)
  - [x] `ASCLCodeAlias` (code_aliases table)
  - [x] `ASCLCodeToKeyword` (code_keywords table)
  - [x] `Keyword` (keywords table)
  - [x] `User` (users table)
  - [x] `Citation` (citations table)
  - [x] `CitationNew` (citations_new table)
  - [x] `ADSEntry` (ads_entries table)
  - [x] `ADSEntryNew` (ads_entries_new table)
  - [x] `Link` (links table)
  - [x] `LinkNew` (links_new table)
  - [x] `CitefileMetadata` (citefile_metadata table)
  - [x] `Change` (change table)
- [x] `ClassicCitation` (classic_citations table)
- [x] `CISession` (ci_sessions table)
- [x] `Temp` (temp table)
- [x] Remove unused legacy table classes (Zenodo matching, ads_entries, links, classic_citations, citations_new, codes_backup2)

### 3.2 Relationship Definitions
**Dependencies**: MODEL-001 complete, DB-006 complete (FKs defined)
**Status**: ✅ DONE

- [x] **MODEL-002**: Define one-to-many relationships
  - [x] `ASCLCode.aliases` → `ASCLCodeAlias` (one code has many aliases)
    - Uses: `ASCLCode.pk == ASCLCodeAlias.code_id`
    - Backref: `alias.code`
  - [x] `ASCLCode.citations` → `Citation` (one code has many citations)
    - Uses: `ASCLCode.pk == Citation.code_pk` (migrated from entry_asclid)
    - Backref: `citation.ascl_code`
  - [x] `ASCLCode.ads_entries` → `ADSEntryNew` (one code has many ADS entries)
    - Uses: `ASCLCode.pk == ADSEntryNew.code_pk`
    - Backref: `ads_entry.ascl_code`
  - [x] `ASCLCode.links` → `LinkNew` (one code has many links)
    - Uses: `ASCLCode.pk == LinkNew.code_pk`
    - Backref: `link.ascl_code`
  - [x] `ASCLCode.citefile_metadata` → `CitefileMetadata` (one-to-many)
    - Uses: `ASCLCode.pk == CitefileMetadata.code_pk`
    - Backref: `citefile_metadata.ascl_code`
  - [x] `ASCLCode.changes` → `Change` (one code has many change records)
    - Uses: `ASCLCode.pk == Change.code_pk`
    - Backref: `change.ascl_code`

- [x] **MODEL-003**: Define many-to-many relationships
  - [x] `ASCLCode.keywords` ↔ `Keyword` (via `code_keywords` junction table)
    - Uses: `ASCLCode.pk == code_keywords.code_id`, `Keyword.id == code_keywords.keyword_id`
    - Backref: `keyword.ascl_codes`
  - [x] Verified all relationships work correctly with test data
  - [x] All relationships use `lazy="selectin"` to avoid N+1 query problem
  - [x] All relationships use `cascade="save-update, merge"` to let DB handle deletion via FK constraints

- [ ] **MODEL-004**: Add convenience properties and methods
  - [ ] `ASCLCode.primary_alias` - Get the first/primary alias
  - [ ] `ASCLCode.site_urls` - Unserialize PHP site_list field
  - [ ] `ASCLCode.reference_urls` - Unserialize PHP ref_list field
  - [ ] `ASCLCode.described_in_bibcodes` - Unserialize PHP described_in field
  - [ ] `ASCLCode.used_in_bibcodes` - Unserialize PHP used_in field
  - [ ] `ASCLCode.is_published` - Boolean check
  - [ ] `ASCLCode.full_bibcode` - Generate ADS bibcode
  - [ ] Helper methods for common queries

### 3.3 Model Validation
**Dependencies**: MODEL-002, MODEL-003 complete
**Status**: 🔴 BLOCKED

- [ ] **MODEL-005**: Add data validation
  - [ ] Validate ASCL ID format (YYMM.NNN)
  - [ ] Validate email addresses
  - [ ] Validate URLs in serialized fields
  - [ ] Validate ADS bibcode format
  - [ ] Add SQLAlchemy validators using `@validates` decorator

---

## Phase 4: Data Migration & Handling

**Goal**: Handle PHP-serialized data and prepare for future migrations

### 4.1 PHP Serialization Handling
**Dependencies**: MODEL-001 complete
**Status**: 🔴 BLOCKED

- [ ] **DATA-001**: Set up PHP deserialization utilities
  - [ ] Install `phpserialize` library
  - [ ] Create helper function `php_unserialize_list()`
  - [ ] Test with real data from `site_list`, `ref_list`, `described_in`, `used_in`
  - [ ] Handle edge cases (NULL, empty arrays, malformed data)

- [ ] **DATA-002**: Integrate PHP deserialization into model properties
  - [ ] Add `@property` methods to ASCLCode for deserialization
  - [ ] Test property access in Flask views
  - [ ] Document usage for other developers

- [ ] **DATA-003**: (Optional) Plan migration away from PHP serialization
  - [ ] Design new table structure for `code_sites` (one-to-many)
  - [ ] Design new table structure for `code_references` (one-to-many)
  - [ ] Design migration script to convert serialized data
  - [ ] Note: `keywords` already migrated to M2M table

### 4.2 Data Integrity & Cleanup
**Dependencies**: DB-006 complete (FKs in place)
**Status**: 🔴 BLOCKED

- [ ] **DATA-004**: Clean up data issues
  - [ ] Find and fix orphaned records (e.g., aliases without codes)
  - [ ] Standardize data formats (dates, URLs, bibcodes)
  - [ ] Remove duplicate entries
  - [ ] Handle NULL vs empty string inconsistencies

---

## Phase 5: Web Application - Core Pages

**Goal**: Implement basic public-facing pages

### 5.1 Homepage
**Dependencies**: MODEL-002 complete (relationships defined)
**Status**: 🟡 READY

- [x] **WEB-001**: Homepage controller (index.py)
  - [x] Basic implementation exists
  - [ ] Verify query for recent codes works
  - [ ] Add error handling for database failures
  - [ ] Test with real data

- [ ] **WEB-002**: Homepage template (index.html)
  - [ ] Display recent additions (10 most recent codes)
  - [ ] Add featured/random codes section
  - [ ] Add quick search box
  - [ ] Add site statistics (total codes, new this month, etc.)
  - [ ] Match v3 layout and styling

### 5.2 Static Pages (WordPress Content)
**Dependencies**: WP-001 complete (WordPress connection)
**Status**: 🟢 IN PROGRESS

- [x] **WEB-003**: About page
  - [x] Controller to fetch WordPress content (ID=2) with subpage menu ordering matching v3
  - [x] Template to display content via shared WordPress renderer
  - [x] Match v3 styling (uses existing base + WordPress tab bar order)

- [x] **WEB-004**: Resources page
  - [x] Controller to fetch WordPress content (ID=697) via shared renderer
  - [x] Template to display content

- [x] **WEB-005**: Submissions page
  - [x] Controller to fetch WordPress content (ID=29) via shared renderer
  - [x] Template to display content

- [x] **WEB-006**: Explain page
  - [x] Controller to fetch WordPress content (ID=1442) via shared renderer
  - [x] Template to display content

### 5.3 Error Pages
**Dependencies**: None
**Status**: 🟡 READY

- [ ] **WEB-007**: 404 error page
  - [ ] Custom 404 handler
  - [ ] Try to match ASCL ID or alias (like v3 does)
  - [ ] Suggest similar codes
  - [ ] Template with helpful messaging

- [ ] **WEB-008**: 500 error page
  - [ ] Custom error handler
  - [ ] User-friendly error message
  - [ ] Log errors to Sentry or file

- [ ] **WEB-009**: Generic error handling
  - [ ] Database connection errors
  - [ ] Template rendering errors
  - [ ] Permission errors

---

## Phase 6: Web Application - Code Management

**Goal**: Implement code viewing, submission, and editing

### 6.1 Code Detail Page
**Dependencies**: MODEL-002 complete, DATA-002 complete (PHP deserialization)
**Status**: 🔴 BLOCKED

- [ ] **CODE-001**: Code detail controller (code_detail.py)
  - [x] Basic implementation exists
  - [ ] Load code by ASCL ID
  - [ ] Load code by alias (redirect to canonical URL)
  - [ ] Handle code not found (404)
  - [ ] Load related data (keywords, citations, links)

- [ ] **CODE-002**: Code detail template
  - [ ] Display all code metadata
  - [ ] Display aliases
  - [ ] Display keywords with links
  - [ ] Display site URLs (deserialized from PHP)
  - [ ] Display reference URLs (deserialized from PHP)
  - [ ] Display described_in bibcodes
  - [ ] Display used_in bibcodes (or count)
  - [ ] Display citation information
  - [ ] Add "Cite this code" section with BibTeX
  - [ ] Add export links (CodeMeta, CFF, JSON, XML)
  - [ ] Match v3 layout and styling

### 6.2 Code Submission (Public)
**Dependencies**: None
**Status**: 🟡 READY

- [ ] **CODE-003**: Submission form controller
  - [ ] Create route `/code/submit`
  - [ ] Implement form with Flask-WTF
  - [ ] Add bot challenge (like v3: "Physics is phun")
  - [ ] Validate all fields
  - [ ] Save submission to database with status='unpublished'
  - [ ] Send confirmation email to submitter
  - [ ] Send notification email to curators

- [ ] **CODE-004**: Submission form template
  - [ ] Form fields matching v3:
    - [ ] Code name (title)
    - [ ] Short name (alias)
    - [ ] Authors/credits
    - [ ] Site URL(s)
    - [ ] Description
    - [ ] Reference URL(s)
    - [ ] Programming language(s)
    - [ ] Submitter email
    - [ ] Bot challenge field
  - [ ] Field help text and validation messages
  - [ ] Match v3 styling

### 6.3 Code Editing (Session-based)
**Dependencies**: CODE-003 complete
**Status**: 🔴 BLOCKED

- [ ] **CODE-005**: Edit submission controller
  - [ ] Create route `/code/edit/<id>`
  - [ ] Verify edit token/session (like v3)
  - [ ] Load submission by ID
  - [ ] Pre-populate form with existing data
  - [ ] Save changes
  - [ ] Prevent editing of published codes

- [ ] **CODE-006**: Edit submission template
  - [ ] Re-use submission form template
  - [ ] Add cancel/delete options
  - [ ] Show submission status

### 6.4 Code Change Requests
**Dependencies**: None
**Status**: 🟡 READY

- [ ] **CODE-007**: Change request controller
  - [ ] Create route `/code/change/<ascl_id>`
  - [ ] Load existing code
  - [ ] Accept change suggestions
  - [ ] Save to `change` table
  - [ ] Send notification to curators
  - [ ] Optionally post to phpBB forum (if integration maintained)

- [ ] **CODE-008**: Change request template
  - [ ] Form to suggest changes
  - [ ] Show current code information
  - [ ] Capture "before" snapshot
  - [ ] Add change notes field

---

## Phase 7: Web Application - Search & Browse

**Goal**: Implement search and browse functionality

### 7.1 Browse All Codes
**Dependencies**: MODEL-002 complete
**Status**: 🟡 READY

- [ ] **BROWSE-001**: Browse controller (browse.py)
  - [x] Basic implementation exists
  - [ ] Test pagination works correctly
  - [ ] Add view mode toggle (abstract vs compact)
  - [ ] Implement sorting (by title, date, ID)
  - [ ] Add filters (by year, month, keyword)
  - [ ] Test performance with full dataset

- [ ] **BROWSE-002**: Browse template (browse.html)
  - [ ] List view with pagination
  - [ ] Sorting controls
  - [ ] Filter controls
  - [ ] Results count display
  - [ ] Abstract view (full descriptions)
  - [ ] Compact view (title + basic info only)
  - [ ] Match v3 styling

### 7.2 Browse by ASCL ID
**Dependencies**: BROWSE-001 complete
**Status**: 🔴 BLOCKED

- [ ] **BROWSE-003**: Browse by ID controller
  - [ ] Create route `/code/all_by_id`
  - [ ] Group codes by year and month (from ASCL ID)
  - [ ] Generate hierarchical structure
  - [ ] Add navigation by year/month

- [ ] **BROWSE-004**: Browse by ID template
  - [ ] Display grouped by year and month
  - [ ] Collapsible sections
  - [ ] Jump to year/month navigation

### 7.3 Browse by Keywords
**Dependencies**: MODEL-003 complete (keyword relationships)
**Status**: 🔴 BLOCKED

- [ ] **BROWSE-005**: Keywords controller
  - [ ] Create route `/code/keywords`
  - [ ] List all keywords with code counts
  - [ ] Create route `/code/keywords/<keyword_id>`
  - [ ] Filter codes by keyword
  - [ ] Support multiple keyword filtering

- [ ] **BROWSE-006**: Keywords template
  - [ ] Display all keywords
  - [ ] Show code count per keyword
  - [ ] Keyword cloud or tag display
  - [ ] Filtered results page

### 7.4 Search Functionality
**Dependencies**: None (basic), SEARCH-002 for advanced
**Status**: 🟡 READY (Basic search exists, needs enhancement)

- [x] **SEARCH-001**: Basic text search
  - [x] Create route `/search` (search.py:9-41)
  - [x] Search in title field (MySQL LIKE)
  - [x] Search in abstract field (MySQL LIKE)
  - [x] Search in credit field (MySQL LIKE)
  - [x] Display results (search.html)
  - [ ] Add pagination (currently shows all results)
  - [ ] Add result count display

**Current Implementation** (2025-12-01):
- **File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py`
- **Route**: `GET /search?q={query}`
- **Search Method**: SQL OR query across title, abstract, credit using LIKE
  ```python
  WHERE title LIKE '%{query}%'
     OR abstract LIKE '%{query}%'
     OR credit LIKE '%{query}%'
  ORDER BY time_added DESC, pk DESC
  ```
- **Limitations**:
  - ❌ Same issues as credit search (no ranking, no fuzzy matching)
  - ❌ No pagination (could be slow with many results)
  - ❌ No filters (keywords, date range, etc.)
  - ❌ No result highlighting
  - ❌ Searches unpublished codes (should filter published=1)

**Issues**:
1. **Missing published filter**: Should only search published codes
2. **No pagination**: All results loaded at once (performance issue)
3. **No relevance ranking**: Results ordered by date, not match quality
4. **No search highlighting**: Matched terms not highlighted in results

- [ ] **SEARCH-002**: Advanced search features
  - [ ] Define search engine technology (Elasticsearch, PostgreSQL FTS, or keep MySQL FULLTEXT)
  - [ ] Implement chosen search technology
  - [ ] Search by author/credits (✅ partially done via credit search)
  - [ ] Search by ASCL ID
  - [ ] Search by keyword (via keywords table relationship)
  - [ ] Search by programming language
  - [ ] Search by bibcode (described_in, used_in)
  - [ ] Combined filters (multiple criteria)
  - [ ] Result highlighting
  - [ ] "Did you mean?" suggestions

**Technology Options for SEARCH-002**:

**Option A: MySQL FULLTEXT** (Easiest, stays with current stack)
- Pros: Already have MySQL, no new dependencies, built-in ranking
- Cons: Limited features, no fuzzy matching, language-specific analyzers limited
- Implementation:
  ```sql
  ALTER TABLE codes ADD FULLTEXT INDEX ft_search (title, abstract, credit);
  SELECT *, MATCH(title,abstract,credit) AGAINST('query' IN NATURAL LANGUAGE MODE) AS score
  FROM codes WHERE MATCH(title,abstract,credit) AGAINST('query')
  ORDER BY score DESC;
  ```

**Option B: PostgreSQL Full-Text Search** (Medium complexity, migration needed)
- Pros: Better than MySQL FTS, trigram similarity, built-in ranking, no new service
- Cons: Requires PostgreSQL migration, learning curve
- Implementation:
  ```sql
  ALTER TABLE codes ADD COLUMN search_vector tsvector;
  CREATE INDEX idx_search ON codes USING GIN(search_vector);
  UPDATE codes SET search_vector =
    to_tsvector('english', coalesce(title,'') || ' ' || coalesce(abstract,'') || ' ' || coalesce(credit,''));
  ```

**Option C: Elasticsearch** (Most powerful, highest complexity)
- Pros: Best search quality, fuzzy matching, faceting, highlighting, suggestions
- Cons: New service to maintain, additional infrastructure, sync complexity
- Implementation:
  - Index codes in Elasticsearch
  - Keep MySQL as primary database
  - Sync on every code update
  - Use Elasticsearch for search queries only

**Recommended**: Start with **Option A** (MySQL FULLTEXT), migrate to **Option B** or **C** if needed later.

- [ ] **SEARCH-003**: Search template (search.html)
  - [x] Basic search form exists
  - [x] Basic results display
  - [ ] Add advanced search options (filters)
  - [ ] Faceted navigation (filter by keyword, year, etc.)
  - [ ] Sort options (relevance, date, title)
  - [ ] Result highlighting
  - [ ] Match v3 search interface
  - [ ] Add result count and pagination controls

### 7.5 Credit Search (Author Search)
**Dependencies**: None
**Status**: ✅ DONE (Basic implementation complete, improvements needed)

- [x] **SEARCH-004**: Credit search controller
  - [x] Create route `/code/cs/<term>` (search.py:43-83)
  - [x] Create route `/code/cs_submit` for form submission (search.py:85-102)
  - [x] Search in credits field using SQL LIKE
  - [x] URL decode and HTML entity decode search terms
  - [x] Limit to 100 results, published codes only
  - [ ] **IMPROVEMENT NEEDED**: Parse author names intelligently (see below)
  - [ ] **IMPROVEMENT NEEDED**: Handle partial matches better (see below)

- [x] **SEARCH-005**: Credit search template
  - [x] Display author search results (credit_search.html)
  - [x] Show search refinement form
  - [x] Display helpful tip about name variations
  - [ ] **IMPROVEMENT NEEDED**: Group by author name variants (see below)

**Current Implementation** (2025-12-01):
- **File**: `alt_ascl/source/ascl_net_app_project_home/ascl_net_app/controllers/search.py`
- **Routes**:
  - `GET /code/cs/<path:search_term>` - Displays credit search results
  - `POST /code/cs_submit` - Form submission handler (redirects to GET route)
- **Search Method**: Simple SQL LIKE query: `WHERE credit LIKE '%{term}%'`
- **Limitations**:
  - ❌ No intelligent name parsing (doesn't understand "Last, First" vs "First Last")
  - ❌ No fuzzy matching or similarity ranking
  - ❌ No author name normalization
  - ❌ Doesn't group results by author variants
  - ❌ No search result ranking (just time_added DESC)

**Known Issues & Suggested Improvements**:

1. **Issue**: Author name format inconsistency
   - Problem: Authors stored as "Smith, John", "Smith, J.", "John Smith", "Smith"
   - Current: Simple LIKE search finds partial matches but doesn't understand relationships
   - **Suggested Fix**: Implement author name parser/normalizer
     - Extract last name, first name, initials
     - Search for all variations
     - Rank exact matches higher than partial matches

2. **Issue**: No fuzzy matching
   - Problem: Typos or slight variations miss results (e.g., "O'Brien" vs "OBrien")
   - Current: Exact substring match only
   - **Suggested Fixes** (pick one):
     - Option A: Add MySQL SOUNDEX for phonetic matching
     - Option B: Use PostgreSQL pg_trgm extension for trigram similarity
     - Option C: Implement Elasticsearch with fuzzy matching
     - Option D: Keep simple LIKE but add substring tokenization

3. **Issue**: No result ranking
   - Problem: Results ordered only by time_added, not relevance
   - Current: Newest codes appear first, regardless of match quality
   - **Suggested Fix**: Implement relevance scoring
     - Exact match (full name) = highest score
     - Last name match = medium score
     - Partial match = lower score
     - Order by score DESC, then time_added DESC

4. **Issue**: No author grouping
   - Problem: Multiple variations of same author scattered in results
   - Current: Just lists all matching codes
   - **Suggested Fix**: Add "Group by author" view option
     - Extract unique author names from results
     - Group codes under each author variant
     - Show "Other variations: Smith, J.; Smith, John; ..." for each group

5. **Issue**: Performance with large result sets
   - Problem: Full table scan on TEXT field with LIKE
   - Current: Works fine with ~4,400 codes, but not scalable
   - **Suggested Fixes**:
     - Option A: Add MySQL FULLTEXT index on credit field
     - Option B: Create separate authors table (normalize)
     - Option C: Use PostgreSQL with GIN index
     - Option D: Implement Elasticsearch

**Recommended Improvement Path**:

**Phase 1** (Quick wins, stay with MySQL LIKE):
- [ ] Add FULLTEXT index to `codes.credit` field
- [ ] Implement simple name parsing (extract last name)
- [ ] Search for "Last" when given "First Last" or "Last, First"
- [ ] Add relevance scoring (exact > partial)
- [ ] Order by score, then time_added

**Phase 2** (Better search, still MySQL):
- [ ] Create `code_authors` junction table (normalize author data)
  - Columns: code_pk, author_name, author_last, author_first, author_initials
  - Populated from parsing `codes.credit` field
  - Indexed for fast searching
- [ ] Update credit search to use junction table
- [ ] Add "Did you mean?" suggestions for typos
- [ ] Implement author faceting (group by author variant)

**Phase 3** (Advanced search engine):
- [ ] Evaluate Elasticsearch vs PostgreSQL FTS
- [ ] Implement chosen search technology
- [ ] Add fuzzy matching, synonyms, stemming
- [ ] Full-text search across all fields (not just credit)
- [ ] Faceted search with filters

**Phase 4** (Data quality):
- [ ] Author name normalization script
- [ ] Deduplicate author variants in database
- [ ] ORCID integration for author disambiguation
- [ ] Admin tool for merging author variants

### 7.6 Alias List
**Dependencies**: MODEL-002 complete
**Status**: 🔴 BLOCKED

- [ ] **BROWSE-007**: Alias list controller
  - [ ] Create route `/code/alias_list`
  - [ ] Load all aliases with code titles
  - [ ] Sort alphabetically

- [ ] **BROWSE-008**: Alias list template
  - [ ] Display alias → full name mapping
  - [ ] Clickable links to code pages

### 7.7 Random Code
**Dependencies**: None
**Status**: 🟡 READY

- [ ] **BROWSE-009**: Random code controller
  - [ ] Create route `/code/random`
  - [ ] Select random published code from database
  - [ ] Redirect to code detail page

---

## Phase 8: Web Application - Export Formats

**Goal**: Implement data export endpoints

### 8.1 CodeMeta Export
**Dependencies**: CODE-001 complete, DATA-002 complete
**Status**: 🔴 BLOCKED

- [ ] **EXPORT-001**: CodeMeta JSON endpoint
  - [ ] Create route `/<ascl_id>/codemeta.json`
  - [ ] Generate CodeMeta 2.0 compliant JSON
  - [ ] Map ASCL fields to CodeMeta fields
  - [ ] Test with CodeMeta validator

### 8.2 Citation File Format (CFF)
**Dependencies**: CODE-001 complete
**Status**: 🔴 BLOCKED

- [ ] **EXPORT-002**: CFF endpoint
  - [ ] Create route `/<ascl_id>/CITATION.cff`
  - [ ] Generate CFF YAML format
  - [ ] Create redirect from `/citation.cff` → `/CITATION.cff`
  - [ ] Test with CFF validator

### 8.3 Bulk Export Formats
**Dependencies**: MODEL-002 complete
**Status**: 🔴 BLOCKED

- [ ] **EXPORT-003**: JSON export
  - [ ] Create route `/code/json`
  - [ ] Export all codes as JSON array
  - [ ] Add pagination support for large datasets
  - [ ] Add filters (date range, keywords, etc.)

- [ ] **EXPORT-004**: XML export
  - [ ] Create route `/code/xml` (100 most recent)
  - [ ] Create route `/code/dci` (all codes)
  - [ ] Create route `/code/dci/<date>` (codes updated since date)
  - [ ] Generate valid XML structure
  - [ ] Test with XML parser

- [ ] **EXPORT-005**: ADS format export
  - [ ] Create route `/code/ads/<date>`
  - [ ] Generate plain text format for ADS import
  - [ ] Include bibcode, authors, title, description

- [ ] **EXPORT-006**: OLE format export (Alice)
  - [ ] Create route `/code/ole/<date>`
  - [ ] Generate JSON format for Alice (OLE)
  - [ ] Require authentication for dates before certain threshold
  - [ ] Verify format matches v3 output

### 8.4 BibTeX Export
**Dependencies**: CODE-001 complete
**Status**: 🔴 BLOCKED

- [ ] **EXPORT-007**: BibTeX generation
  - [ ] Add BibTeX generation function
  - [ ] Create route `/<ascl_id>/bibtex` or embed in code detail page
  - [ ] Support multiple citation styles

---

## Phase 9: WordPress Integration

**Goal**: Pull WordPress content into Flask app

### 9.1 WordPress Database Connection
**Dependencies**: None
**Status**: 🟢 IN PROGRESS

- [ ] **WP-001**: Set up WordPress database access
  - [ ] Document WordPress table structure (`0hjpDo4yM_` prefix)
  - [ ] Create SQLAlchemy models for WordPress tables (read-only) or lightweight query helpers
    - [ ] `posts` table
    - [ ] `postmeta` table (if needed)
  - [x] Test queries to fetch posts (latest published posts read from `ascl_wordpress.0hjpDo4yM_posts`)
  - [ ] Add configuration for WordPress database connection
  - [ ] Consider using `wordpress_orm` (owner-maintained) once basic news endpoints are stable

### 9.2 WordPress Content Fetching
**Dependencies**: WP-001 complete
**Status**: 🔴 BLOCKED

- [ ] **WP-002**: WordPress content helper
  - [ ] Create function `get_wordpress_page(page_id)`
  - [ ] Fetch `post_content`, `post_title`, `post_parent`
  - [ ] Parse WordPress shortcodes (if needed)
  - [ ] Cache fetched content (Redis or file cache)

- [ ] **WP-003**: WordPress integration in templates
  - [ ] Create WordPress content display template/macro
  - [ ] Test with About, Resources, Submissions pages
  - [ ] Handle missing/deleted WordPress pages

### 9.3 WordPress Blog/News
**Dependencies**: WP-001 complete
**Status**: ✅ DONE

- [x] **WP-004**: Blog listing page
  - [x] Create route `/news` (Flask) backed by `ascl_wordpress.0hjpDo4yM_posts`
  - [x] Fetch recent blog posts (post_type='post', post_status='publish') with pagination
  - [x] Display with pagination
  - [x] Template: `alt_ascl/templates/news_list.html`
  - [x] Controller: `alt_ascl/controllers/news.py`

- [x] **WP-005**: Individual blog post page
  - [x] Create route `/news/<slug>` or fetch by ID
  - [x] Display full post content
  - [x] Handle WordPress formatting and embeds
  - [x] Template: `alt_ascl/templates/news_detail.html`
  - [x] Controller: `alt_ascl/controllers/news.py`

**Implementation Notes**:
- **Current Architecture**: Flask queries WordPress database directly (hybrid approach)
  - Production site at https://ascl.net/wordpress/ is full WordPress installation with separate theme
  - Flask implementation at /news queries `ascl_wordpress.0hjpDo4yM_posts` directly
  - Renders posts using Flask templates with ASCL site styling (consistent with rest of site)
  - This approach aligns with Phase 9 migration strategy (gradual WordPress → Flask migration)

- **Production vs Dev**:
  - Production: Full WordPress blog with WordPress theme, comments, plugins at /wordpress/
  - Flask /news: Simplified presentation, consistent ASCL styling, no WordPress overhead
  - Future: Full migration to Flask/Python once all features stable

**Options for Future Direction** (Decision Pending):

**Option 1: Keep Flask /news implementation** ✅ (Recommended by migration plan)
- **Pros**:
  - Consistent styling with rest of ASCL site
  - Full control over presentation and features
  - No WordPress overhead or maintenance
  - Aligns with v3→v4 migration strategy
- **Cons**:
  - No comments system (unless implemented separately)
  - No WordPress plugin features
  - Need to maintain Flask templates
- **Best for**: Unified site experience, gradual migration to Flask/Python

**Option 2: Redirect /news to WordPress**
- **Pros**:
  - Full WordPress features (comments, plugins, widgets)
  - No Flask code to maintain for blog
  - Leverage WordPress ecosystem
- **Cons**:
  - Different styling/theme from main ASCL site
  - Maintains two separate systems indefinitely
  - Inconsistent user experience
- **Best for**: Keeping WordPress features while migrating everything else

**Option 3: Proxy WordPress through Flask**
- **Pros**:
  - Can wrap WordPress content in ASCL template/styling
  - Unified navigation and header/footer
  - Gradual migration while maintaining features
- **Cons**:
  - Complex implementation
  - Potential caching and performance issues
  - Debugging difficulties
  - Still maintains WordPress dependency
- **Best for**: Transition period with unified styling

**Recommended**: **Option 1** - Current Flask implementation aligns with TODO Phase 9 plan and provides unified site experience. Completed tasks WP-004 and WP-005 implement this approach successfully.

---

## Phase 10: Authentication & Authorization

**Goal**: Implement user login and permission system

### 10.1 User Authentication
**Dependencies**: None
**Status**: ✅ DONE (2025-12-28)

- [x] **AUTH-001**: Upgrade password hashing ✅ **COMPLETED 2025-12-28**
  - [x] Replace SHA-1 with bcrypt (v3 uses SHA-1)
  - [x] Expanded database password field from 40 to 60 characters (`migrations/001_upgrade_password_hashing.sql`)
  - [x] Implemented dual-hash authentication system (supports both SHA-1 and bcrypt during migration)
  - [x] Automatic password migration on successful login (no user password reset required)
  - [x] Added comprehensive test suite (`test_password_hashing.py`)
  - [x] Documentation: `PASSWORD_HASHING_UPGRADE.md`
  - **Security Impact**: Passwords now protected with industry-standard bcrypt (work factor 12)

- [x] **AUTH-002**: Login system ✅ **COMPLETED**
  - [x] Login form implemented in `/admin` template
  - [x] Route `/admin/login` (POST) handles authentication
  - [x] Verifies credentials against `users` table
  - [x] Creates Flask session on successful login
  - [x] Logout route `/admin/logout` implemented

- [x] **AUTH-003**: Session management ✅ **COMPLETED**
  - [x] Custom session handling using Flask sessions
  - [x] Store user ID and username in session
  - [x] `_current_user()` helper function implemented
  - [x] `@_login_required` decorator protects admin routes
  - [x] Login attempt tracking (lockout after 10 failed attempts)

**Current v4 admin auth (implementation)**
- Credentials stored in MySQL database `users` table (fields: `username`, `real_name`, `password` = bcrypt or SHA-1, `login_attempts`)
- Password hashing: bcrypt with automatic SHA-1 migration on login
- Session-based authentication with login attempt tracking
- Protected routes: `/admin/unpublished`, `/admin/archived` require login

### 10.2 User Roles & Permissions
**Dependencies**: AUTH-002 complete
**Status**: 🔴 BLOCKED

- [ ] **AUTH-004**: Define user roles
  - [ ] Document role types (admin, curator, user)
  - [ ] Add role field to users table (or separate table)
  - [ ] Implement role checking functions

- [ ] **AUTH-005**: Permission decorators
  - [ ] Create `@admin_required` decorator
  - [ ] Create `@curator_required` decorator
  - [ ] Protect admin routes with permissions

---

## Phase 11: API Development

**Goal**: Create RESTful API for external access

### 11.1 API Infrastructure
**Dependencies**: MODEL-002 complete
**Status**: 🔴 BLOCKED

- [ ] **API-001**: API framework setup
  - [ ] Decide: Flask-RESTful, Flask-RESTX, or FastAPI integration
  - [ ] Set up API blueprints
  - [ ] Configure CORS if needed
  - [ ] Set up API versioning (e.g., `/api/v1/`)

- [ ] **API-002**: API authentication
  - [ ] Implement HTTP Basic Auth (like v3)
  - [ ] Or implement API key authentication
  - [ ] Or implement OAuth 2.0
  - [ ] Document authentication in API docs

### 11.2 API Endpoints
**Dependencies**: API-001 complete
**Status**: 🔴 BLOCKED

- [ ] **API-003**: Search endpoint
  - [ ] Create route `/api/search`
  - [ ] Accept query parameters:
    - [ ] `q` - search query (field:"value" or just "value")
    - [ ] `fl` - field list (comma-separated)
    - [ ] `fq` - filter query (field[operator]:value)
  - [ ] Return JSON results
  - [ ] Limit fields for unauthenticated users
  - [ ] Return all fields for authenticated users
  - [ ] Test with various query formats

- [ ] **API-004**: Code detail endpoint
  - [ ] Create route `/api/code/<ascl_id>`
  - [ ] Return full code information as JSON
  - [ ] Include deserialized PHP fields

- [ ] **API-005**: List codes endpoint
  - [ ] Create route `/api/codes`
  - [ ] Support pagination (page, per_page)
  - [ ] Support filtering (keywords, date range, etc.)
  - [ ] Support sorting

- [ ] **API-006**: Additional endpoints
  - [ ] `/api/keywords` - List all keywords
  - [ ] `/api/keywords/<id>/codes` - Codes for a keyword
  - [ ] `/api/statistics` - Site statistics

### 11.3 API Documentation
**Dependencies**: API-003, API-004, API-005 complete
**Status**: 🔴 BLOCKED

- [ ] **API-007**: API documentation
  - [ ] Use Swagger/OpenAPI specification
  - [ ] Document all endpoints, parameters, responses
  - [ ] Provide example requests and responses
  - [ ] Host at `/api/docs` or similar

---

## Phase 12: Admin Interface

**Goal**: Create curator/admin interface for managing codes

### 12.1 Admin Dashboard
**Dependencies**: AUTH-002 complete
**Status**: ✅ DONE (2025-12-28)

- [x] **ADMIN-001**: Admin home page ✅ **COMPLETED 2025-12-28**
  - [x] Create route `/admin` (requires login)
  - [x] Dashboard overview (published/unpublished view counts)
  - [x] Quick links to admin functions (unpublished/archived)
  - [x] Login/logout functionality with session management
  - [x] Hardened auth: Upgraded to bcrypt password hashing (work factor 12)
  - [ ] Recent activity log (deferred)
  - [ ] CSRF protection (future enhancement)
  - [ ] Role-based access control (future enhancement)

- [x] **ADMIN-002**: Public statistics dashboard ✅ **COMPLETED 2025-12-28**
  - [x] Created route `/dashboard` (public-facing, no login required)
  - [x] Display comprehensive statistics:
    - [x] Total codes, citations, views, keywords, links
    - [x] Codes added by year with bar chart visualization
    - [x] Most viewed codes (top 10)
    - [x] Most cited codes (top 10)
    - [x] Recently added codes (top 10)
    - [x] Top keywords (top 20)
    - [x] Metadata completeness (missing DOI/bibcode)
  - [x] Modern, responsive design with styled sections
  - [x] Added custom Jinja2 filter `number_format` for thousands separators
  - **Implementation**: `controllers/dashboard.py`, `templates/dashboard.html`
  - [ ] Admin-only version with additional statistics (future enhancement)

### 12.2 Code Management (Admin)
**Dependencies**: ADMIN-001 complete, MODEL-002 complete
**Status**: 🟢 IN PROGRESS

- [ ] **ADMIN-003**: List unpublished codes
  - [x] Create route `/admin/unpublished`
  - [x] Query codes where status='unpublished'
  - [x] Display list (basic table, links to detail)
  - [ ] Add edit/publish/delete actions and bulk ops
  - [ ] Add pagination and filtering

- [ ] **ADMIN-004**: List archived codes
  - [x] Create route `/admin/archived`
  - [x] Query codes where status='archived'
  - [x] Display list (basic table, links to detail)
  - [ ] Add restore/unarchive action
  - [ ] Add pagination and filtering

- [ ] **ADMIN-005**: Insert new code
  - [ ] Create route `/admin/insert_code`
  - [ ] Form to enter all code fields
  - [ ] Save to database
  - [ ] Trigger phpBB forum post (if integration maintained)

- [ ] **ADMIN-006**: Update existing code
  - [ ] Create route `/admin/update_code/<id>`
  - [ ] Load existing code data
  - [ ] Form to edit all fields
  - [ ] Save changes
  - [ ] Log changes to `change` table

- [ ] **ADMIN-007**: Delete code
  - [ ] Create route `/admin/delete_code/<id>`
  - [ ] Confirmation dialog
  - [ ] Soft delete (set status='deleted') or hard delete
  - [ ] Handle foreign key constraints

- [ ] **ADMIN-008**: Archive/unarchive code
  - [ ] Create route `/admin/archive_code/<id>`
  - [ ] Toggle archived status
  - [ ] Update database

### 12.3 Utility Pages (Admin)
**Dependencies**: ADMIN-001 complete
**Status**: 🔴 BLOCKED

- [ ] **ADMIN-009**: Utility pages from v3
  - [ ] `/code/utility/ascl` - Table of all codes
  - [ ] `/code/utility/ascl2` - Simple two-column code list
  - [ ] `/code/utility/ascl3` - Text format code list
  - [ ] `/code/utility/arxiv` - Codes with arXiv references
  - [ ] `/code/utility/links` - List of all links
  - [ ] `/code/utility/links/repos` - Repository links only
  - [ ] `/code/utility/links2` - Links in table format
  - [ ] `/code/utility/site_links` - Site links only
  - [ ] `/code/utility/emails` - Email addresses
  - [ ] `/code/utility/codes_with_notes` - Codes with notes
  - [ ] `/code/utility/dois` - Codes with DOIs
  - [ ] `/code/utility/citation_method` - Citation methods
  - [ ] `/code/utility/reference_list` - Reference lists
  - [ ] `/code/utility/usage_list` - Usage statistics
  - [ ] `/code/utility/wrnote` - Research note report
  - [ ] `/code/utility/wrnote2` - Research note report with citations

### 12.4 Admin Dashboard Statistics
**Dependencies**: ADMIN-001 complete
**Status**: ✅ DONE (2025-12-28)

- [x] **ADMIN-010**: Public statistics dashboard ✅ **COMPLETED 2025-12-28**
  - [x] Create route `/dashboard`
  - [x] Display public-facing statistics:
    - [x] Total codes, citations, views
    - [x] Codes added by year
    - [x] Most viewed/cited codes
    - [x] Recently added codes
    - [x] Top keywords
    - [x] Codes missing metadata (DOI/bibcode)
  - [x] Charts and visualizations (bar charts for codes by year)
  - [ ] Citations by year and journal (future enhancement)
  - [ ] Prolific authors (future enhancement)
  - [ ] Link checking status (future enhancement)
  - **Note**: See ADMIN-002 above for full implementation details

---

## Phase 13: Template System

**Goal**: Modularize templates for easy theme swapping

### 13.1 Template Structure
**Dependencies**: None
**Status**: 🟡 READY

- [ ] **TMPL-001**: Base template system
  - [ ] Create `base.html` template
  - [ ] Define template blocks (header, content, footer, sidebar, etc.)
  - [ ] Set up template inheritance

- [ ] **TMPL-002**: Header/navigation template
  - [ ] Create `header.html` include/macro
  - [ ] Site logo and tagline
  - [ ] Main navigation menu (Home, About, Browse, etc.)
  - [ ] Search box
  - [ ] User menu (Login/Logout)

- [ ] **TMPL-003**: Footer template
  - [ ] Create `footer.html` include/macro
  - [ ] Social media links
  - [ ] Copyright and license information
  - [ ] Contact information
  - [ ] Page rendering time (optional)

### 13.2 Template Macros & Components
**Dependencies**: TMPL-001 complete
**Status**: 🔴 BLOCKED

- [ ] **TMPL-004**: Reusable components
  - [ ] Pagination macro
  - [ ] Code listing macro (for browse, search results)
  - [ ] Keyword tag macro
  - [ ] Citation display macro
  - [ ] Alert/message macro (success, error, warning)

- [ ] **TMPL-005**: Form components
  - [ ] Form field macro (with labels, errors, help text)
  - [ ] Button macro
  - [ ] Search form macro

### 13.3 Styling & Assets
**Dependencies**: None
**Status**: 🟡 READY

- [ ] **TMPL-006**: CSS organization
  - [ ] Create main stylesheet structure
  - [ ] Match v3 look and feel (or design new theme)
  - [ ] Responsive design (mobile-friendly)
  - [ ] Print stylesheet

- [ ] **TMPL-007**: JavaScript functionality
  - [ ] Search autocomplete (if desired)
  - [ ] Form validation
  - [ ] Interactive elements (collapsible sections, etc.)
  - [ ] Analytics tracking (Google Analytics or alternative)

- [ ] **TMPL-008**: Static assets
  - [ ] Favicon
  - [ ] Logo images
  - [ ] Social media icons
  - [ ] robots.txt

### 13.4 Theme System
**Dependencies**: TMPL-001, TMPL-002, TMPL-003 complete
**Status**: 🔴 BLOCKED

- [ ] **TMPL-009**: Modular theme architecture
  - [ ] Create theme directory structure
  - [ ] Allow theme selection via config
  - [ ] Document how to create new themes
  - [ ] Create "classic" theme matching v3
  - [ ] Create "modern" theme (optional)

---

## Phase 14: Testing & Quality

**Goal**: Ensure code quality and functionality

### 14.1 Unit Tests
**Dependencies**: Various, per component
**Status**: 🟡 READY

- [ ] **TEST-001**: Database model tests
  - [ ] Test ASCLCode model CRUD operations
  - [ ] Test relationships (aliases, keywords, citations)
  - [ ] Test PHP deserialization helpers
  - [ ] Test validation functions

- [ ] **TEST-002**: View/controller tests
  - [ ] Test homepage loads correctly
  - [ ] Test code detail page loads
  - [ ] Test browse pagination
  - [ ] Test search functionality
  - [x] Test WordPress-backed about page loads (added /about test)
  - [ ] Test API endpoints

- [ ] **TEST-003**: Form validation tests
  - [ ] Test code submission form validation
  - [ ] Test login form validation
  - [ ] Test admin forms

### 14.2 Integration Tests
**Dependencies**: Major features complete
**Status**: 🔴 BLOCKED

- [ ] **TEST-004**: End-to-end tests
  - [ ] Test full user workflows:
    - [ ] Submit a code → curator edits → publish → view on site
    - [ ] Search for code → view details → export formats
    - [ ] Browse by keyword → filter → view code

- [ ] **TEST-005**: Database integrity tests
  - [ ] Test foreign key constraints work
  - [ ] Test data consistency
  - [ ] Test transaction rollback scenarios

### 14.3 Performance Testing
**Dependencies**: Most features complete
**Status**: 🔴 BLOCKED

- [ ] **TEST-006**: Load testing
  - [ ] Test with full dataset (~4,400 codes)
  - [ ] Measure page load times
  - [ ] Identify slow queries
  - [ ] Optimize database queries
  - [ ] Add query result caching where appropriate

- [ ] **TEST-007**: Stress testing
  - [ ] Test concurrent users
  - [ ] Test API rate limiting (if implemented)
  - [ ] Ensure connection pool sizing is adequate

### 14.4 Code Quality
**Dependencies**: None
**Status**: 🟡 READY

- [ ] **TEST-008**: Code linting and formatting
  - [ ] Set up Black for code formatting
  - [ ] Set up Flake8 or Ruff for linting
  - [ ] Set up mypy for type checking
  - [ ] Configure pre-commit hooks

- [ ] **TEST-009**: Security audit
  - [ ] SQL injection prevention (use parameterized queries)
  - [ ] XSS prevention (template auto-escaping)
  - [ ] CSRF protection (Flask-WTF)
  - [ ] Password security (bcrypt/Argon2, not SHA-1)
  - [ ] Secure session configuration
  - [ ] HTTPS enforcement in production

---

## Phase 15: Deployment & DevOps

**Goal**: Deploy to production and set up monitoring

### 15.1 Production Environment
**Dependencies**: Most features complete
**Status**: 🔴 BLOCKED

- [ ] **DEPLOY-001**: Server setup
  - [ ] Set up production server (VPS or cloud)
  - [ ] Install Python, Nginx, MySQL
  - [ ] Configure firewall (ufw or iptables)
  - [ ] Set up SSL certificate (Let's Encrypt)

- [ ] **DEPLOY-002**: Application deployment
  - [ ] Create systemd service for Uvicorn
  - [ ] Configure Nginx reverse proxy
  - [ ] Set up static file serving
  - [ ] Configure environment variables
  - [ ] Test deployment with staging data

- [ ] **DEPLOY-003**: Database migration
  - [ ] Plan downtime window
  - [ ] Back up production database
  - [ ] Apply schema changes (InnoDB conversion, PKs, FKs)
  - [ ] Verify data integrity
  - [ ] Test application with production data

### 15.2 Monitoring & Logging
**Dependencies**: DEPLOY-002 complete
**Status**: 🔴 BLOCKED

- [ ] **DEPLOY-004**: Application monitoring
  - [ ] Set up error tracking (Sentry or alternative)
  - [ ] Configure application logging
  - [ ] Set up log rotation
  - [ ] Monitor disk space

- [ ] **DEPLOY-005**: Performance monitoring
  - [ ] Set up uptime monitoring (UptimeRobot or similar)
  - [ ] Monitor response times
  - [ ] Monitor database performance
  - [ ] Set up alerts for issues

### 15.3 Backup & Recovery
**Dependencies**: DEPLOY-001 complete
**Status**: 🔴 BLOCKED

- [ ] **DEPLOY-006**: Backup strategy
  - [ ] Set up automated database backups
  - [ ] Set up application file backups
  - [ ] Store backups off-site
  - [ ] Document restore procedure
  - [ ] Test restore procedure

### 15.4 CI/CD Pipeline
**Dependencies**: TEST-001, TEST-002 complete
**Status**: 🔴 BLOCKED

- [ ] **DEPLOY-007**: Automated testing
  - [ ] Set up GitHub Actions or similar
  - [ ] Run tests on every commit
  - [ ] Run linting and formatting checks

- [ ] **DEPLOY-008**: Automated deployment
  - [ ] Set up staging environment
  - [ ] Automated deployment to staging
  - [ ] Manual or automated deployment to production
  - [ ] Rollback procedure

---

## Phase 16: Documentation

**Goal**: Comprehensive documentation for users and developers

### 16.1 User Documentation
**Dependencies**: Features complete
**Status**: 🔴 BLOCKED

- [ ] **DOC-001**: User guide
  - [ ] How to search for codes
  - [ ] How to submit a code
  - [ ] How to request changes to a code
  - [ ] How to cite codes
  - [ ] FAQ

- [ ] **DOC-002**: API documentation
  - [ ] API endpoints reference
  - [ ] Authentication guide
  - [ ] Example requests and responses
  - [ ] Rate limiting (if implemented)

### 16.2 Developer Documentation
**Dependencies**: Code complete
**Status**: 🔴 BLOCKED

- [ ] **DOC-003**: Development setup guide
  - [ ] Prerequisites
  - [ ] Installation steps
  - [ ] Configuration options
  - [ ] Running tests

- [ ] **DOC-004**: Architecture documentation
  - [ ] System architecture diagram
  - [ ] Database schema documentation
  - [ ] Code organization
  - [ ] Key design decisions

- [ ] **DOC-005**: Contribution guide
  - [ ] How to contribute
  - [ ] Code style guidelines
  - [ ] Pull request process
  - [ ] Issue reporting

### 16.3 Operations Documentation
**Dependencies**: Deployment complete
**Status**: 🔴 BLOCKED

- [ ] **DOC-006**: Deployment guide
  - [ ] Server requirements
  - [ ] Deployment steps
  - [ ] Configuration reference
  - [ ] Troubleshooting common issues

- [ ] **DOC-007**: Maintenance guide
  - [ ] Backup and restore procedures
  - [ ] Database maintenance
  - [ ] Log management
  - [ ] Security updates

---

## Additional Tasks

### Citation & Metadata Scripts

- [ ] **SCRIPTS-001**: Rewrite citation import scripts for efficiency
  - [x] **Issue identified** (2025-12-10): Current scripts (`ascl_citations.py`, `ascl_citations_fast.py`) use inefficient truncate/rebuild approach
    - **Problems**:
      - Destroys `created_at`/`updated_at` timestamps every run (can't track citation growth over time)
      - Deletes and reinserts ~18,700 citation rows even if only 1-2% changed
      - Creates brief window where citation tables are empty (race condition for concurrent queries)
      - No change tracking (can't identify new vs existing citations, or detect removed citations)
      - No audit trail for citation changes
    - **Impact**: Analytics on citation growth impossible, wasteful database load, no historical tracking

  - [x] **SCRIPTS-001a**: Rewrite `ascl_citations_fast.py` for incremental updates (2025-12-10)
    - [x] New script: `ascl_citations_fast_incremental.py` (Python 3.6+)
    - [x] Use upsert logic: insert new citations, update existing, optionally track removed
    - [x] Preserve `created_at` timestamps (know when citation first appeared)
    - [x] Update `updated_at` only for changed records
    - [x] Minimal database writes (only process changed records)
    - [x] Works with CURRENT production schema (entry_asclid, no FKs)
    - [x] Add `--dry-run` flag for testing
    - [x] Add detailed statistics (new, updated, unchanged, removed)
    - [x] **SAFE**: Only touches `citations` and `ads_entries_new` tables

  - [ ] **SCRIPTS-001b**: Update citation script for new schema (post-migration)
    - [ ] Modify script to use `code_pk` instead of `entry_asclid`
    - [ ] Take advantage of FK constraints for data integrity
    - [ ] Update for InnoDB-specific optimizations
    - [ ] Test with ascl_db_v4 schema
    - [ ] **Blocked by**: CUTOVER-002 (production database migration)

  - [ ] **SCRIPTS-001c**: Similar efficiency improvements for other scripts
    - [ ] Review `link_checker_fast.py` for similar inefficiencies
    - [ ] Review `citefile_metadata_fast.py` for similar inefficiencies
    - [ ] Review `described_in_citations.py` for similar inefficiencies
    - [ ] Apply incremental update pattern where appropriate

- [x] **SCRIPTS-002**: ADS API Error Investigation (2025-12-10)
  - [x] **Current Error**: `ads.exceptions.APIResponseError: "Not found"`
  - [x] Investigated ADS API changes (endpoint, query syntax, authentication)
  - [x] Verified `bibstem:ascl.soft` query still valid (confirmed working as of 2024)
  - [x] Created diagnostic script: `test_ads_api.py`
  - [x] Created troubleshooting guide: `ADS_API_TROUBLESHOOTING.md`

  **ROOT CAUSE IDENTIFIED**: Most likely **missing or invalid API key** on production server

  **Evidence**:
  - Dev server has NO API key configured (expected - different environment)
  - Production server error "Not found" is consistent with missing/invalid API key
  - ads library version 0.12.7 (current as of Dec 2024) - no deprecation
  - Query syntax `bibstem:ascl.soft` still valid per ASCL documentation (2022-2024)
  - ADS API docs confirm authentication required via `~/.ads/dev_key` or `ADS_DEV_KEY` env var

  **ACTIONABLE NEXT STEPS** (must be done on PRODUCTION server):
  1. Run diagnostic script: `python3 ~/scripts/test_ads_api.py`
  2. If API key missing: Get key from https://ui.adsabs.harvard.edu/user/settings/token
  3. Save to `~/.ads/dev_key` with `chmod 600`
  4. Re-run diagnostic to confirm fix
  5. Test incremental script: `python3 ascl_citations_fast_incremental.py --dry-run`
  6. If successful, run production: `python3 ascl_citations_fast_incremental.py`

  **Resources Created**:
  - `~/ascl_scripts/scripts/test_ads_api.py` - Diagnostic script
  - `~/ascl_scripts/scripts/ADS_API_TROUBLESHOOTING.md` - Troubleshooting guide
  - See guides for detailed step-by-step instructions

### Miscellaneous

- [ ] **MISC-001**: phpBB Forum Restoration & Discourse Migration

  **Goal**: Restore phpBB forum for archival viewing and migrate to modern Discourse platform

  **Backups Available**:
  - Database: `~/repositories/ASCL/db_backups/ascl_phpbb-database-backup-2025.12.02.sql.gz`
  - Files: `~/repositories/ASCL/db_backups/ascl_phpBB3_files-2025.12.03-backup.bzip2`

  **Scripts**:
  - `alt_ascl/v3_to_v4_migration/restore_phpbb_backup.sh` - Restore phpBB database to Docker MySQL (port 3307)
  - `alt_ascl/v3_to_v4_migration/setup_discourse_from_phpbb.sh` - Setup Discourse + import phpBB data

  ### phpBB Restoration (Read-Only Archive)

  **Status as of 2025-12-09**: ✅ Database restored, ⚠️ Original phpBB has CSS/template issues

  - [x] Restore phpBB database to Docker MySQL:
    - [x] Run: `./alt_ascl/v3_to_v4_migration/restore_phpbb_backup.sh`
    - [x] Verify database: `mysql --defaults-group-suffix=_ascl_root -h 127.0.0.1 -P 3307 -e "USE ascl_phpbb; SELECT COUNT(*) FROM phpbb_users;"`
    - [x] **Result**: 533 users, 3,982 posts restored successfully

  - [x] Extract phpBB files:
    - [x] Extract: `tar -xjf db_backups/ascl_phpBB3_files-2025.12.03-backup.bzip2 -C ~/ASCL/phpbb/`
    - [x] Update `phpBB3/config.php` with Docker MySQL credentials (host=host.mysql:3307)
    - [x] **Location**: Moved to `~/ASCL/phpbb/` (non-code directory)

  - [x] Test phpBB access:
    - [x] Docker container created: `phpbb_web` (PHP 7.4 + Apache, port 8888)
    - [x] **Issue**: Template rendering broken, empty `<head>` section, no CSS
    - [x] **Workaround**: Created simple viewer at `~/ASCL/phpbb-viewer/`

  - [x] **Alternative Solution: phpBB Simple Viewer** (2025-12-09)
    - [x] Location: `~/ASCL/phpbb-viewer/` (3 PHP files: index.php, forum.php, topic.php)
    - [x] Reads directly from `ascl_phpbb` database (bypasses broken phpBB templates)
    - [x] Provides: Forum list, topic list, post view with clean minimal UI
    - [x] Running on http://localhost:8888 (PHP built-in server)
    - [x] **Status**: ✅ Working, read-only, temporary solution
    - [x] **Usage**: `cd ~/ASCL/phpbb-viewer && php -S localhost:8888`
    - [x] **Reversible**: Original phpBB preserved at `~/ASCL/phpbb/`, can switch back anytime

  **Notes**:
  - Original phpBB has PHP 7.4/8 compatibility issues (Zend Framework warnings, template cache problems)
  - Simple viewer is **temporary** until Discourse migration
  - Database is intact and ready for Discourse import
  - No integration with Flask v4 planned (standalone archive only)

  ### Discourse Setup & Import
  - [ ] Setup Discourse with Docker Compose:
    - [ ] Run: `./alt_ascl/v3_to_v4_migration/setup_discourse_from_phpbb.sh`
    - [ ] Verify services running: `cd alt_ascl/discourse && docker-compose ps`
    - [ ] Verify Discourse accessible at http://localhost:45888
  - [ ] Verify phpBB → Discourse import:
    - [ ] Check import logs: `cd alt_ascl/discourse && docker-compose logs discourse | grep -i import`
    - [ ] Login to Discourse (demitri@nightlightresearch.com / changeme_discourse_admin_123)
    - [ ] Verify users imported (Admin → Users)
    - [ ] Verify categories imported (Forum homepage)
    - [ ] Verify posts/threads imported (browse categories)
    - [ ] Verify attachments/avatars imported (if phpBB files backup was present)
  - [ ] Configure Discourse settings:
    - [ ] Verify read-only mode enabled (Admin → Settings → Login → "read only mode enabled")
    - [ ] Update site title/description (Admin → Settings → Required)
    - [ ] Configure site logo/favicon (Admin → Customize → Themes)
    - [ ] Test guest access (logout and browse forum as guest)
  - [ ] Performance & maintenance:
    - [ ] Verify database backups: `cd alt_ascl/discourse && docker-compose exec postgres pg_dump discourse > backup.sql`
    - [ ] Document container management commands (start/stop/logs/rebuild)
    - [ ] Set up automatic backups (cron job or systemd timer)

  ### Future: Discourse Integration (Optional)
  - [ ] Decision: Integrate Discourse with Flask app or keep standalone?
  - [ ] If integrating:
    - [ ] Implement SSO between Flask and Discourse (DiscourseConnect)
    - [ ] Add forum link to Flask app navigation
    - [ ] Embed Discourse comments on code detail pages (optional)
    - [ ] Make Discourse publicly accessible (configure firewall, Nginx reverse proxy)
  - [ ] If standalone:
    - [ ] Document Discourse as read-only archive for internal reference only
    - [ ] Consider periodic exports to static HTML for long-term archival

- [ ] **MISC-002**: Email functionality
  - [ ] Set up email server configuration (SMTP)
  - [ ] Test email sending for:
    - [ ] Code submission confirmations
    - [ ] Curator notifications
    - [ ] Password reset (if implementing)

- [ ] **MISC-003**: Analytics
  - [ ] Implement page view tracking
  - [ ] Track code detail page views (store in database)
  - [ ] Track search queries for analysis
  - [ ] Privacy-friendly analytics (avoid Google Analytics if desired)

- [ ] **MISC-004**: Accessibility
  - [ ] WCAG 2.1 AA compliance

### PHP-Serialized Data Cleanup
- [x] **DATA-010**: Identify and replace PHP-serialized columns
  - [x] Document tables/columns storing PHP-serialized strings:
    - `codes.site_list`
    - `codes.ref_list`
    - `codes.described_in`
    - `codes.used_in`
    - `codes.see_also`
    - `codes.keywords`
    - `codes.notes` (mixed content, includes serialized in places)
  - [x] Add parsing in Flask app as interim fix (described_in parsing added)
  - [x] Plan schema/data migration to structured JSON or relational tables (link fields → link table)
  - [ ] Update application to use migrated structures
  - [ ] Screen reader testing
  - [ ] Keyboard navigation
  - [ ] Alt text for images

- [x] **DATA-011**: Migrate PHP-serialized link fields to link table
  - [x] Update DB_UPGRADE_PLAYBOOK.sql with Step 8:
    - [x] Add `short_name` and `description` columns to `link_type` table
    - [x] Insert new link types: 'Code Site', 'Described In', 'Used In', 'Reference'
    - [x] Rename `links_new` table to `link` (singular, matching Python class naming)
    - [x] Update all subsequent references from `links_new` to `link`
  - [x] Create Python migration script: `agents/migrate_php_links_to_table.py`
    - [x] Reads PHP-serialized fields: `site_list`, `described_in`, `used_in`, `ref_list`
    - [x] Unpacks URLs using phpserialize library
    - [x] Creates new rows in `link` table with appropriate `link_type_pk`
    - [x] Supports --dry-run and --limit flags for testing
  - [x] Update ASCLModelClasses.py: Rename `LinkNew` class to `Link`
  - [ ] Run migration script on development database:
    - [ ] Test with `--dry-run --limit 10` first
    - [ ] Review output and verify correctness
    - [ ] Run full migration: `python3 agents/migrate_php_links_to_table.py`
    - [ ] Verify link count and data integrity
  - [ ] Update Flask application to use `link` table instead of parsing PHP fields
  - [ ] Add database cleanup step to drop PHP-serialized columns (after verification):
    - [ ] `ALTER TABLE codes DROP COLUMN site_list;`
    - [ ] `ALTER TABLE codes DROP COLUMN ref_list;`
    - [ ] `ALTER TABLE codes DROP COLUMN described_in;`
    - [ ] `ALTER TABLE codes DROP COLUMN used_in;`

- [ ] **MISC-005**: Internationalization (i18n)
  - [ ] If desired: Set up Flask-Babel
  - [ ] Mark strings for translation
  - [ ] Provide translations (languages TBD)

---

## Migration Cutover Checklist

When ready to switch from v3 to v4:

- [ ] **CUTOVER-001**: Pre-migration
  - [ ] Announce maintenance window
  - [ ] Back up all databases (ascl_db, WordPress)
  - [ ] Back up all files (code assets, WordPress uploads)
  - [ ] Test backup restore procedure

- [ ] **CUTOVER-002**: Database migration
  - [ ] Apply schema changes (InnoDB, PKs, FKs)
  - [ ] Verify data integrity
  - [ ] Run migration scripts if needed

- [ ] **CUTOVER-003**: Application deployment
  - [ ] Deploy v4 application
  - [ ] Configure DNS/reverse proxy
  - [ ] Test all major features
  - [ ] Monitor error logs

- [ ] **CUTOVER-004**: Post-migration
  - [ ] Verify site is accessible
  - [ ] Test submission form
  - [ ] Test admin functions
  - [ ] Monitor performance
  - [ ] Address any issues

- [ ] **CUTOVER-005**: Decommission v3
  - [ ] Keep v3 running in parallel for period (1 week? 1 month?)
  - [ ] Archive v3 codebase
  - [ ] Remove v3 from production server

---

## Notes for AI Agents

### Development Environment Setup
- **Database Connection**: MySQL 8.0 in Docker container on **port 3307** (not standard 3306)
- **Database**: `ascl_db_v4` (upgraded database with InnoDB, FKs, and code_pk migration)
- **Connection Config**: `alt_ascl/ascl_core/database/connections/Trillian2DBConnection.py`
  - **Note**: Points to `ascl_db_v4` database (changed from `ascl_db` on 2025-12-01)
  - **Metadata Caching**: Disabled during active development (`cache_name=None`)
- **Credentials**: Read from `~/.my.cnf` (MySQL) with `[client_ascl]` section
- **Development Approach**: Make changes freely on dev database, no production downtime concerns
- **Production Config**: Will need separate `ProductionDBConnection.py` for production deployment
- **v3→v4 DB refresh steps**:
  1) `./alt_ascl/v3_to_v4_migration/copy_ascl_database.sh` (excludes legacy tables)
  2) `mysql --defaults-group-suffix=_ascl -h 127.0.0.1 -P 3307 < alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql`
  3) `python3 alt_ascl/agents/migrate_php_links_to_table.py` (unpack PHP-serialized link fields → link table)
- **Database Change Logging**: Record every schema or data change in `alt_ascl/agents/DB_UPGRADE_PLAYBOOK.sql` so the process can be replayed from a fresh production dump; keep this playbook up to date.

### Key File Locations
- **PHP v3 app**: `/home/demitri/repositories/ASCL/ascl_php_application/`
- **Flask v4 app**: `/home/demitri/repositories/ASCL/alt_ascl/`
- **ascl_core module**: `/home/demitri/repositories/ASCL/ascl_core/`
- **dm-dbcore module**: `/home/demitri/repositories/ASCL/dm-dbcore/`
- **Database schema**: `/home/demitri/repositories/ASCL/ascl_php_application/ascl_db-schema-2025-10-30.sql`
- **Database backup**: `/home/demitri/repositories/ASCL/alt_ascl/ascl_db_2025.09.30_bkup.sql.gz`
- **Dev DB Connection**: `/home/demitri/repositories/ASCL/alt_ascl/ascl_core/database/connections/Trillian2DBConnection.py`

### Important Conventions
- **ASCL ID format**: `YYMM.NNN` (e.g., `1404.008` = April 2014, entry #008)
  - Stored only in `codes.ascl_id` - used for display and search only
  - **All joins use `codes.pk` (integer) via `code_pk` columns in related tables**
- **Database**: `ascl_db_v4` (upgraded db with InnoDB, FKs, code_pk), `ascl_wordpress` (WordPress content)
- **PHP serialized fields**: `site_list`, `ref_list`, `described_in`, `used_in`, `keywords`
- Use `phpserialize` library to deserialize PHP data in Python
- **Foreign Key Pattern**: All related tables use `code_pk MEDIUMINT UNSIGNED` → `codes.pk` (not ascl_id)

### Critical Dependencies
1. Database must be converted to InnoDB before defining FKs
2. Primary keys must be defined before foreign keys
3. Foreign keys must be defined before fully implementing model relationships
4. Model relationships must work before implementing most web pages
5. PHP deserialization must work before code detail pages work correctly
6. WordPress connection must work before static pages work

### Testing Strategy
- Test each component as it's built
- Use actual production data from database backup
- Verify compatibility with both MySQL and PostgreSQL (for future migration)
- Test on both development and staging environments before production

---

**Last Updated**: 2025-12-01
**Version**: 1.2
**Maintainer**: Demitri Muna
**Changelog**:
- v1.2 (2025-12-01): Completed Phase 1.3 (Foreign Keys) and Phase 3.2 (Relationships)
  - Migrated all tables from `ascl_id` to `code_pk` for foreign keys (DB-008)
  - Defined all SQLAlchemy relationships in ASCLModelClasses.py (MODEL-002, MODEL-003)
  - Updated connection to use `ascl_db_v4` database
  - Disabled metadata caching during active development
  - All 7 relationships tested and working (aliases, keywords, ads_entries, links, citefile_metadata, changes, citations)
- v1.1.1 (2025-11-29): Corrected MySQL credentials section to `[client_ascl]` (not `[client]`)
- v1.1 (2025-11-29): Added development environment details (Docker MySQL on port 3307, Trillian2DBConnection.py)
- v1.0 (2025-11-29): Initial master TODO created
