"""
Typesense Client - Singleton wrapper for Typesense search

Provides a Flask-integrated client for Typesense search with:
- Configuration from Flask app config
- Automatic fallback to MySQL on errors
- Connection health checking
- Convenient search methods
"""

import logging
import time
from urllib.parse import urlparse
from flask import current_app

try:
    import requests
    RequestsTimeout = requests.exceptions.Timeout
    RequestsConnectionError = requests.exceptions.ConnectionError
except Exception:  # pragma: no cover - environment-dependent
    requests = None

    class _RequestsUnavailable(Exception):
        pass

    RequestsTimeout = _RequestsUnavailable
    RequestsConnectionError = _RequestsUnavailable

logger = logging.getLogger(__name__)


class TypesenseClient:
    """
    Singleton Typesense client with MySQL fallback.

    Usage:
        client = TypesenseClient.get_instance()
        results = client.search('python', query_by='title,abstract')
    """

    _instance = None
    _initialized = False

    def __init__(self):
        """Private constructor - use get_instance() instead."""
        if TypesenseClient._initialized:
            return

        self.enabled = False
        self.host = None
        self.port = None
        self.protocol = None
        self.api_key = None
        self.collection = None
        self.base_url = None
        self.fallback_to_mysql = True
        self._healthy = None  # None = unknown, True = healthy, False = unhealthy
        self._last_health_check = 0.0
        self._health_check_interval_s = 10
        self._requests_missing_logged = False

        TypesenseClient._initialized = True

    @classmethod
    def get_instance(cls):
        """Get singleton instance of TypesenseClient."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def configure(self, app=None):
        """
        Configure client from Flask app config.

        Args:
            app: Flask application (uses current_app if None)
        """
        if app is None:
            app = current_app

        self.enabled = app.config.get('USING_TYPESENSE', False)
        self.host = app.config.get('TYPESENSE_HOST', 'localhost')
        self.port = app.config.get('TYPESENSE_PORT', 8108)
        self.protocol = app.config.get('TYPESENSE_PROTOCOL', 'http')
        self.api_key = app.config.get('TYPESENSE_API_KEY', '')
        self.collection = app.config.get('TYPESENSE_COLLECTION', 'codes')
        self.fallback_to_mysql = app.config.get('TYPESENSE_FALLBACK_TO_MYSQL', True)
        self._health_check_interval_s = app.config.get('TYPESENSE_HEALTHCHECK_INTERVAL_SECONDS', 10)
        typesense_url = app.config.get('TYPESENSE_URL')
        if typesense_url:
            parsed = urlparse(typesense_url)
            self.protocol = parsed.scheme or self.protocol
            self.host = parsed.hostname or self.host
            self.port = parsed.port or self.port
            self.base_url = typesense_url.rstrip('/')
        else:
            self.base_url = f'{self.protocol}://{self.host}:{self.port}'

        if requests is None and self.enabled:
            if not self._requests_missing_logged:
                logger.warning("Typesense disabled: optional dependency 'requests' is not installed.")
                self._requests_missing_logged = True
            self.enabled = False
            self._healthy = False
            return

        # Test connection on configure
        if self.enabled:
            self.check_health()
            if self.is_healthy():
                logger.info(f"✅ Typesense client configured: {self.base_url}/collections/{self.collection}")
            else:
                logger.warning(f"⚠️  Typesense server not responding at {self.base_url}")
                if self.fallback_to_mysql:
                    logger.info("   Will fall back to MySQL LIKE search")
        else:
            logger.info("Typesense search disabled (USING_TYPESENSE=False)")

    def check_health(self):
        """
        Check if Typesense server is responding.

        Returns:
            bool: True if healthy, False otherwise
        """
        if not self.enabled:
            self._healthy = False
            self._last_health_check = time.monotonic()
            return False

        if requests is None:
            self._healthy = False
            self._last_health_check = time.monotonic()
            return False

        try:
            response = requests.get(
                f'{self.base_url}/health',
                timeout=2  # 2 second timeout
            )

            if response.status_code == 200 and response.json().get('ok'):
                self._healthy = True
                self._last_health_check = time.monotonic()
                return True
            else:
                self._healthy = False
                self._last_health_check = time.monotonic()
                logger.warning(f"Typesense health check failed: {response.text}")
                return False

        except RequestsTimeout:
            self._healthy = False
            self._last_health_check = time.monotonic()
            logger.warning(f"Typesense health check timed out: {self.base_url}")
            return False
        except RequestsConnectionError:
            self._healthy = False
            self._last_health_check = time.monotonic()
            logger.warning(f"Cannot connect to Typesense at {self.base_url}")
            return False
        except Exception as e:
            self._healthy = False
            self._last_health_check = time.monotonic()
            logger.error(f"Typesense health check error: {e}")
            return False

    def is_healthy(self, force_check=False):
        """
        Check if Typesense is currently healthy.

        Returns:
            bool: True if healthy, False otherwise
        """
        if not self.enabled:
            return False

        now = time.monotonic()
        should_refresh = (
            force_check
            or self._healthy is None
            or (not self._healthy)  # retry quickly when currently marked unhealthy
            or (now - self._last_health_check) >= self._health_check_interval_s
        )
        if should_refresh:
            return self.check_health()
        return self._healthy

    def search(self, query, query_by='title,abstract,credit', **params):
        """
        Search Typesense collection.

        Args:
            query: Search query string
            query_by: Comma-separated list of fields to search
            **params: Additional Typesense search parameters
                - per_page: Results per page (default: 10)
                - page: Page number (default: 1)
                - filter_by: Filter expression (e.g., 'published:1')
                - sort_by: Sort expression (e.g., 'time_added:desc')
                - facet_by: Comma-separated fields for faceting
                - max_facet_values: Max facet values per field
                - highlight_full_fields: Fields to highlight fully

        Returns:
            dict: Typesense search results with structure:
                {
                    'found': int,
                    'hits': [{'document': {...}, 'highlight': {...}}],
                    'facet_counts': [...],
                    'out_of': int,
                    'page': int,
                    'request_params': {...},
                    'search_time_ms': int
                }

            Returns None if search fails and fallback is disabled.
        """
        if not self.enabled:
            logger.debug("Typesense disabled, search not performed")
            return None
        if requests is None:
            return None

        # Check health before searching
        if not self.is_healthy():
            logger.warning("Typesense unavailable, search not performed")
            return None

        # Build search parameters
        search_params = {
            'q': query,
            'query_by': query_by,
            'per_page': params.get('per_page', 10),
            'page': params.get('page', 1),
        }

        # Add optional parameters
        if 'filter_by' in params:
            search_params['filter_by'] = params['filter_by']
        if 'sort_by' in params:
            search_params['sort_by'] = params['sort_by']
        if 'facet_by' in params:
            search_params['facet_by'] = params['facet_by']
        if 'max_facet_values' in params:
            search_params['max_facet_values'] = params['max_facet_values']
        if 'highlight_full_fields' in params:
            search_params['highlight_full_fields'] = params['highlight_full_fields']
        # Pass through any additional Typesense params (e.g., num_typos, prefix)
        for key, value in params.items():
            if key not in search_params and value is not None:
                search_params[key] = value

        # Perform search
        try:
            response = requests.get(
                f'{self.base_url}/collections/{self.collection}/documents/search',
                headers={'X-TYPESENSE-API-KEY': self.api_key},
                params=search_params,
                timeout=5  # 5 second timeout
            )

            if response.status_code == 200:
                results = response.json()
                logger.debug(f"Typesense search: '{query}' found {results['found']} results in {results.get('search_time_ms', 0)}ms")
                return results
            else:
                logger.error(f"Typesense search failed: {response.status_code} - {response.text}")
                self._healthy = False
                return None

        except RequestsTimeout:
            logger.error(f"Typesense search timed out for query: '{query}'")
            self._healthy = False
            return None
        except RequestsConnectionError:
            logger.error(f"Cannot connect to Typesense for search: '{query}'")
            self._healthy = False
            return None
        except Exception as e:
            logger.error(f"Typesense search error: {e}")
            self._healthy = False
            return None

    def get_stats(self):
        """
        Get collection statistics.

        Returns:
            dict: Collection info or None if unavailable
        """
        if not self.enabled or not self.is_healthy():
            return None

        try:
            response = requests.get(
                f'{self.base_url}/collections/{self.collection}',
                headers={'X-TYPESENSE-API-KEY': self.api_key},
                timeout=2
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(
                    f"Typesense stats request failed: {response.status_code} - {response.text}"
                )
                return None

        except Exception as e:
            logger.error(f"Error getting Typesense stats: {e}")
            return None

    def get_collection_status(self):
        """
        Check collection access and return detailed status.

        Returns:
            tuple: (status_code, payload_or_text)
                status_code: HTTP status code, or None on request error
                payload_or_text: parsed JSON dict when possible, else raw response text / error message
        """
        if not self.enabled or not self.is_healthy():
            return (None, "Typesense disabled or unhealthy")

        try:
            response = requests.get(
                f'{self.base_url}/collections/{self.collection}',
                headers={'X-TYPESENSE-API-KEY': self.api_key},
                timeout=2
            )

            try:
                payload = response.json()
            except Exception:
                payload = response.text

            return (response.status_code, payload)
        except Exception as e:
            return (None, str(e))


# Global convenience function
def get_typesense_client():
    """
    Get configured Typesense client singleton.

    Returns:
        TypesenseClient: Configured client instance
    """
    client = TypesenseClient.get_instance()
    if not TypesenseClient._initialized or client.base_url is None:
        client.configure()
    return client
