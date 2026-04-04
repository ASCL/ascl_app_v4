#!/usr/bin/env python3
"""
run_icecave.py — Launch the Icecave API server.

Usage:
    python3 run_icecave.py                    # default: localhost:5001
    python3 run_icecave.py -p 8080            # custom port
    python3 run_icecave.py --config production.cfg
    python3 run_icecave.py --rules            # list all routes
"""

import argparse

from icecave import create_app


def main():
    parser = argparse.ArgumentParser(description='Icecave API server')
    parser.add_argument('-p', '--port', type=int, default=5001, help='Port (default: 5001)')
    parser.add_argument('--host', default='127.0.0.1', help='Host (default: 127.0.0.1)')
    parser.add_argument('--config', default=None, help='Config file name (e.g. production.cfg)')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('-r', '--rules', action='store_true', help='List all URL routes')
    args = parser.parse_args()

    app = create_app(config_name=args.config)

    if args.rules:
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            methods = ','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
            print(f'{methods:8s} {rule.rule}')
        return

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
