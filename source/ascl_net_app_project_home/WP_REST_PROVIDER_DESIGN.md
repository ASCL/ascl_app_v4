# Design: WordPress Content Provider Abstraction (DB + REST)

**Status:** Proposed (not yet implemented) — revised after code-grounded review
**Date:** 2026-06-24
**Scope:** How the dev deployment (`devascl` cPanel account) reads WordPress content from the **production** WordPress (`ascl` account) without copying the WP database, while production continues to read its co-located WP DB directly.

---

## 1. Problem

The Flask app renders About / Submissions / Resources / Explain / News from the WordPress database. Today it reaches WordPress by writing **fully-qualified, cross-database table names** into SQL and executing them on the **same** SQLAlchemy engine used for the app DB:

```sql
FROM `devascl_wordpress`.`0hjpDo4yM_posts` p
JOIN `devascl_wordpress`.`0hjpDo4yM_users` u ON u.ID = p.post_author
```

This works **only** because the app DB (`ascl_db_v4`) and the WP DB live in the same MySQL instance under the same cPanel account, so one connection sees both schemas.

The dev account currently holds its **own copy** of the WP database. Keeping that copy in sync with the live site is a non-trivial, ongoing chore with little benefit. We want the dev app to read the **production** WordPress instead — across a hard cPanel account boundary — without relying on the two accounts sharing a server or a MySQL instance.

### Key constraint

Cross-database (`db1.table JOIN db2.table`) queries require both schemas to be visible to **one connection on one MySQL server**. A connection authenticated as the `devascl` MySQL user cannot see the `ascl` account's `ascl_wordpress` database, and if the accounts are ever on separate servers a single connection cannot span them at all. So direct-DB access across the boundary is rejected.

### Enabling fact

Every WordPress query in the app joins WP tables **only** to other WP tables (posts ↔ users ↔ terms ↔ comments). **No query joins WordPress to the v4 app tables** (`code`, `link`, `keyword`, `author`). Verified against `about.py`, `news.py`, `wordpress.py`. The WP data source is therefore cleanly separable from the app DB.

---

## 2. Decision

- **Production** keeps direct MySQL access to its co-located WordPress DB (unchanged behavior).
- **Dev** reads production WordPress over the **WordPress REST API** (`/wp-json/wp/v2/...`) via HTTPS — clean across the account boundary, no MySQL grants, no shared instance, survives the accounts ever being split across servers.
- The two access methods sit behind a **provider abstraction** that returns a **canonical, already-rendered DTO** (see §3.4) selected by config.
- **Dev is read-only** with respect to production WordPress. Comment *writes* always stay on the DB path (`WPDBProvider`); the REST path never writes (see §5).
- **No response cache.** Dev performance is explicitly a non-concern — but request fan-out is bounded and partial failures must fail loud, not silently truncate (see §4.7).

### 2.1 The rendered-vs-raw decision (load-bearing)

The current code reads **raw** `post_content` / `comment_content` and runs it through the app's own `wpautop()` port — which also expands `[caption]`/`[video]` shortcodes (`process_shortcodes`) and rewrites links (`rewrite_ascl_links`). Anonymous WordPress REST (`context=view`) returns **only** `content.rendered`, never `raw`; raw fields require `context=edit`, which requires authentication.

**Decision:** the REST path uses `content.rendered` and does **not** attempt to reconstruct raw content. This keeps the "anonymous, no secrets" premise. The consequence — and the rest of this doc follows from it — is that **rendering moves behind the provider boundary**: every provider returns already-rendered, link-rewritten HTML, and controllers stop calling `wpautop()` themselves. Authenticating for `context=edit` raw content was considered and rejected (it breaks the no-secrets premise for marginal fidelity gain).

---

## 3. Architecture

### 3.1 Provider interface (PROPOSED names → existing functions)

All WordPress access — currently raw SQL in private functions scattered across `ascl_net_app/controllers/about.py`, `ascl_net_app/controllers/news.py`, and `ascl_net_app/utilities/wordpress.py` — is collapsed behind one interface. **These method names are proposed, not existing** (only `insert_comment` matches a current name). The mapping the §7 refactor must follow:

| Proposed interface method | Existing function(s) |
|---|---|
| `get_page(id)` | `about.py:_fetch_wp_page` |
| `get_subpages(parent)` | `about.py:_fetch_subpages` (includes parent — see §4.3) |
| `list_posts(limit, offset, search, category, archive_month, author)` | `news.py:_fetch_posts` (+ `_build_post_filter_sql`) |
| `count_posts(search, category, archive_month, author)` | `news.py:_count_posts` |
| `get_post_by_slug(slug)` | `news.py:_fetch_post_by_slug` |
| `categories_for_posts(ids)` | `news.py:_fetch_categories_for_posts` |
| `recent_posts(limit)` | `news.py:_fetch_recent_posts` |
| `categories(limit)` | `news.py:_fetch_categories` |
| `archives(limit)` | `news.py:_fetch_archives` |
| `archive_posts(limit)` | `news.py:_fetch_archive_posts_by_month` |
| `comments(post_id)` | `wordpress.py:fetch_comments` (threaded tree) |
| `insert_comment(post_id, author, email, url, content, ip="", user_agent="")` | `wordpress.py:insert_comment` |

