#!/usr/bin/env python3
"""
Shared database credentials for the v3 maintenance scripts.

Credentials come from ~/.my.cnf so that no password is ever written into
source (and therefore into git history). Create the file with:

    [client_ascl]
    user     = ascl_db
    password = <the password>
    host     = localhost
    database = ascl_db

and restrict it: chmod 600 ~/.my.cnf

The `[client_ascl]` section is preferred; `[client]` is used as a fallback so
that a stock MySQL client config also works. `database` is optional and
defaults to `ascl_db` (v3) — see ../README.md for why these scripts must never
be pointed at `ascl_db_v4`.

History:
  2026-07-24 Extracted from link_checker_async.py so all three v3 scripts
             share one implementation instead of hardcoding credentials.
"""

import configparser
import os
import sys

DEFAULT_DATABASE = "ascl_db"


def read_db_config(default_database: str = DEFAULT_DATABASE) -> dict:
    """Read MySQL credentials from ~/.my.cnf.

    Prefers the [client_ascl] section, falls back to [client]. Returns a dict
    with host/user/password/database/port, plus unix_socket if one is
    configured (common on shared and cPanel hosts).
    """
    cnf_path = os.path.expanduser("~/.my.cnf")
    if not os.path.exists(cnf_path):
        sys.exit(
            f"Error: {cnf_path} not found. Create it with a [client_ascl] "
            f"section containing user, password, and host."
        )

    config = configparser.ConfigParser()
    config.read(cnf_path)

    section = "client_ascl" if config.has_section("client_ascl") else "client"
    if not config.has_section(section):
        sys.exit(f"Error: No [client] or [client_ascl] section in {cnf_path}")

    try:
        cfg = {
            "host":     config.get(section, "host", fallback="localhost"),
            "user":     config.get(section, "user"),
            "password": config.get(section, "password"),
            "database": config.get(section, "database", fallback=default_database),
            "port":     config.getint(section, "port", fallback=3306),
        }
    except configparser.NoOptionError as exc:
        sys.exit(f"Error: {cnf_path} [{section}] is missing a required key: {exc}")

    # Support Unix socket connections (common on shared/cPanel hosts).
    socket = config.get(section, "socket", fallback=None)
    if socket:
        cfg["unix_socket"] = socket

    return cfg


def pymysql_kwargs(db_cfg: dict) -> dict:
    """Translate a config dict into pymysql.connect() keyword arguments.

    A unix_socket and a host/port pair are mutually exclusive in pymysql, so
    only one is passed.
    """
    kwargs = {
        "user":     db_cfg["user"],
        "password": db_cfg["password"],
        "database": db_cfg["database"],
        "charset":  "utf8mb4",
    }

    if "unix_socket" in db_cfg:
        kwargs["unix_socket"] = db_cfg["unix_socket"]
    else:
        kwargs["host"] = db_cfg["host"]
        kwargs["port"] = db_cfg["port"]

    return kwargs
