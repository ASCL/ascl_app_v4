# Production Deployment Guide

Step-by-step walkthrough for bringing up the ASCL.net Flask application in production. Two deployment targets are supported and can be used interchangeably for the same code:

- **cPanel + Phusion Passenger** — production host for `ascl.net` and `dev.ascl.net`
- **VPS** — Nginx + Uvicorn (4 workers) + systemd, for self-hosted environments

Both are driven by the `bin/ascl` CLI. For day-to-day commands (`restart`, `redeploy`, `status`, `test`, `dumpdb`, `typesense`, `linkcheck`) see the top-level [README.md](../../README.md). For env-variable / credentials details see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Shared prerequisites

1. **MySQL 8.0** with the v4 database (`ascl_db_v4`) imported. See the top-level README for the portable dump procedure (`bin/ascl_db_dump.sh` → import on the target host).
2. **`~/.my.cnf`** on the app host with a `[client_ascl]` (or `[client_ascl_root]`) section:
   ```ini
   [client_ascl]
   host     = 127.0.0.1
   port     = 3306            # VPS dev uses Docker on 3307
   user     = ascl_user
   password = ...
   database = ascl_db_v4
   ```
   `chmod 600 ~/.my.cnf`.
3. **Secrets file** (`SECRET_KEY`, `ADS_API_TOKEN`, `TYPESENSE_API_KEY`) at `/etc/ascl/secrets.cfg` (VPS) or `~/secrets/secrets.cfg` (cPanel). The app refuses to start in production if any required secret is missing. See `ascl_net_app/configuration_files/secrets.cfg.example`.
4. *(Optional)* **Typesense** running locally or on a reachable host. Without it, search falls back to MySQL fulltext.

---

## cPanel + Passenger

### 1. Create the Python app in cPanel

In **Setup Python App**:
- Python: 3.13
- Application root: `ascl_app_v4`
- Application startup file: `passenger_wsgi.py`
- Application Entry point: `application`

cPanel creates a virtualenv at `/itss/home/<account>/virtualenv/ascl_app_v4/3.13/`. Activate it over SSH and install dependencies:

```bash
source /itss/home/<account>/virtualenv/ascl_app_v4/3.13/bin/activate
cd /itss/home/<account>/ascl_app_v4
pip install flask pymysql bcrypt requests nameparser phpserialize \
            python-dotenv termcolor cryptography httpx typesense
```

Also install the two sibling packages (`ascl_core`, `dm-dbcore`) from the repo you rsync in the next step.

### 2. Deploy application files

From your workstation, configure a `cpanel` target in `~/.config/ascl/config.toml` (see README) and run:

```bash
ascl redeploy cpanel
```

This rsyncs `ascl_net_app/` + libs to the cPanel host, pip-installs, and touches `tmp/restart.txt`. Excluded from the sync: `passenger_wsgi.py`, `secrets.cfg`, `tmp/`, venvs, `__pycache__`.

### 3. Install the Passenger entry point

Copy `deployments/passenger/passenger_wsgi.py` to the cPanel app root once (it's host-specific, so it's not rsynced automatically). Typical contents:

```python
import os, sys, pymysql
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
pymysql.install_as_MySQLdb()  # pure-Python MySQL — no compilation on shared hosts
os.environ['FLASK_CONFIG']         = 'ascl_net.cfg'
os.environ['ASCLDB_MYCNF_SECTION'] = 'client_ascl'
os.environ['ASCL_SECRETS_FILE']    = '/itss/home/<account>/secrets/secrets.cfg'
from ascl_net_app import create_app
application = create_app(debug=False)
```

### 4. Configure `ascl_net.cfg`

In `ascl_net_app/configuration_files/ascl_net.cfg`, set the cPanel-prefixed DB credentials (cPanel prefixes accounts, e.g. `devascl_ascl_db_v4`, `devascl_dbuser`). Do not put secrets here — they live in `secrets.cfg`.

### 5. Restart

```bash
ascl restart cpanel      # or: touch ~/ascl_app_v4/tmp/restart.txt
```

### 6. Logs

Flask logs to `~/ascl_app_v4/logs/app.log`. Passenger stderr goes to cPanel's error log viewer.

---

## VPS (Nginx + Uvicorn + systemd)

### 1. systemd unit

Install the unit file once:

```bash
sudo cp deployments/systemd/ascl_net_app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ascl_net_app
```

The service binds Uvicorn to `127.0.0.1:5050` with 4 workers and logs to `/var/log/ascl_v4_uvicorn.log`. Environment variables (`FLASK_CONFIG`, `ASCLDB_MYCNF_SECTION`, etc.) are set inside the unit file — see `deployments/systemd/ascl_net_app.service`.

### 2. Nginx reverse proxy

```bash
sudo cp deployments/nginx/nginx_production.cfg /etc/nginx/sites-available/ascl_production
sudo ln -s /etc/nginx/sites-available/ascl_production /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Nginx proxies port 80 → Uvicorn on 5050 and serves `/static/` directly from the deploy directory.

### 3. Deploy code

Configure the `vps` target in `~/.config/ascl/config.toml`, then:

```bash
sudo ascl redeploy vps
```

This aborts on uncommitted repo changes (override with `-f`), stops the service, rsyncs the app + any `[[vps.libs]]` entries into `/var/www/`, sets ownership to `www-data`, `uv pip install`s, and restarts.

### 4. HTTPS (recommended)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain
```

After enabling TLS, set `SESSION_COOKIE_SECURE = True` in the Flask config and `ascl restart vps`.

### 5. Managing the service

```bash
ascl status vps               # systemctl status ascl_net_app
ascl restart vps              # systemctl restart ascl_net_app
sudo journalctl -u ascl_net_app -f
```

---

## Post-deployment checks

Smoke tests hit the live URL over HTTP — no Flask internals needed:

```bash
ascl test https://ascl.net
ascl test https://dev.ascl.net -x
ASCL_ADMIN_USER=... ASCL_ADMIN_PASSWORD=... ascl test https://ascl.net
```

Admin tests are skipped (not failed) when no credentials are supplied.

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| App won't start | `journalctl -u ascl_net_app -f` (VPS) or `~/ascl_app_v4/logs/app.log` (cPanel) |
| `KeyError: SECRET_KEY` at startup | Secrets file missing or `ASCL_SECRETS_FILE` pointing at the wrong path |
| 502 Bad Gateway | Uvicorn not running — `ascl status vps` |
| DB "Access denied" | Wrong `ASCLDB_MYCNF_SECTION` or `~/.my.cnf` permissions not 600 |
| Search returns MySQL-style results | Typesense unreachable — `ascl typesense status` |
| Passenger didn't pick up changes | `touch ~/ascl_app_v4/tmp/restart.txt` (or `ascl restart cpanel`) |

---

## Security checklist

- [x] Secrets externalized to a file outside the repo; startup validation enforced
- [x] Admin passwords hashed with bcrypt (SHA-1 legacy hashes auto-upgraded on login)
- [x] Session cookies HTTP-only; `SameSite=Lax`
- [x] DB credentials in `~/.my.cnf` (mode 600), never in code
- [x] App bound to `127.0.0.1` (VPS) — all public traffic via Nginx/Passenger
- [ ] HTTPS enabled (strongly recommended; Let's Encrypt on VPS, cPanel AutoSSL on shared hosting)
- [ ] CSRF protection on admin forms (TODO)
- [ ] Rate limiting on `/admin/login` (TODO)
