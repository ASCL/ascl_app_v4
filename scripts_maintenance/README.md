# scripts_maintenance

Scheduled maintenance scripts, **split by which site and database they target.**

```
scripts_maintenance/
├── v3/    → the v3 site,  database `ascl_db`      (currently in production)
├── v4/    → the v4 site,  database `ascl_db_v4`
├── cron_wrap.sh      shared cron wrapper + rolling log (used by both)
└── crontab.example   the production crontab
```

## Read this before touching anything here

**A v3 script pointed at v4 (or vice versa) fails immediately — it does not
silently do the wrong thing, and it does not partially work.** The two schemas
diverged in ways that break the very first query:

| | v3 (`ascl_db`) | v4 (`ascl_db_v4`) |
|---|---|---|
| Code URLs | `codes.site_list`, PHP-serialized | `link` table, normalized |
| Link results | `links_new` table | `link_check` table |
| Primary keys | `id` | `pk` |

The v4 migration **dropped** `codes.site_list` (step 11) and never created
`links_new`. So every v3 script here dies on its opening `SELECT` if aimed at v4.

The whole directory lives in the **v4 repository** only because that repo is the
checkout deployed on the production host. Directory location says nothing about
which schema a script targets — the `v3/` and `v4/` subdirectories do.

## Which is which

| Job | v3 | v4 |
|---|---|---|
| Link checking | `v3/link_checker_async.py` | `bin/ascl_link_checker.py` (`ascl linkcheck`) |
| Citations from ADS | `v3/ascl_citations.py` | not yet ported |
| codemeta / CITATION.cff detection | `v3/citefile_metadata.py` | not yet ported |

See `v3/README.md` and `v4/README.md` for per-script detail.

## Scheduling

All jobs run under `cron_wrap.sh`, which logs every run to
`~/ascl_app_v4/logs/cron/`. To check whether a job actually ran:

```bash
tail -n 20 ~/ascl_app_v4/logs/cron/cron_history.log
```

**cron does not read `~/.bash_profile`.** `~/bin` is therefore absent from
cron's PATH, and a bare `python` will not resolve to `~/bin/python` the way it
does in an interactive shell. Always give cron an absolute interpreter path.
