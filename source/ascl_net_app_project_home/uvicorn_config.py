"""
Uvicorn configuration for production deployment.

This file can be used to configure Uvicorn programmatically.
Alternatively, use command-line options (see README.md).

Usage:
    uvicorn asgi:application --config uvicorn_config.py
"""

# Bind to all interfaces on port 8000
bind = "0.0.0.0:8000"

# Number of worker processes
# Rule of thumb: (2 x CPU cores) + 1
workers = 4

# Worker class - use uvloop for better performance
worker_class = "uvicorn.workers.UvicornWorker"

# Logging
loglevel = "info"
access_log = True
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "ascl_net_app"

# Daemon mode (run in background)
daemon = False

# PID file
pidfile = "/tmp/ascl_net_app.pid"

# Timeouts
timeout = 120
keepalive = 5

# SSL/TLS (if not using Nginx as reverse proxy)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"
