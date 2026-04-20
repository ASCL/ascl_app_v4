"""
Phusion Passenger WSGI entry point for cPanel deployment.

This file lives in the cPanel app root (alongside the `ascl_net_app/` package
and `secrets.cfg`). cPanel's "Setup Python App" loads it via Passenger.

NOTE: This file is host-specific in placement but the contents are
account-agnostic — it auto-selects the Flask config based on the cPanel
account name (devascl vs ascl). The same file works on both deployments.

Deployment: copy manually to the cPanel app root when it changes
(this should be very rare). It is intentionally NOT auto-rsynced by
`ascl redeploy` to avoid surprising cPanel restarts.
"""

import os
import sys
import getpass

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_startup.log')
with open(log_path, 'w') as f:
    f.write(f"executable: {sys.executable}\n")
    f.write(f"sys.path:\n")
    for p in sys.path:
        f.write(f"  {p}\n")
    f.write(f"prefix: {sys.prefix}\n")
    f.write(f"base_prefix: {sys.base_prefix}\n")

# Activate the cPanel virtualenv.
# IMPORTANT: this path is account-specific — /itss/home/<account>/virtualenv/...
# This committed copy uses the devascl path; production (ascl account) needs
# the path edited before manual copy. The rest of this file is account-agnostic.
VENV = '/itss/home/devascl/virtualenv/ascl_app_v4/3.13'
sys.path.insert(0, os.path.join(VENV, 'lib', 'python3.13', 'site-packages'))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
pymysql.install_as_MySQLdb()

# Select config based on cPanel account
username = getpass.getuser()
if username == 'devascl':
    os.environ['FLASK_CONFIG'] = 'devascl_net.cfg'
elif username == 'ascl':
    os.environ['FLASK_CONFIG'] = 'ascl_net.cfg'

# secrets (shhh)
app_dir = os.path.dirname(os.path.abspath(__file__))
os.environ['ASCL_SECRETS_FILE'] = os.path.join(app_dir, 'secrets.cfg')

from ascl_net_app import create_app

application = create_app(debug=False)
