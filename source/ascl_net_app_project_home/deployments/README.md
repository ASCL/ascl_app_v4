# Deployment artifacts

Configuration and entry-point files for the various ways this app is deployed.
None of these files is loaded automatically at runtime — they are reference /
template files that get installed (manually or via `bin/ascl redeploy`) into
host-specific locations.

| Subdirectory     | Purpose                                              | Used by                            |
|------------------|------------------------------------------------------|------------------------------------|
| `passenger/`     | `passenger_wsgi.py` for cPanel + Phusion Passenger   | dev.ascl.net, ascl.net (cPanel)    |
| `systemd/`       | `ascl_net_app.service` unit file                     | VPS deployments                    |
| `nginx/`         | Nginx reverse-proxy configs (dev + production)       | VPS deployments                    |
| `uwsgi/`         | uWSGI configuration (legacy / alternative to systemd)| VPS deployments                    |
| `my.cnf.template`| `~/.my.cnf` template with `[client_ascl]` section    | All deployments (DB credentials)   |

## Why these aren't auto-deployed

- **`passenger_wsgi.py`** lives at the cPanel app root and is account-specific
  (the `VENV` path differs per account). It changes very rarely. Copy by hand.
- **`systemd/ascl_net_app.service`** is installed once with `sudo cp ... /etc/systemd/system/`.
  After that, systemctl uses the installed copy.
- **`nginx/*.cfg`** is installed once into `/etc/nginx/sites-available/`.

`bin/ascl redeploy <target>` rsyncs **only the application code**
(typically just `ascl_net_app/`), not these deployment artifacts.
