#!/usr/bin/env python3
"""
icecave_import.py — Import code_archive data from the ASCL MySQL database
into the Icecave app's own database (SQLite or PostgreSQL).

This is a one-time migration tool to seed the Icecave database from the
existing code_archive table in ascl_db_v4.

Usage:
    python3 icecave_import.py                           # default settings
    python3 icecave_import.py --mysql-db ascl_db_v4     # specify source
    python3 icecave_import.py --config production.cfg   # use production config
"""

import argparse
import configparser
from pathlib import Path

import MySQLdb

from icecave import create_app
from icecave.model.database import Database
from icecave.model.tables import CodeArchive


def get_mysql_connection(database):
    """Connect to MySQL using ~/.my.cnf [client_ascl_root] section."""
    cnf = configparser.ConfigParser()
    cnf.read(str(Path.home() / '.my.cnf'))
    section = 'client_ascl_root'
    return MySQLdb.connect(
        host=cnf.get(section, 'host', fallback='127.0.0.1'),
        port=int(cnf.get(section, 'port', fallback='3307')),
        user=cnf.get(section, 'user'),
        passwd=cnf.get(section, 'password'),
        db=database,
        charset='utf8mb4',
    )


def main():
    parser = argparse.ArgumentParser(description='Import code_archive from MySQL')
    parser.add_argument('--mysql-db', default='ascl_db_v4', help='Source MySQL database')
    parser.add_argument('--config', default=None, help='Icecave config file name')
    args = parser.parse_args()

    # Set up icecave app context for database access
    app = create_app(config_name=args.config)

    with app.app_context():
        db = Database()
        session = db.session()

        # Read from MySQL
        mysql_conn = get_mysql_connection(args.mysql_db)
        cursor = mysql_conn.cursor()

        cursor.execute("""
            SELECT c.ascl_id, c.title, c.short_name,
                   ca.archive_type, ca.source_url, ca.dir_name,
                   ca.last_checked, ca.last_updated, ca.last_wayback,
                   ca.wayback_url, ca.size_bytes, ca.status, ca.error_message
            FROM code_archive ca
            JOIN codes c ON c.pk = ca.code_pk
            ORDER BY c.ascl_id
        """)

        # Check what already exists
        existing = {r.ascl_id for r in session.query(CodeArchive.ascl_id).all()}

        imported = 0
        skipped = 0

        for row in cursor.fetchall():
            (ascl_id, title, short_name, archive_type, source_url, dir_name,
             last_checked, last_updated, last_wayback, wayback_url,
             size_bytes, status, error_message) = row

            if ascl_id in existing:
                skipped += 1
                continue

            code = CodeArchive(
                ascl_id=ascl_id,
                code_title=title,
                short_name=short_name,
                archive_type=archive_type,
                source_url=source_url or '',
                dir_name=dir_name,
                last_checked=last_checked,
                last_updated=last_updated,
                last_wayback=last_wayback,
                wayback_url=wayback_url,
                size_bytes=size_bytes,
                status=status,
                error_message=error_message,
            )
            session.add(code)
            imported += 1

        session.commit()
        cursor.close()
        mysql_conn.close()

        print(f"Imported {imported} records, skipped {skipped} (already exist)")


if __name__ == '__main__':
    main()
