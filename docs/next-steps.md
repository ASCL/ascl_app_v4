# Next Steps

Active punch list. For the full v3 → v4 endpoint map see [`ENDPOINT_MAPPING.md`](../ENDPOINT_MAPPING.md); for architecture see [`CLAUDE.md`](../CLAUDE.md).

## High priority

### Security hardening
- CSRF protection on admin forms
- Rate limiting on `/admin/login`
- Role-based access control (admin / curator / user) — currently a single admin role
- HTTPS on all deployment targets; set `SESSION_COOKIE_SECURE = True`

### Exports & API
- Verify `/code/ads/<date>` plain-text export matches v3 output byte-for-byte
- REST API as a Flask blueprint (not a separate service) — see `CLAUDE.md` architectural decision
  - `/api/search` with authentication as the first endpoint

### Link checker follow-up
- Scheduled run (cron or systemd timer) of `ascl linkcheck` in quiet mode against `ascl_db_v4`
- Admin review UI on top of the `link_check` table (domain changes, pattern-matched notes)
- Log rotation plan for `~/ascl_app_v4/logs/app.log` (noted in README TODO)

## Medium priority

- Port remaining v3 admin utilities flagged in `ENDPOINT_MAPPING.md`
- Typesense: verify re-index cadence and add a health check endpoint the dashboard can surface
- Monitoring / alerting (Sentry hook is already scaffolded; just needs DSN)

## Future enhancements

- Faceted search UI
- Activity log surfaced in the admin UI
