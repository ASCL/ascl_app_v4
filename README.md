# ASCL.net - Astrophysics Source Code Library

> Flask rebuild of the ASCL.net website (v4), replacing the legacy PHP/CodeIgniter/WordPress stack.

## Overview

The Astrophysics Source Code Library (ASCL) is a registry of source codes used in astronomy and astrophysics research. This is a ground-up rewrite of ascl.net, migrating from PHP/CodeIgniter + WordPress to a Python/Flask application backed by a normalized MySQL database (v4 schema).

**Stack:**
- **Flask 3.0+** with Jinja2 templates
- **SQLAlchemy 2.0** ORM
- **MySQL 8.0** (v4 normalized schema)
- **Typesense** for full-text search (with MySQL fallback)
- **Uvicorn** ASGI server (VPS) / **Phusion Passenger** (cPanel)
- **Nginx** reverse proxy (VPS)

## Repository Layout

This repo (`alt_ascl/`) is one of several projects under the ASCL root:

```
~/repositories/ASCL/
├── alt_ascl/                          # <-- This repo
│   ├── bin/
│   │   └── ascl                       # Management CLI
│   ├── deployment/
│   │   ├── ascl_net_app.service       # systemd unit
│   │   ├── nginx_ascl_production.conf
│   │   └── redeploy.sh               # Legacy deploy script (use `ascl` CLI instead)
│   ├── source/
│   │   └── ascl_net_app_project_home/ # Flask application
│   │       ├── ascl_net_app/
│   │       │   ├── __init__.py        # App factory (create_app)
│   │       │   ├── controllers/       # Blueprints (routes)
│   │       │   ├── model/             # Database integration
│   │       │   ├── services/          # Typesense client, etc.
│   │       │   ├── templates/         # Jinja2 templates
│   │       │   ├── static/            # CSS, JS, images
│   │       │   └── configuration_files/
│   │       ├── run_ascl_net_app.py    # Dev server entry point
│   │       ├── asgi.py                # Production ASGI entry point
│   │       └── requirements.txt
│   ├── v3_to_v4_migration/            # Database migration scripts
│   ├── ENDPOINT_MAPPING.md            # v3 → v4 endpoint status
│   ├── CLAUDE.md                      # Detailed technical docs
│   └── README.md                      # This file
│
├── ascl_core/                         # Shared Python module (DB singleton, ORM models)
├── dm-dbcore/                         # Database core library dependency
├── ascl_php_application/              # Legacy PHP app (reference only)
└── ascl_api/                          # Dormant (API is a blueprint in alt_ascl)
```

## Implemented Endpoints

39 of 54 v3 endpoints are implemented, plus 28 v4-only additions. See [ENDPOINT_MAPPING.md](ENDPOINT_MAPPING.md) for full status.

**Public pages:** Homepage, about, submissions, resources, explain, WordPress page fetcher
**Code browsing:** All codes (paginated), by ASCL ID, credit search, keyword cloud, alias list, random code, individual code detail
**Search:** Unified search (Typesense + MySQL fallback), type-ahead suggestions, author suggestions
**Data exports:** JSON, XML, DCI, OLE (Alice), ADS plain-text — all with date filtering
**CodeMeta/CFF:** `/<ascl_id>/codemeta.json`, `/<ascl_id>/CITATION.cff`, redirect from `citation.cff`
**News:** Listing with pagination, detail, RSS feed, comments
**Dashboard:** Public statistics
**Code submission:** Guest submission form
**Admin:** Authentication (bcrypt), code CRUD, unpublished/archived lists, notes, utility pages, internal JSON APIs

## `ascl` Management CLI

A single CLI for managing the application across deployment targets.

### Setup

```bash
# Symlink to PATH
sudo ln -s ~/repositories/ASCL/alt_ascl/bin/ascl /usr/local/bin/ascl

# Enable tab completion (bash)
# Copy the completion file to your completions directory, or:
eval "$(ascl completions bash)"
```

On first run, if no config exists, the CLI creates a template at `~/.config/ascl/config.toml` and exits with instructions. Or create it explicitly:

```bash
ascl init            # Creates ~/.config/ascl/config.toml
ascl init --force    # Overwrite existing config
```

### Commands

```bash
ascl status [TARGET]       # Show service status
ascl restart [TARGET]      # Restart the running app
ascl redeploy [TARGET]     # Full redeploy: sync code, install deps, restart
ascl config [TARGET]       # Show resolved config for a target
ascl completions bash|zsh  # Print shell completion script
```

TARGET is `vps` or `cpanel` (defaults to `default_target` in config).

### Deployment Targets