`news.py:_build_post_filter_sql` is an internal helper of `list_posts`/`count_posts`, not a public method. `news.py:_fetch_sidebar_data` is a controller-level composite of `recent_posts` + `categories` + `archives` + `archive_posts`; it stays in the controller and calls the interface.

**Note** the `insert_comment` signature includes `ip` and `user_agent` (passed from `news.py` as `request.remote_addr` / `User-Agent`); the interface must keep them.

After the refactor, controllers depend on this interface only — no `Database().db.engine.connect()` in `about.py` / `news.py`.

### 3.2 Implementations

- **`WPDBProvider`** — today's SQL, relocated behind the interface. Owns `wpautop()` (and therefore shortcode expansion + link rewriting). Production path; behavior-identical to today.
- **`WPRestProvider`** — `httpx` (already a dependency) against `{WP_REST_BASE_URL}/wp-json/wp/v2/...`, persistent client for keep-alive. Read endpoints are anonymous (no secrets). Dev path.

A small factory reads config and selects the provider, stashing it on the app (e.g. `app.extensions['wp']`).

### 3.3 Configuration

```ini
WP_SOURCE        = 'rest'                          # default 'db' when unset
WP_REST_BASE_URL = 'https://ascl.net/wordpress'    # required when WP_SOURCE='rest'
WP_READONLY      = True                            # default True when unset (fail-safe)
WP_LINK_REWRITE_HOST = 'dev.ascl.net'              # required on dev so REST links are rewritten
```

- `ascl_net.cfg` (production): `WP_SOURCE = 'db'` — direct DB, unchanged.
- `devascl_net.cfg` (dev): `WP_SOURCE = 'rest'`, `WP_REST_BASE_URL`, `WP_READONLY = True`, `WP_LINK_REWRITE_HOST`.

**Defaults are fail-safe:** absent `WP_SOURCE` ⇒ `db`; absent `WP_READONLY` ⇒ `True` (never default to writable). 

**Dead config to note (not introduced here):** `WP_DB_HOST` / `WP_DB_USER` / `WP_DB_PASSWORD` / `WP_DB_PORT` exist in configs but are read by **no** Python code — the WP DB path uses the main app engine via `wp_table()`, so they are inert. `WP_DB_DATABASE` and `WP_TABLE_PREFIX` *are* read (by `wp_table()`). The new keys above are the only ones the provider factory consumes.

### 3.4 Canonical DTO (resolves the parity contract)

Because `WPDBProvider` renders via `wpautop()` and `WPRestProvider` renders via WordPress core, the two cannot return identical *raw* structures. The interface therefore defines a **canonical dict** per entity, carrying **already-rendered, link-rewritten** HTML and normalized scalar types:

- Page: `{id, title, content_html, parent_id}`
- Post (list/detail): `{id, title, slug, date (datetime), author_name, author_slug, content_html, excerpt, categories: [{name, slug}]}`
- Comment node: `{id, author, author_url, date (datetime), content_html, children: [...]}`
- Category/archive entries: as today (`{name, slug, count}` / `{key, label, count}` / `{month_key: [{title, slug}]}`)

`content_html` is the post-`wpautop`/post-link-rewrite HTML for the DB path, and `content.rendered` + `rewrite_ascl_links()` for the REST path. Controllers render `content_html` directly and never call `wpautop()` after the refactor. Parity (§6) compares **normalized** DTOs, never byte-equal HTML.

---

## 4. REST mapping details

The REST API being reachable is binary and confirmed (`/wp-json/wp/v2/pages/2` returns on dev). The work is matching the *shape and semantics* of the SQL. `WPRestProvider` must handle:

### 4.1 Rendered content + link rewriting
Use `content.rendered` / `title.rendered` (shortcodes already expanded by WP core). Do **not** call `wpautop()`. **Must** still call `rewrite_ascl_links()` on the rendered HTML — `WP_REST_BASE_URL` points at production, so `content.rendered` contains absolute `https://ascl.net/...` links; without rewriting, dev pages link back to the live site (`wordpress.py:329` shows this runs only inside `wpautop()` today, which the REST path skips). `rewrite_ascl_links()` no-ops outside an app context (`wordpress.py:48`) — providers and tests must run within one.

