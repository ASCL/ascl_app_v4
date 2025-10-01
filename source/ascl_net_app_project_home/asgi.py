#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ASGI entry point for the ASCL.net application.

This module provides the ASGI application callable for Uvicorn.
For development, use run_ascl_net_app.py instead.

Production usage:
    uvicorn asgi:application --host 0.0.0.0 --port 8000 --workers 4
"""

import os
from ascl_net_app import create_app

# Create the Flask application instance
# In production, debug should always be False
application = create_app(debug=False)

# For backwards compatibility, also expose as 'app'
app = application