| | VPS | cPanel |
|---|---|---|
| Process manager | systemd | Phusion Passenger |
| Restart | `systemctl restart` | `touch tmp/restart.txt` |
| Deploy path | `/var/www/ascl_net_app` | `~/ascl.net` |
| File transfer | rsync (local) | rsync (local or over SSH) |
| Run-as user | `www-data` | cPanel user |

### Configuration

The config file lives at `~/.config/ascl/config.toml` (respects `$XDG_CONFIG_HOME`). Each target is a TOML section:

```toml
default_target = "vps"

[vps]
restart_method   = "systemd"
service_name     = "ascl_net_app"
deploy_app       = "/var/www/ascl_net_app"
deploy_dmdbcore  = "/var/www/dm-dbcore"
deploy_ascl_core = "/var/www/ascl_core"
repo_app         = "/home/demitri/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home"
repo_dmdbcore    = "/home/demitri/repositories/ASCL/dm-dbcore"
repo_ascl_core   = "/home/demitri/repositories/ASCL/ascl_core"
run_as_user      = "www-data"
flask_config     = "ascl_net.cfg"
secrets_file     = "/etc/ascl/secrets.cfg"
typesense_url        = "http://127.0.0.1:8108"
typesense_collection = "codes"

[cpanel]
restart_method   = "passenger"
deploy_app       = "~/ascl.net"
# ... see config template for full options
```

### What `ascl redeploy vps` Does

1. Checks `/etc/ascl/secrets.cfg` exists
2. Stops the systemd service
3. Rsyncs app, dm-dbcore, and ascl_core from repo to deploy paths
4. Sets ownership to `www-data`
5. Installs dependencies via `uv pip install`
6. Starts the service
7. Shows status

### What `ascl redeploy cpanel` Does

1. Rsyncs repos to deploy paths (local or over SSH if `ssh_host` is set)
2. Installs dependencies via `pip install`
3. Touches `tmp/restart.txt` for Passenger

## Development Setup

### Prerequisites

- Python 3.11+
- MySQL 8.0+
- The `ascl_core` and `dm-dbcore` sibling repos

### Quick Start

```bash
cd ~/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home

# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install ~/repositories/ASCL/dm-dbcore/[mysql]
pip install ~/repositories/ASCL/ascl_core/
pip install -r requirements.txt

# Run dev server (uses default.cfg, ascl_db on port 3307)
python run_ascl_net_app.py --debug --port 5000

# List registered routes
python run_ascl_net_app.py --rules
```

### Database

Dev uses a MySQL Docker container on port 3307. Credentials come from `~/.my.cnf` (`[client_ascl_root]` section).

```bash
# Query the dev database
mysql --defaults-group-suffix=_ascl_root -h 127.0.0.1 -P 3307 ascl_db_v4 -e "SELECT COUNT(*) FROM codes"
```

**Schema versions:**
- `ascl_db` (v3): Legacy PHP-serialized fields in `codes` table
- `ascl_db_v4` (v4): Normalized `link`, `author`, `code_note`, `code_see_also` tables

**Config → database mapping:**
- `default.cfg` → `ascl_db` (v3), port 3307
- `ascl_net.cfg` → `ascl_db_v4` (v4), port 3306
- To develop against v4 locally, use `trillian2_dev.cfg`

### Secrets

Production secrets (`SECRET_KEY`, `ADS_API_TOKEN`, `TYPESENSE_API_KEY`) are in `/etc/ascl/secrets.cfg`, loaded after the main config. Not committed to the repo. See `configuration_files/secrets.cfg.example` for the template.

For local development, place a `secrets.cfg` in `configuration_files/` — it will be loaded automatically in debug mode.

## Production Deployment (VPS)

The VPS runs Uvicorn behind Nginx, managed by systemd.

```bash
# Initial setup (one-time)
sudo cp deployment/ascl_net_app.service /etc/systemd/system/
sudo cp deployment/nginx_ascl_production.conf /etc/nginx/sites-available/ascl_production
sudo ln -s /etc/nginx/sites-available/ascl_production /etc/nginx/sites-enabled/
sudo systemctl daemon-reload
sudo systemctl enable ascl_net_app

# Deploy / redeploy
sudo ascl redeploy vps

# Day-to-day
sudo ascl restart vps
ascl status vps
```

### Logs

```bash
sudo journalctl -u ascl_net_app -f          # App logs
sudo tail -f /var/log/nginx/access.log      # Nginx
```

## Documentation

- [ENDPOINT_MAPPING.md](ENDPOINT_MAPPING.md) — v3 → v4 endpoint migration status
- [CLAUDE.md](CLAUDE.md) — Detailed architecture, schema, config reference
- [deployment/DEPLOYMENT.md](deployment/DEPLOYMENT.md) — Production deployment guide

## Contact

- Original site: https://ascl.net

---

*Last Updated: 2026-03-10*
