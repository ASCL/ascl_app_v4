#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ASGI entry point for the ASCL.net application.

This module provides the ASGI application callable for Uvicorn.
For development, use run_ascl_net_app.py instead.

Production usage:
    uvicorn asgi:application --host 0.0.0.0 --port 8000 --workers 4

Note: Flask is a WSGI application, so we use WsgiToAsgi to wrap it for Uvicorn.
"""

import os
from asgiref.wsgi import WsgiToAsgi
from ascl_net_app import create_app

# Create the Flask application instance
# In production, debug should always be False
flask_app = create_app(debug=False)

# Wrap the WSGI Flask app with ASGI adapter for Uvicorn
application = WsgiToAsgi(flask_app)

# For backwards compatibility, also expose as 'app'
app = application
