#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from ascl_net_app.utilities.logging_config import get_logger

logger = get_logger(__name__)


def test_logging_levels(app):
    app.logger.debug("DEBUG")
    app.logger.info("INFO")
    app.logger.warning("WARNING")
    app.logger.error("ERROR")
    app.logger.critical("CRITICAL")


def test_module_logger():
    logger.debug("DEBUG")
    logger.info("INFO")
    logger.warning("WARNING")
    logger.error("ERROR")
    logger.critical("CRITICAL")


def test_database_logger():
    db_logger = logging.getLogger('DatabaseConnection logger')
    db_logger.info("DB logger reachable")


def test_exception_logging(app):
    try:
        _ = 1 / 0
    except Exception as e:
        app.logger.error(f"Caught exception: {e}", exc_info=True)


def test_formatted_messages(app):
    app.logger.info("User %s performed search: '%s'", 12345, "test search")
