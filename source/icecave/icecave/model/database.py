"""
Database connection management for the Icecave app.

Supports SQLite (default/dev) and PostgreSQL (production) via SQLAlchemy.
The database type is determined by the DB_TYPE configuration parameter.
"""

import logging
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

logger = logging.getLogger(__name__)


class Database:
    """Singleton database connection manager.

    Usage:
        db = Database()
        db.connect(app)          # call once at startup
        session = db.session()   # per-request session
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.engine = None
        self._Session = None
        self.db_type = None

    def connect(self, flask_app):
        """Connect to database using Flask app config."""
        if self.engine is not None:
            return  # already connected

        self.db_type = flask_app.config.get('DB_TYPE', 'sqlite').lower()

        if self.db_type == 'sqlite':
            db_path = flask_app.config.get('DB_PATH', 'icecave.db')
            connection_string = f'sqlite:///{db_path}'

        elif self.db_type == 'postgresql':
            host = flask_app.config['DB_HOST']
            port = flask_app.config.get('DB_PORT', '5432')
            database = flask_app.config['DB_DATABASE']
            user = flask_app.config['DB_USER']
            password = quote_plus(flask_app.config.get('DB_PASSWORD', ''))
            connection_string = f'postgresql://{user}:{password}@{host}:{port}/{database}'

        else:
            raise ValueError(f"Unsupported DB_TYPE: {self.db_type}")

        logger.info(f"Connecting to {self.db_type} database")
        self.engine = create_engine(connection_string, echo=False)
        self._Session = scoped_session(sessionmaker(bind=self.engine))

    def session(self):
        """Return a scoped session."""
        if self._Session is None:
            raise RuntimeError("Database.connect() has not been called")
        return self._Session()

    def remove_session(self):
        """Remove the current scoped session (call at end of request)."""
        if self._Session is not None:
            self._Session.remove()

    def create_tables(self):
        """Create all tables from the ORM models."""
        from .tables import Base
        Base.metadata.create_all(self.engine)
