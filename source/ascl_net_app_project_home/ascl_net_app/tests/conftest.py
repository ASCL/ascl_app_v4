import os
import sys
import pytest

from ascl_net_app import create_app


@pytest.fixture(scope="session")
def app():
	# Ensure the project root is on path for imports
	project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
	if project_root not in sys.path:
		sys.path.insert(0, project_root)

	# Prevent PermissionError on /etc/ascl/secrets.cfg during tests
	os.environ.setdefault("ASCL_SECRETS_FILE", "/dev/null")

	app = create_app(debug=True)
	app.config["TESTING"] = True
	return app


@pytest.fixture()
def client(app):
	return app.test_client()
