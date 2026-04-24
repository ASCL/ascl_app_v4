# ASCL.net Flask Application (v4)

Flask rebuild of the [ascl.net](https://ascl.net) website, replacing the legacy PHP/CodeIgniter stack. The application reads content from both the ASCL database (codes, keywords, authors, links) and the existing WordPress database (about, submissions, resources pages, news/blog posts).

## Stack

- **Flask 3.0+** with Jinja2 templates
- **SQLAlchemy 2.0** ORM
- **MySQL 8.0** (v4 normalized schema for ASCL data; WordPress DB read-only)
- **Typesense** for full-text search (MySQL fulltext fallback)
- **Uvicorn** ASGI server (VPS) or **Phusion Passenger** (cPanel)

## Project Structure

```
alt_ascl/
├── bin/
│   ├── ascl                       # Management CLI
│   ├── ascl_typesense.py          # Typesense index management (subcommand)
│   ├── ascl_link_checker.py       # Async link checker (subcommand)
│   └── ascl_db_dump.sh            # Portable MySQL dump script
├── source/
│   └── ascl_net_app_project_home/ # Flask application
│       ├── ascl_net_app/
│       │   ├── __init__.py        # App factory (create_app)
│       │   ├── controllers/       # Route blueprints
│       │   ├── model/             # Database integration
│       │   ├── services/          # Typesense client, etc.
│       │   ├── templates/         # Jinja2 templates
│       │   ├── static/            # CSS, JS, images
│       │   └── configuration_files/
│       ├── deployments/           # Host-specific deploy artifacts
│       │   ├── passenger/         # passenger_wsgi.py for cPanel
│       │   ├── systemd/           # ascl_net_app.service unit file
│       │   ├── nginx/             # Reverse-proxy configs (dev + production)
│       │   └── uwsgi/             # uWSGI configuration (legacy)
│       ├── run_ascl_net_app.py    # Dev server entry point
│       ├── asgi.py                # Production ASGI entry point
│       └── requirements.txt
├── v3_to_v4_migration/            # Database migration scripts (v3 → v4)
├── tests/test_smoke.py            # Live-URL smoke tests
├── ENDPOINT_MAPPING.md            # v3 → v4 endpoint migration status
└── CLAUDE.md                      # Detailed technical documentation
```

This project depends on two sibling packages (installed as regular Python dependencies via `requirements.txt`):

- **ascl_core** — Shared module: DB singleton, SQLAlchemy ORM models
- **dm-dbcore** — Database core library

## Endpoint Status

39 of 54 v3 PHP endpoints are implemented, plus 28 v4-only additions. See [ENDPOINT_MAPPING.md](ENDPOINT_MAPPING.md) for the full mapping.

Highlights: code browsing and detail pages, unified search (Typesense + MySQL), data exports (JSON, XML, DCI, ADS), CodeMeta/CITATION.cff generation, news from WordPress, public dashboard, admin CRUD with bcrypt auth.

## Development

```bash
cd source/ascl_net_app_project_home

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run dev server (uses default.cfg)
python run_ascl_net_app.py --debug --port 5000

# List all registered routes
python run_ascl_net_app.py --rules
```

### Configuration

Flask config files live in `ascl_net_app/configuration_files/`. The app loads `default.cfg` first, then overlays an environment-specific config:

- **Debug mode** (`--debug`): uses `default.cfg` only (or hostname-specific overrides)
- **Production**: set `FLASK_CONFIG=ascl_net.cfg` (or another file) via environment variable

Secrets (`SECRET_KEY`, `ADS_API_TOKEN`, `TYPESENSE_API_KEY`) are loaded from a separate file not committed to the repo. In debug mode, the app looks for `configuration_files/secrets.cfg` as a fallback. See `secrets.cfg.example` for the template.

## Testing

Smoke tests verify every page loads without crashing. They hit a live URL over HTTP — no Flask internals or database imports needed.

```bash
# --base-url is required
pytest tests/test_smoke.py --base-url https://dev.ascl.net
pytest tests/test_smoke.py --base-url https://ascl.net
pytest tests/test_smoke.py --base-url http://localhost:5000

# Stop on first failure
pytest tests/test_smoke.py --base-url https://dev.ascl.net -x

# Include admin page tests (requires credentials)
pytest tests/test_smoke.py --base-url https://dev.ascl.net --admin-user <user> --admin-pass <pass>
```

**What's covered (100 tests):**

- All public pages: index, about, submissions, resources, explain, dashboard
- Code browsing: `/code/all`, `/code/all_by_id`, `/code/keywords`, `/code/alias_list`, `/code/random`, `/code/submit`
- Discover routes: similar, mentioned, domain, language, author
- Code detail, suggest-edit, alt detail
- Search: empty, with query, suggest, author suggest, credit search, adversarial input
- News: list, RSS feed, WordPress redirect
- Data exports: JSON, XML, DCI, OLE, ADS (with date/auth restrictions)
- CodeMeta and CITATION.cff generation
- Error handling: 404 page, bad parameters, stack trace suppression
- Static assets: favicon, robots.txt
- Security: all admin routes reject unauthenticated users
- **Admin pages** (with `--admin-user`/`--admin-pass`): every admin GET route renders without errors — dashboard, unpublished, archived, insert code, user CP, notes, corrections, code lists, utilities, broken links, icecave, and admin API endpoints

Without credentials, admin tests are skipped (not failed).

## `ascl` Management CLI

A single CLI for operating the application across deployment environments.

### Setup

```bash
# Symlink to PATH
sudo ln -s /path/to/alt_ascl/bin/ascl /usr/local/bin/ascl

# Tab completion (bash) — add to your completions directory or:
eval "$(ascl completions bash)"
```

On first run, if no config exists, the CLI creates a template at `~/.config/ascl/config.toml` (respects `$XDG_CONFIG_HOME`) and exits with instructions.

### Commands

```bash
ascl status [TARGET]                # Show app/service status
ascl restart [TARGET]               # Restart the running app
ascl redeploy [TARGET] [-f]         # Full redeploy: sync code + libs, install, restart
ascl config [TARGET]                # Show resolved config for a target
ascl test <URL> [--admin-user U --admin-pass P] [-x]
                                    # Run smoke tests against a live site
ascl dumpdb <DATABASE> [-o FILE]    # Dump a MySQL database to a dated .sql file
ascl typesense reset                # Drop collection, recreate schema, re-index
ascl typesense index                # (Re-)index all published codes
ascl typesense status               # Show collection info and document count
ascl linkcheck [DATABASE] [options] # Async link checker (see below)
ascl init [--force]                 # Create or overwrite config template
ascl completions bash|zsh           # Print shell completion script
```

`TARGET` defaults to `default_target` in the config file. Built-in targets are `vps` and `cpanel`, but any section name in the config works.

`ascl redeploy -f` overrides the uncommitted-changes guard on source repositories.

### Config

Each deployment target is a TOML section in `~/.config/ascl/config.toml`:

```toml
default_target = "vps"

# VPS — Nginx + Uvicorn + systemd
[vps]
restart_method = "systemd"
service_name   = "ascl_net_app"
repo_app       = "/home/user/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home"
deploy_app     = "/var/www/ascl_net_app"
run_as_user    = "www-data"
flask_config   = "ascl_net.cfg"
secrets_file   = "/etc/ascl/secrets.cfg"
typesense_url        = "http://127.0.0.1:8108"
typesense_collection = "codes"

# Optional library dependencies — rsynced and pip-installed on redeploy
[[vps.libs]]
repo   = "/home/user/repositories/ASCL/ascl_core"
deploy = "/var/www/ascl_core"

[[vps.libs]]
repo   = "/home/user/repositories/ASCL/dm-dbcore"
deploy = "/var/www/dm-dbcore"

# cPanel — Phusion Passenger
[cpanel]
restart_method = "passenger"     # touch tmp/restart.txt
repo_app       = ""              # leave empty if using git pull on the server
deploy_app     = "~/ascl.net"
flask_config   = "ascl_net.cfg"
ssh_host       = ""              # set for remote deploy from another machine
typesense_url        = ""
typesense_collection = "codes"
```

### What `ascl redeploy` does

**VPS (systemd):** abort if any tracked repo has uncommitted changes (override with `-f`), stop the service, rsync libs listed in `[[vps.libs]]`, rsync the app, set ownership, `uv pip install` libs + requirements, start the service.

**cPanel (Passenger):** rsync the app (local or over SSH via `ssh_host`), `pip install -r requirements.txt`, touch `tmp/restart.txt`.

Both modes exclude `venv/`, `.venv/`, `__pycache__/`, `.git/`, `*.egg-info`, `passenger_wsgi.py`, `secrets.cfg`, and `tmp/` from the rsync.

### `ascl test`

Runs the smoke-test suite (`tests/test_smoke.py`) against a live base URL. Admin tests run only if credentials are provided via `--admin-user`/`--admin-pass` or `$ASCL_ADMIN_USER`/`$ASCL_ADMIN_PASSWORD`.

```bash
ascl test https://dev.ascl.net
ascl test dev.ascl.net -x                       # Stop on first failure
ASCL_ADMIN_USER=admin ASCL_ADMIN_PASSWORD=... ascl test https://ascl.net
```

### `ascl dumpdb`

Dumps a MySQL database to `{name}_YYYY-MM-DD.sql`. Reads credentials from `~/.my.cnf [client_ascl_root]`, defaults to `127.0.0.1:3307`, uses `--databases` (includes `CREATE DATABASE IF NOT EXISTS` + `USE`), skips `DROP TABLE`, and patches `CREATE TABLE` to `CREATE TABLE IF NOT EXISTS`.

```bash
ascl dumpdb ascl_db_v4
ascl dumpdb ascl_db_v4 -o mybackup.sql --host 127.0.0.1 --port 3307
```

### `ascl linkcheck`

Async link checker for the v4 `link` table. Uses `httpx` + `pymysql`, writes per-link results into the `link_check` table (HTTP status, final URL after redirects, page `<title>`, domain-change flag, pattern-matched notes) and mirrors `is_working` / `last_working` back to `link`.

```bash
ascl linkcheck                              # Default DB (ascl_db_v4), link_type=code-site
ascl linkcheck --link-type all              # Check every link type
ascl linkcheck --retry-failed -i            # Only re-check previously failed links
ascl linkcheck --dry-run -v                 # Check without writing to DB
ascl linkcheck --concurrency 10             # Limit concurrency
```

Features:
- Per-domain rate limiting (max 2 in flight per domain, 0.5s spacing)
- Retries on 429/5xx with `Retry-After` support
- Treats 401/403/405/406/429 as "probably working" (bot-blocking)
- Detects Cloudflare challenges, bot checks, GitHub/GitLab/Bitbucket "not found"/"archived" pages, and parked-domain indicators
- Relaxes SSL verification on certificate errors so the site can still be reached
- Interactive progress display with live failure ticker (`-i` or `-v`); `-q` silences output for cron
- Reads DB credentials from `~/.my.cnf` (`[client_ascl]`, `[client_ascl_root]`, or `[client]`)

## cPanel Deployment

### Prerequisites

- cPanel account with **Setup Python App** and **MySQL Databases** access
- SSH access to the cPanel server

### Repository Access (GitHub Personal Access Tokens)

Because the cPanel account is **shared between developers**, SSH deploy keys aren't a good fit — a single key would give everyone the same GitHub access with no accountability, and rotating it would break every user at once. Instead, each developer clones and pulls over HTTPS using their own **GitHub Personal Access Token (PAT)**.

A PAT is a long string GitHub generates that acts as a substitute for your password at the git command line. You create it once (or once per expiration window), paste it as the password when git prompts, and you're done.

**One-time setup per developer:**

1. Sign in to GitHub with your own account.
2. Click your avatar in the top-right → **Settings**.
3. In the left sidebar, scroll all the way down to **Developer settings**.
4. Choose **Personal access tokens → Tokens (classic)**.
   *GitHub also offers newer "Fine-grained tokens", but those are scoped to a single organization or user account. Since this project pulls from the `ASCL` organization and also from a personal repo (`demitri/dm-dbcore`), one classic token is the simplest way to cover everything with a single credential.*
5. Click **Generate new token → Generate new token (classic)**. GitHub may ask you to confirm your password or 2FA code.
6. Fill in the form:
   - **Note**: a label so you can recognize it later, e.g. `cpanel-devascl-<yourname>`.
   - **Expiration**: pick a duration. 90 days is a safe default; 1 year is the maximum. Tokens on GitHub.com cannot be made non-expiring.
   - **Scopes**: tick **`repo`** (full control of private repositories). This is the minimum scope required to clone and pull from private repos.
7. Click **Generate token** at the bottom of the page.
8. **Copy the token immediately.** It looks like `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`. GitHub will show it only this once — if you lose it, you must generate a new one.

**Cloning the ASCL repos on cPanel:**

SSH into the cPanel account, then clone the three repos the deployment depends on:

```bash
cd ~
git clone https://github.com/ASCL/alt_ascl.git
git clone https://github.com/ASCL/ascl_core.git
git clone https://github.com/demitri/dm-dbcore.git
```

When git prompts for credentials:

- **Username**: your GitHub username
- **Password**: paste the PAT (not your GitHub account password)

**Avoid re-entering the token on every `git pull`.** Cache it with git's credential helper. Either on disk:

```bash
git config --global credential.helper 'store --file=~/.git-credentials'
# After the next successful git operation, lock the file down:
chmod 600 ~/.git-credentials
```

…or in memory only, cleared when the session ends:

```bash
git config --global credential.helper 'cache --timeout=28800'   # 8 hours
```

Because this is a shared account, anything written to `~/.git-credentials` is technically readable by other users of the account (if permissions slip). If that concerns you, use the in-memory cache, or clear the saved credential when you log out:

```bash
git credential reject https://github.com
```

**Token expiry and rotation:**

Tokens **expire**. When yours does, `git pull` starts failing with `HTTP 401 Unauthorized` (or `Authentication failed`). To rotate:

1. Generate a new token on GitHub by repeating the steps above.
2. Either edit the line for `github.com` in `~/.git-credentials` to contain the new token, or run `git credential reject https://github.com` and let the next git operation re-prompt you to paste it.

If a token is ever leaked (accidentally pasted into a message, committed to a repo, etc.), revoke it immediately from the same **Personal access tokens** page on GitHub. Revocation is instant, and because each developer has their own token, it does not affect anyone else.

### 1. Import the Database

Via cPanel's **MySQL Databases** interface:

1. **Create a database** (e.g. `ascl_db_v4`; cPanel will prefix it, e.g. `devascl_db_v4`)
2. **Create a database user** (e.g. `user`; cPanel will prefix it, e.g. `devascl_user`)
3. **Add the user to the database** — scroll to "Add User to Database", select the user and database, and grant **All Privileges**

Generate a portable dump from the source server (strips `CREATE DATABASE`/`USE`/`DEFINER` clauses and rewrites the database name):

```bash
# On the source server (e.g. trillian2)
bin/ascl_db_dump.sh -o ascl_db_v4_cpanel.sql -t devascl_db_v4
```

Transfer to the cPanel server and import:

```bash
mysql --defaults-file=~/.my.cnf devascl_db_v4 < ascl_db_v4_cpanel.sql
```

Create `~/.my.cnf` for password-less CLI access:

```ini
[client]
user=devascl_user
password=YOUR_DB_PASSWORD
host=localhost
port=3306
```

```bash
chmod 600 ~/.my.cnf
```

### 2. Create the Python App in cPanel

In **Setup Python App**, create a new application:

- **Python version**: 3.13
- **Application root**: `ascl_app_v4`
- **Application URL**: your domain
- **Application startup file**: `passenger_wsgi.py`
- **Application Entry point**: `application`

cPanel creates a virtualenv at `/itss/home/devascl/virtualenv/ascl_app_v4/3.13/`.

Activate it via SSH:

```bash
source /itss/home/devascl/virtualenv/ascl_app_v4/3.13/bin/activate && cd /itss/home/devascl/ascl_app_v4
```

### 3. Install Dependencies

```bash
pip install flask pymysql bcrypt requests nameparser phpserialize python-dotenv termcolor cryptography
```

The `ascl_core` and `dm-dbcore` packages must also be installed — see step 4.

### 4. Deploy Application Files

Copy the Flask application to the cPanel app directory:

```bash
# From the app directory on the server:
# ascl_app_v4/
#   ├── passenger_wsgi.py
#   ├── ascl_net_app/          (copy of source/ascl_net_app_project_home/ascl_net_app/)
#   ├── run_ascl_net_app.py    (optional, for CLI debugging)
#   └── tmp/
#       └── restart.txt        (touch to restart Passenger)
```

### 5. Create `passenger_wsgi.py`

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Pure-Python MySQL driver (no C compilation needed on shared hosting)
import pymysql
pymysql.install_as_MySQLdb()

os.environ['FLASK_CONFIG'] = 'ascl_net.cfg'

from ascl_net_app import create_app

application = create_app(debug=False)
```

### 6. Configure `ascl_net.cfg`

Update `ascl_net_app/configuration_files/ascl_net.cfg` with the cPanel-prefixed database credentials:

```ini
DB_DATABASE = 'devascl_ascl_db_v4'
DB_USER = 'devascl_dbuser'
DB_PASSWORD = 'your_password'
DB_HOST = 'localhost'
DB_PORT = '3306'
```

### 7. Secrets

On shared hosting you typically cannot write to `/etc/ascl/`. Instead, point to a file in your home directory by adding this to `passenger_wsgi.py` before the import:

```python
os.environ['ASCL_SECRETS_FILE'] = '/itss/home/devascl/secrets/secrets.cfg'
```

Or add the secrets directly to `ascl_net.cfg`:

```ini
SECRET_KEY = 'generate-a-real-random-key'
ADS_API_TOKEN = 'your-ads-token'
TYPESENSE_API_KEY = 'your-typesense-key'
```

### 8. Restart

```bash
touch /itss/home/devascl/ascl_app_v4/tmp/restart.txt
```

Or use the **Restart** button in cPanel's Python App interface.

### Logging

Flask application errors are logged to `~/ascl_app_v4/logs/app.log`.

## TODO

- [ ] Log rotation and reporting plan for `~/ascl_app_v4/logs/app.log`

## Documentation

- [ENDPOINT_MAPPING.md](ENDPOINT_MAPPING.md) — v3 → v4 endpoint migration status
- [CLAUDE.md](CLAUDE.md) — Architecture, database schema, configuration reference
- [source/ascl_net_app_project_home/deployments/README.md](source/ascl_net_app_project_home/deployments/README.md) — Deployment artifacts reference
- [source/ascl_net_app_project_home/DEPLOYMENT.md](source/ascl_net_app_project_home/DEPLOYMENT.md) — Production deployment guide
- [tests/test_smoke.py](tests/test_smoke.py) — Smoke tests for all public and admin pages

---

*Last Updated: 2026-04-14*
