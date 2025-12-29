#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Logging configuration for ASCL.net Flask application.

This module provides centralized logging setup for:
- Flask application logs
- ascl_core module logs (database operations)
- SQLAlchemy query logs (when LOG_SQL_QUERIES is enabled)

Usage:
    from ascl_net_app.logging_config import setup_logging
    setup_logging(app)
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path


def setup_logging(app):
    """
    Configure logging for the Flask application and all related modules.

    Args:
        app: Flask application instance

    Logging levels configured:
        - Production: INFO for app, WARNING for libraries
        - Debug mode: DEBUG for app and ascl_core, INFO for SQLAlchemy

    Log outputs:
        - Console: All logs (with colors if ENABLE_COLOR_LOGS is True)
        - File: app.log in logs/ directory (rotating, 10MB max, 5 backups)
    """

    # Determine log level based on debug mode
    if app.debug:
        app_log_level = logging.DEBUG
        ascl_core_log_level = logging.DEBUG
        sqlalchemy_log_level = logging.INFO
    else:
        app_log_level = logging.INFO
        ascl_core_log_level = logging.INFO
        sqlalchemy_log_level = logging.WARNING

    # Create logs directory if it doesn't exist
    log_dir = Path(app.root_path).parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / 'app.log'

    # Clear existing handlers on root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)  # Set to DEBUG, handlers will filter

    # ============================================================================
    # Console Handler (stdout)
    # ============================================================================
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Use colored formatter if enabled
    if app.config.get('ENABLE_COLOR_LOGS', True) and sys.stdout.isatty():
        console_formatter = ColoredFormatter(
            fmt='%(levelname_colored)s [%(name_colored)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        console_formatter = logging.Formatter(
            fmt='%(levelname)-8s [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    console_handler.setFormatter(console_formatter)

    # ============================================================================
    # File Handler (rotating)
    # ============================================================================
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        fmt='%(asctime)s %(levelname)-8s [%(name)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # ============================================================================
    # Configure specific loggers
    # ============================================================================

    # Flask app logger
    app.logger.setLevel(app_log_level)
    app.logger.handlers.clear()
    app.logger.addHandler(console_handler)
    app.logger.addHandler(file_handler)
    app.logger.propagate = False

    # ascl_core module logger (database operations) - legacy name
    ascl_core_logger = logging.getLogger('DatabaseConnection logger')
    ascl_core_logger.setLevel(ascl_core_log_level)
    ascl_core_logger.handlers.clear()
    ascl_core_logger.addHandler(console_handler)
    ascl_core_logger.addHandler(file_handler)
    ascl_core_logger.propagate = False

    # ascl_core.* module loggers (captures all ascl_core modules including Trillian2DBConnection)
    # This configures the root logger for the entire ascl_core package
    ascl_core_root_logger = logging.getLogger('ascl_core')
    ascl_core_root_logger.setLevel(ascl_core_log_level)
    ascl_core_root_logger.handlers.clear()
    ascl_core_root_logger.addHandler(console_handler)
    ascl_core_root_logger.addHandler(file_handler)
    ascl_core_root_logger.propagate = False

    # dm_dbcore.* module loggers (the actual database connection layer)
    # This wraps the DatabaseConnection from dm-dbcore
    dm_dbcore_logger = logging.getLogger('dm_dbcore')
    dm_dbcore_logger.setLevel(ascl_core_log_level)
    dm_dbcore_logger.handlers.clear()
    dm_dbcore_logger.addHandler(console_handler)
    dm_dbcore_logger.addHandler(file_handler)
    dm_dbcore_logger.propagate = False

    # SQLAlchemy loggers
    if app.config.get('LOG_SQL_QUERIES', False):
        # Log all SQL queries
        sqlalchemy_engine_logger = logging.getLogger('sqlalchemy.engine')
        sqlalchemy_engine_logger.setLevel(logging.INFO)
        sqlalchemy_engine_logger.handlers.clear()
        sqlalchemy_engine_logger.addHandler(console_handler)
        sqlalchemy_engine_logger.addHandler(file_handler)
        sqlalchemy_engine_logger.propagate = False

        app.logger.info("SQL query logging ENABLED")
    else:
        # Suppress SQLAlchemy logs unless WARNING or higher
        logging.getLogger('sqlalchemy').setLevel(sqlalchemy_log_level)

    # Other library loggers (suppress unless WARNING)
    for logger_name in ['urllib3', 'werkzeug']:
        lib_logger = logging.getLogger(logger_name)
        lib_logger.setLevel(logging.WARNING)

    # Log startup message
    app.logger.info("="*60)
    app.logger.info(f"ASCL.net application starting (debug={app.debug})")
    app.logger.info(f"Log file: {log_file}")
    app.logger.info(f"App log level: {logging.getLevelName(app_log_level)}")
    app.logger.info(f"ascl_core/dm_dbcore log level: {logging.getLevelName(ascl_core_log_level)}")
    app.logger.info("Configured loggers: ascl_net_app, ascl_core.*, dm_dbcore.*")
    app.logger.info("="*60)


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds color to log output using ANSI escape codes.

    Colors:
        DEBUG: Cyan
        INFO: Green
        WARNING: Yellow
        ERROR: Red
        CRITICAL: Red + Bold
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[1;31m', # Bold Red
        'RESET': '\033[0m'        # Reset
    }

    # Logger name colors
    NAME_COLORS = {
        'ascl_net_app': '\033[94m',                                    # Bright Blue
        'ascl_net_app.model.database': '\033[94m',                     # Bright Blue
        'DatabaseConnection logger': '\033[95m',                       # Magenta (legacy)
        'ascl_core': '\033[95m',                                       # Magenta
        'ascl_core.database.connections.Trillian2DBConnection': '\033[95m',  # Magenta
        'dm_dbcore': '\033[35m',                                       # Purple
        'sqlalchemy.engine': '\033[96m',                               # Bright Cyan
    }

    def format(self, record):
        # Color the log level
        levelname_colored = (
            f"{self.COLORS.get(record.levelname, '')}"
            f"{record.levelname:<8}"
            f"{self.COLORS['RESET']}"
        )

        # Color the logger name
        name_color = self.NAME_COLORS.get(record.name, '\033[90m')  # Default: gray
        name_colored = f"{name_color}{record.name}{self.COLORS['RESET']}"

        # Add to record
        record.levelname_colored = levelname_colored
        record.name_colored = name_colored

        return super().format(record)


def get_logger(name):
    """
    Get a logger instance for use in application modules.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        logging.Logger instance

    Example:
        from ascl_net_app.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logging.getLogger(name)
