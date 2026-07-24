# v3 maintenance scripts

> **Target: the v3 site, database `ascl_db`.**
> Nothing in this directory reads or writes `ascl_db_v4`. See `../README.md`
> for why aiming these at v4 fails outright.

These are the jobs currently keeping the **live production site** up to date.

## Scripts

| File | Reads | Writes | Credentials | Requires |
|---|---|---|---|---|
| `ascl_citations.py` | NASA ADS API | `citations`, `ads_entries_new` | **hardcoded** ⚠️ | `ads`, `peewee`, ADS key at `~/.ads/dev_key` |
| `link_checker_async.py` | `codes.site_list` | `links_new` | `~/.my.cnf` `[client_ascl]` | Python 3.13+, `httpx`, `pymysql`, `phpserialize` |
| `citefile_metadata.py` | `codes.site_list`, GitHub | `citefile_metadata` | **hardcoded** ⚠️ | `requests`, `pymysql` |
| `phpserialize.py` | — | — | — | vendored dependency of the link checker |
| `test_ads_api.py` | NASA ADS API | — | — | ADS connectivity check |

⚠️ `ascl_citations.py` and `citefile_metadata.py` both carry a plaintext
database password in source. Pending cleanup — move to `~/.my.cnf`
`[client_ascl]`, matching what `link_checker_async.py` already does, and rotate
the credential (it is in git history).

## What the dashboard shows

The v3 dashboard's "N site links (X%) are working as of DATE" line takes DATE
from the newest `links_new.updated_at`
(`ascl_php_application/.../controllers/dashboard.php:85`).

`link_checker_async.py` stamps `updated_at = now` on **every** row it touches —
insert and both update branches — so there is no "nothing changed, skip" path.
That date therefore advances on any successful run, and a frozen date means the
job is not completing, not that it found nothing to do.

One known wrinkle: the dashboard counts only HTTP `200` as working
(`dashboard.php:129`) while the checker treats `{200, 202}` as working. The
displayed percentage is slightly pessimistic as a result.
