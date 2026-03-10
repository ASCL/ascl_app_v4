# ASCL Endpoint Mapping: v3 (PHP) → v4 (Flask)

This document maps every endpoint from the v3 PHP/CodeIgniter application to its v4 Flask equivalent.

**Architectural decision (2026-03-09):** The REST API and data export endpoints will be
implemented as Flask blueprints within the main app (not a separate service). Production
runs on shared cPanel with Phusion Passenger, which supports one Python app per
domain/subdomain. A separate `api.ascl.net` subdomain remains an option if needed later.

*Last Updated: 2026-03-10*

---

## Public Pages

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/` | `/` | Homepage with recent additions | [x] | |
| `/about` | `/about` | About page | [x] | WordPress content fetched via DB |
| `/submissions` | `/submissions` | Submission guidelines | [x] | WordPress content fetched via DB |
| `/resources` | `/resources` | Resources page | [x] | WordPress content fetched via DB |
| `/explain` | `/explain` | Explanation page | [x] | WordPress content fetched via DB |
| `/getwp/{id}` | `/getwp/<page_id>` | Generic WordPress page fetcher | [x] | |

## Code Browsing & Viewing

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/code` | — | Code browsing landing page | [ ] | No separate landing page in v4 |
| `/code/all` | `/code/all` | Browse all codes (paginated) | [x] | |
| `/code/all_by_id` | `/code/all_by_id` | Browse codes by ASCL ID | [x] | |
| `/code/search/{term}` | `/search?q={term}` | Search codes by keyword | [x] | v4 uses query param instead of path |
| `/code/cs/{term}` | `/code/cs/<search_term>` | Credit/author search | [x] | |
| `/code/keywords` | `/code/keywords` | Browse keyword cloud | [x] | |
| `/code/keywords/{keyword}` | `/code/keywords/<keyword>` | Filter by keyword | [x] | |
| `/code/alias_list` | `/code/alias_list` | Code alias listing | [x] | |
| `/code/random` | `/code/random` | Redirect to random code | [x] | |
| `/{ascl_id}` | `/<ascl_id>` | View individual code detail | [x] | Handles aliases and redirects |

## Code Submission & Editing

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/code/submit` | `/code/submit` | Guest code submission form | [x] | |
| `/code/edit/{id}` | — | Edit submitted code (session-based) | [ ] | Guest editing of own submission |
| `/code/change/{id}` | — | Request changes to existing code | [ ] | Public change request form |

## Data Export Formats

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/code/json` | `/code/json` | Export all codes as JSON | [x] | |
| `/code/xml` | `/code/xml` | Export 100 most recent as XML | [x] | |
| `/code/dci` | `/code/dci` | Export all codes as XML | [x] | |
| `/code/dci/{date}` | `/code/dci/<date>` | Export codes updated since date | [x] | |
| `/code/ole/{date}` | `/code/ole/<date>` | JSON export for Alice (auth req) | [x] | 1-month restriction for guests |
| `/code/ads/{date}` | `/code/ads/<date>` | Plain text format for ADS import | [x] | 1-month restriction for guests |

## CodeMeta & Citation Files

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/{ascl_id}/codemeta.json` | `/<ascl_id>/codemeta.json` | CodeMeta 2.0 JSON export | [x] | Uses v4 author table |
| `/{ascl_id}/CITATION.cff` | `/<ascl_id>/CITATION.cff` | Citation File Format (CFF) | [x] | Uses v4 author table |
| `/{ascl_id}/citation.cff` | `/<ascl_id>/citation.cff` | Redirect to CITATION.cff | [x] | 301 redirect |

## Webhooks

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/webhooks/manual` | — | Manual CodeMeta submission form | [ ] | |
| `/webhooks/manual_submit` | — | Process CodeMeta submission | [ ] | |

## Search & Suggest (v4 additions)

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| — | `/search` | Full-text search (Typesense + MySQL) | [x] | v4 unified search page |
| — | `/search/suggest` | JSON type-ahead suggestions | [x] | v4 only |
| — | `/search/author_suggest` | JSON author type-ahead | [x] | v4 only |

## API

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/api/search` | — | RESTful search API (Basic Auth) | [ ] | |

## News / Blog

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| WordPress blog | `/news` | News listing with pagination | [x] | v4 reads WP posts from DB |
| WordPress post | `/news/<slug>` | News post detail | [x] | |
| — | `/news/feed` | RSS 2.0 feed | [x] | v4 only |
| — | `/news/<slug>/comment` | Comment submission | [x] | v4 only |
| — | `/wordpress` | 301 redirect to `/news` | [x] | v4 only |

## Dashboard & Statistics

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/dashboard` | `/dashboard` | Public statistics dashboard | [x] | |

