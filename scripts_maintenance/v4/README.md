# v4 maintenance scripts

> **Target: the v4 site, database `ascl_db_v4`.**
> Nothing in this directory may read or write `ascl_db` (v3). See `../README.md`
> for why the two are not interchangeable.

This directory is currently empty of scripts. It exists so that v4 maintenance
jobs have an unambiguous home and are never confused with their v3 counterparts
in `../v3/`.

## Existing v4 maintenance code lives in `bin/`

The v4 link checker was written as a subcommand of the `ascl` management CLI
rather than a standalone cron script:

```bash
ascl linkcheck                    # database ascl_db_v4, link_type=code-site
ascl linkcheck --link-type all
ascl linkcheck -q                 # quiet — the mode intended for cron
```

Implementation: `bin/ascl_link_checker.py`. It writes the `link_check` table and
mirrors `is_working` / `last_working` back onto `link`. **It is not scheduled
yet** — see `docs/next-steps.md`.

Leave it in `bin/`; moving it would break the `ascl` subcommand wiring. Add a
pointer here instead when a v4 job is set up.

## Still to port from v3

| Job | v3 script | Notes |
|---|---|---|
| Citations from ADS | `../v3/ascl_citations.py` | writes `citations`, `ads_entries_new`; needs v4 table equivalents |
| codemeta / CITATION.cff detection | `../v3/citefile_metadata.py` | reads `codes.site_list`, which v4 dropped — must read the `link` table instead |

Both rewrites need the same schema translation: `codes.site_list`
(PHP-serialized) becomes a join against `link`, and `id` becomes `pk`.

## Conventions for scripts added here

- Default to `ascl_db_v4`, and accept a database name argument — dev deployments
  read `devascl_db_v4`, not `ascl_db_v4`.
- Take credentials from `~/.my.cnf`; never hardcode them.
- Quiet on success, so cron only mails on failure.
- Schedule through `../cron_wrap.sh` so runs land in the rolling log.
