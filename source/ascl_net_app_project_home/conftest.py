import os
import sys
import pytest

from ascl_net_app import create_app


@pytest.fixture(scope="session")
def app():
	# Ensure project root on sys.path for imports
	project_root = os.path.abspath(os.path.dirname(__file__))
	if project_root not in sys.path:
		sys.path.insert(0, project_root)

	flask_app = create_app(debug=False)
	flask_app.config["TESTING"] = True
	return flask_app


@pytest.fixture()
def client(app):
	return app.test_client()
