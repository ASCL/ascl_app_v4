# v3 maintenance scripts

> **Target: the v3 site, database `ascl_db`.**
> Nothing in this directory reads or writes `ascl_db_v4`. See `../README.md`
> for why aiming these at v4 fails outright.

These are the jobs currently keeping the **live production site** up to date.

## Scripts

| File | Reads | Writes | Requires |
|---|---|---|---|
| `ascl_citations.py` | NASA ADS API | `citations`, `ads_entries_new` | `ads`, `peewee`, ADS key at `~/.ads/dev_key` |
| `link_checker_async.py` | `codes.site_list` | `links_new` | Python 3.13+, `httpx`, `pymysql`, `phpserialize` |
| `citefile_metadata.py` | `codes.site_list`, GitHub | `citefile_metadata` | `requests`, `pymysql` |
| `db_config.py` | `~/.my.cnf` | — | shared credential loader |
| `phpserialize.py` | — | — | vendored dependency of the link checker |
| `test_ads_api.py` | NASA ADS API | — | ADS connectivity check |

## Credentials

All three scripts get their database credentials from `~/.my.cnf` via
`db_config.py`. No password appears in source.

```ini
[client_ascl]
user     = ascl_db
password = <the password>
host     = localhost
database = ascl_db
```

`chmod 600 ~/.my.cnf`. The `[client_ascl]` section is preferred and `[client]`
is the fallback; `database` is optional and defaults to `ascl_db`.

> **The old password is still in git history** (commit `b6e96ef` and earlier,
> pushed to GitHub). Removing it from the working tree does not remove it from
> the repository — it must be rotated in MySQL to actually be revoked.

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