### 4.2 Pagination & counts
`per_page` is capped at 100; totals come from `X-WP-Total` / `X-WP-TotalPages` headers. **Caveat:** these back `count_posts` only when no search term is set — REST `search` uses WP relevance tokenization, so `X-WP-Total` and the result set differ from the SQL `LIKE '%q%'` / `COUNT(DISTINCT)` baseline (§4.5). Document the search divergence as accepted on dev, or add a custom route.

### 4.3 Subpages (must re-add the parent)
`about.py:_fetch_subpages` selects `WHERE post_parent = :parent OR ID = :parent` and pins the parent first via `CASE WHEN ID = :parent THEN -1`, then `menu_order ASC, ID ASC`. REST `pages?parent=<id>&orderby=menu_order&order=asc` returns **children only**. The provider must fetch the parent separately (`get_page`) and prepend it, preserving the `ID ASC` tiebreaker, or the current/root page disappears from nav.

### 4.4 Category cloud
The `categories` endpoint returns a `count` field per term (published-post count). For the sidebar cloud, match `_fetch_categories`' `hide_empty`, `orderby=count desc, name asc`, and limit semantics explicitly.

### 4.5 Filters resolve to IDs, not slugs
SQL filters category by `t.slug` and author by `au.user_nicename` (`news.py:_build_post_filter_sql`). REST `posts` filters want integer `categories=` / `author=` IDs. The provider must resolve slug→ID first (`categories?slug=`, `users?slug=`), with explicit handling: **unknown slug ⇒ return empty result, never all posts**; the anonymous `users` endpoint only lists users with published posts (others 401/omitted). Archive-month filtering has no equivalent `DATE_FORMAT` filter — see §4.6.

### 4.6 Archives — custom WP route (option chosen)
`archives()` / `archive_posts()` are `GROUP BY YEAR(post_date), MONTH(post_date)` aggregations with no core REST endpoint. Client-side bucketing is rejected: with `per_page≤100` it requires walking the entire post history (dozens of sequential prod requests per sidebar render) and `_fetch_archive_posts_by_month`'s correlated subquery is not expressible client-side. **Decision: add a small custom WP REST route** that returns month buckets, computed on `post_date` (site-local — REST's `date` field, *not* `date_gmt`) to match the SQL baseline.

### 4.7 Request fan-out (correctness, not just speed)
A single `/news` render today is a handful of SQL queries; naively over REST it fans out to: list (1) + per-post categories (~10) + slug→ID lookups + sidebar (recent, categories, archives). Mitigations: use `_embed` so the list call returns embedded `wp:term` categories in one request (replacing the N+1 `categories_for_posts`), and use the custom archive route (§4.6). Uncached against production, unbounded fan-out invites `429`; multi-request loops (comments, any paged fetch) must treat a mid-loop failure as an error, **not** return a partial (silently truncated) result.

### 4.8 Comments — page all, re-sort, rebuild tree, filter type
`fetch_comments` orders `comment_date ASC`, filters `comment_approved='1' AND comment_type IN ('comment','')`, and builds a **threaded tree** via `comment_parent` (`wordpress.py:344-378`); it also runs `wpautop()` on each comment body. REST `comments?post=<id>` defaults to flat, `orderby=date_gmt`, `order=desc`, `per_page=10`. The provider must: (a) page through **all** approved comments (a single page can place a child before its parent → replies orphaned as top-level), (b) pass `type=comment` to exclude pingbacks/trackbacks, (c) re-sort ascending and rebuild the parent/child tree, (d) return `content_html` from `content.rendered` (already rendered — do not re-`wpautop`).

---

## 5. Read-only enforcement

Production comment writes stay on the DB path (`WPDBProvider.insert_comment`), so **REST comment-write auth/nonce is never needed in production** — it is a test-only concern.

On the dev/REST path, writes are refused, **fail-safe and fail-loud**:
- `WP_READONLY` defaults to `True` when absent (§3.3) — a missing key never enables writes.
- The provider **raises** (not silent no-op) on a blocked write, and the controller (`news.py:post_comment`) is updated to **disable/reject the comment form** when read-only rather than calling `insert_comment` and redirecting as if it succeeded.
- Read-only is bound to the REST provider and additionally refuses to write when `WP_REST_BASE_URL` is a production host, so `WP_READONLY` and `WP_REST_BASE_URL` being independent knobs cannot combine into a write against production.

The write path remains testable by pointing `WP_REST_BASE_URL` at the disposable dev WP install with `WP_READONLY = False`.

---

## 6. Error contract

REST introduces a failure class that in-instance SQL never had. Each provider method defines explicit behavior so controllers keep working and a production hiccup degrades gracefully (no cache + dev→prod means transient prod errors otherwise 500 every dev page):

