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
│   └── ascl                       # Management CLI (restart, redeploy, status)
├── deployment/
│   ├── ascl_net_app.service       # systemd unit file
│   └── nginx_ascl_production.conf
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
│       ├── run_ascl_net_app.py    # Dev server entry point
│       ├── asgi.py                # Production ASGI entry point
│       └── requirements.txt
├── v3_to_v4_migration/            # Database migration scripts (v3 → v4)
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
ascl status [vps|cpanel]       # Show service status
ascl restart [vps|cpanel]      # Restart the running app
ascl redeploy [vps|cpanel]     # Full redeploy: sync code, install deps, restart
ascl config [vps|cpanel]       # Show resolved config for a target
ascl init [--force]            # Create or overwrite config template
ascl completions bash|zsh      # Print shell completion script
```

Target defaults to `default_target` in the config file.

### Config

Each deployment target is a TOML section in `~/.config/ascl/config.toml`:

```toml
default_target = "vps"

[vps]
restart_method = "systemd"       # systemctl restart <service_name>
service_name   = "ascl_net_app"
repo_app       = "/home/user/repositories/ASCL/alt_ascl/source/ascl_net_app_project_home"
deploy_app     = "/var/www/ascl_net_app"
run_as_user    = "www-data"
flask_config   = "ascl_net.cfg"
secrets_file   = "/etc/ascl/secrets.cfg"
typesense_url        = "http://127.0.0.1:8108"
typesense_collection = "codes"

[cpanel]
restart_method = "passenger"     # touch tmp/restart.txt
deploy_app     = "~/ascl.net"
flask_config   = "ascl_net.cfg"
ssh_host       = ""              # Set for remote deploy from another machine
typesense_url        = ""
typesense_collection = "codes"
```

### What `ascl redeploy` Does

**VPS (systemd):** stop service, rsync app from repo to deploy path, set ownership, `pip install -r requirements.txt`, start service.

**cPanel (Passenger):** rsync app (local or over SSH), `pip install -r requirements.txt`, touch `tmp/restart.txt`.

## Documentation

- [ENDPOINT_MAPPING.md](ENDPOINT_MAPPING.md) — v3 → v4 endpoint migration status
- [CLAUDE.md](CLAUDE.md) — Architecture, database schema, configuration reference
- [deployment/DEPLOYMENT.md](deployment/DEPLOYMENT.md) — Production deployment guide

---

*Last Updated: 2026-03-10*
