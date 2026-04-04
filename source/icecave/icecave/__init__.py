"""
Icecave — ASCL Code Archive API

Minimal Flask app that manages the ASCL code archive on a VPS and
exposes a JSON API for the main ascl.net application to query.
"""

import os
import logging

from flask import Flask, g, jsonify, request

from .model.database import Database

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """Application factory."""

    app = Flask(__name__, instance_relative_config=True)

    # Load default config
    app.config.from_pyfile(
        os.path.join(os.path.dirname(__file__), 'configuration_files', 'default.cfg')
    )

    # Overlay environment-specific config
    if config_name:
        app.config.from_pyfile(
            os.path.join(os.path.dirname(__file__), 'configuration_files', config_name)
        )

    # Load secrets (API key, etc.)
    secrets_file = os.environ.get('ICECAVE_SECRETS_FILE', '/etc/icecave/secrets.cfg')
    if os.path.exists(secrets_file):
        app.config.from_pyfile(secrets_file)

    # Database setup
    db = Database()
    db.connect(app)
    db.create_tables()

    # Register blueprints
    from .api.status import status_api
    from .api.sync import sync_api
    from .api.wayback import wayback_api

    app.register_blueprint(status_api, url_prefix='/api')
    app.register_blueprint(sync_api, url_prefix='/api')
    app.register_blueprint(wayback_api, url_prefix='/api')

    # Authentication middleware
    @app.before_request
    def check_api_key():
        api_key = app.config.get('API_KEY')
        if not api_key:
            return  # no key configured (dev mode)
        if request.path == '/api/health':
            return  # health check is unauthenticated
        auth = request.headers.get('Authorization', '')
        if auth != f'Bearer {api_key}':
            return jsonify({'error': 'unauthorized'}), 401

    # Session cleanup
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.remove_session()

    return app