## Admin — Authentication

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/adm` | `/admin/` | Admin home / login page | [x] | |
| — | `/admin/login` | Login POST handler | [x] | bcrypt + SHA-1 migration |
| — | `/admin/logout` | Logout handler | [x] | |
| — | `/admin/user_cp` | User profile page | [x] | v4 only |
| — | `/admin/update_user` | Update user profile | [x] | v4 only |
| — | `/admin/update_password` | Change password | [x] | v4 only |

## Admin — Code Management

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/adm/unpublished` | `/admin/unpublished` | List unpublished codes | [x] | |
| `/adm/archived` | `/admin/archived` | List archived codes | [x] | |
| `/adm/insert_code` | `/admin/insert_code` | Insert new code | [x] | |
| `/adm/update_code/{id}` | `/admin/update_code/<pk>` | Edit existing code | [x] | |
| `/adm/delete_code/{id}` | `/admin/delete_code/<pk>` | Delete code | [x] | |
| `/adm/archive_code/{id}` | `/admin/archive_code/<pk>` | Toggle archive status | [x] | |
| `/adm/dash` | `/admin/dashboard` | Admin dashboard | [x] | Renders public dashboard in admin layout |
| — | `/admin/view/<pk>` | View code (admin read-only) | [x] | v4 only |
| — | `/admin/notes/attention` | Codes with flagged notes | [x] | v4 only |
| — | `/admin/codes/awaiting-ids` | Codes awaiting ASCL IDs | [x] | v4 only |
| — | `/admin/codes/missing-citation-method` | Codes missing citation method | [x] | v4 only |
| — | `/admin/codes/missing-described-used` | Codes missing described/used-in | [x] | v4 only |
| — | `/admin/codes/submitted-by-authors` | Author-submitted codes | [x] | v4 only |

## Admin — Utility Pages (Require Login)

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| `/code/utility/ascl` | `/admin/utility/full_table` | Full table of all codes | [x] | |
| `/code/utility/ascl2` | `/admin/utility/simple_table` | Simple two-column code list | [x] | |
| `/code/utility/ascl3` | — | Text format code list | [ ] | |
| `/code/utility/arxiv` | — | Codes with arXiv references | [ ] | |
| `/code/utility/links` | `/admin/utility/all_links` | All links as plain text | [x] | |
| `/code/utility/links/repos` | — | Repository links only | [ ] | |
| `/code/utility/links2` | — | Links in table format | [ ] | |
| `/code/utility/site_links` | `/admin/utility/site_links` | Site links only | [x] | |
| `/code/utility/emails` | — | Email addresses | [ ] | |
| `/code/utility/codes_with_notes` | — | Codes with notes | [ ] | Partially covered by `/admin/notes/attention` |
| `/code/utility/dois` | — | Codes with DOIs | [ ] | |
| `/code/utility/citation_method` | — | Citation methods | [ ] | |
| `/code/utility/reference_list` | — | Reference lists | [ ] | |
| `/code/utility/usage_list` | — | Usage statistics | [ ] | |
| `/code/utility/wrnote` | — | Research note report | [ ] | |
| `/code/utility/wrnote2` | — | Research note report + citations | [ ] | |

## Admin — Internal API (v4 only)

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| — | `/admin/api/check_ascl_id/<id>` | Check if ASCL ID exists (JSON) | [x] | |
| — | `/admin/api/next_ascl_id` | Get next available ASCL ID (JSON) | [x] | |
| — | `/admin/api/keyword_count/<kw>` | Keyword usage count (JSON) | [x] | |
| — | `/admin/api/check_alias/<alias>` | Check if alias exists (JSON) | [x] | |
| — | `/admin/api/typesense_status` | Typesense index status (JSON) | [x] | |
| — | `/admin/api/normalize_name` | Normalize author name (JSON) | [x] | |
| — | `/admin/api/check_url` | Validate URL accessibility (JSON) | [x] | |
| — | `/admin/api/bibcode_info/<bib>` | ADS bibcode lookup (JSON) | [x] | |
| — | `/admin/api/note_types` | Get note type list (JSON) | [x] | |
| — | `/admin/api/code/<pk>/notes` | Get/create code notes (JSON) | [x] | GET + POST |
| — | `/admin/api/note/<pk>/toggle_pin` | Toggle note pinned state (JSON) | [x] | |
| — | `/admin/api/note/<pk>/toggle_hidden` | Toggle note hidden state (JSON) | [x] | |

## Error Handling

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| Any 404 | `/<ascl_id>` catch-all | Custom 404 with ASCL ID matching | [x] | v4 catch-all route handles this |

## Static / Misc

| v3 PHP Endpoint | v4 Flask Endpoint | Description | Done | Notes |
|---|---|---|---|---|
| — | `/favicon.ico` | Favicon | [x] | |
| — | `/robots.txt` | Robots.txt | [x] | |

---

## Summary

| Category | v3 Total | Implemented in v4 | Not Yet |
|---|---|---|---|
| Public Pages | 6 | 6 | 0 |
| Code Browsing | 10 | 10 | 0 |
| Code Submission/Edit | 3 | 1 | 2 |
| Data Export | 6 | 6 | 0 |
| CodeMeta/CFF | 3 | 3 | 0 |
| Webhooks | 2 | 0 | 2 |
| API | 1 | 0 | 1 |
| Dashboard | 1 | 1 | 0 |
| Admin Auth | 1 | 1 | 0 |
| Admin Code Mgmt | 6 | 6 | 0 |
| Admin Utilities | 14 | 4 | 10 |
| Error Handling | 1 | 1 | 0 |
| **Total v3 endpoints** | **54** | **39** | **15** |
| v4-only additions | — | 28 | — |