- `404` ⇒ `None` for single-entity getters (so `about.py` / `news.py` still `abort(404)` rather than 500).
- `403` / `429` / `5xx` / timeout / invalid JSON ⇒ method-defined empty/`None`, surfaced as an empty section, never a bubbled `httpx` exception.
- Multi-request loops (§4.7, §4.8) ⇒ a mid-loop failure raises/aborts the whole method rather than returning a partial result.

---

## 7. Testability

The existing **stale dev WP install** is repurposed from a content source into a **test oracle**: it exposes both a MySQL DB and a REST API over the *same* data, so the two providers can be run against the same install and diffed. Staleness is irrelevant for parity — any *difference* between providers over the same install is an adapter bug.

Test infrastructure: a `pytest` suite exists under `ascl_net_app/tests/` with `conftest.py`. `pytest` / `pytest-flask` are listed (commented) in `requirements.txt` and would be enabled. **`ascl_net_app/tests/fixtures/wp/` does not exist yet — it is net-new work.**

Three layers:

1. **Unit (offline, CI-safe).** Captured WP JSON fixtures under `ascl_net_app/tests/fixtures/wp/`, mocked `httpx`. Assert `WPRestProvider` produces the canonical DTO (§3.4). Run within an app context so `rewrite_ascl_links()` is exercised (it no-ops otherwise → false green).
2. **Contract (`@pytest.mark.integration`, on-demand).** Hit the live dev WP REST API; confirm real payloads still parse. Catches WP/plugin changes fixtures wouldn't.
3. **Parity (the oracle).** Run `WPDBProvider` and `WPRestProvider` against the same dev WP install; assert equivalent **normalized** DTOs per page/post — normalize HTML (parse/strip) before comparing, never byte-equality.

```python
def test_rest_matches_db_for_about_page(db_provider, rest_provider):
    assert normalize(rest_provider.get_page(2)) == normalize(db_provider.get_page(2))
```

**Caveat on the existing guard:** `tests/test_public_pages.py` reaches the WP DB *directly* (imports `WordpressDBConnection`, hardcoded `0hjpDo4yM_` prefix) to fetch oracle values, then asserts the rendered page contains them. It validates the **step-1 DB refactor** but is **not** a REST guard: once `devascl_net.cfg` flips to `rest`/prod (step 5), it compares dev-DB titles against production-rendered content and will mislead. It must be decoupled (or pinned to the parity-oracle install) before the cutover.

---

## 8. Implementation sequence

1. Extract the interface; move existing SQL into `WPDBProvider` and move `wpautop()` ownership into it (behavior-identical — guarded by `tests/test_public_pages.py`, which exercises `/about`, `/submissions`, `/news`, `/news/<slug>`).
2. Add the factory + config keys (§3.3); default to `db` (no behavior change anywhere).
3. Build the parity oracle + test layers (§7) **and** `WPRestProvider` together — interleaved, not provider-first — so each mapping (§4) is driven to faithfulness against the oracle as it's written.
4. Decouple `test_public_pages.py` from the direct-DB oracle (§7 caveat).
5. Flip `devascl_net.cfg` to `rest` + read-only. First moment dev points at production — gated on §9's prod `/wp-json/` check. Keep `WP_SOURCE='db'` as the documented rollback.

---

## 9. Prerequisites

- ✅ `/wp-json/` exposed on dev WP — `wp/v2/pages/2` returns, so the `wp/v2` namespace is live.
- ✅ `httpx` already a dependency; `pytest` available to enable.
- ⛔ **Hard blocker:** confirm production WP (`ascl.net/wordpress`) exposes `/wp-json/` for **all** resources actually used (pages, posts by slug/id, categories, users/authors, comments, pagination headers) — not just `/pages/2`. The whole REST path depends on it; security plugins often lock down subsets of the REST API.

---

## 10. Rejected / deferred alternatives

- **`context=edit` for raw REST content.** Would let the REST path keep the local `wpautop()`/shortcode pipeline, but requires authentication — breaks the "anonymous, no secrets" premise (§2.1). Rejected.
- **Client-side archive bucketing.** Rejected in favor of a custom WP route (§4.6) — `per_page≤100` makes full-history scans per render operationally untenable.
- **Direct cross-account MySQL grant (same server).** Smallest change, but depends on root/WHM, is operationally brittle (cPanel account operations can re-sync grants), and dies if the accounts ever move to separate servers. Rejected for durability.
- **Remote MySQL across servers.** Semantically the closest match (cross-database joins keep working), but requires Remote-MySQL whitelisting, a remote grant, firewall/bind changes, plus a second engine anyway, and does not honor the "hard division" as cleanly. Deferred.
- **Response cache (TTL).** Out of scope — dev performance is a non-concern; a cache would obscure parity testing. (Bounding request fan-out per §4.7 is a separate, retained concern.)
