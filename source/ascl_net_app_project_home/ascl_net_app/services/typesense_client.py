"""
Typesense Client - Singleton wrapper for Typesense search

Provides a Flask-integrated client for Typesense search with:
- Configuration from Flask app config
- Automatic fallback to MySQL on errors
- Connection health checking
- Convenient search methods
"""

import requests
import logging
from flask import current_app

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

        self.base_url = f'{self.protocol}://{self.host}:{self.port}'

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
            return False

        try:
            response = requests.get(
                f'{self.base_url}/health',
                timeout=2  # 2 second timeout
            )

            if response.status_code == 200 and response.json().get('ok'):
                self._healthy = True
                return True
            else:
                self._healthy = False
                logger.warning(f"Typesense health check failed: {response.text}")
                return False

        except requests.exceptions.Timeout:
            self._healthy = False
            logger.warning(f"Typesense health check timed out: {self.base_url}")
            return False
        except requests.exceptions.ConnectionError:
            self._healthy = False
            logger.warning(f"Cannot connect to Typesense at {self.base_url}")
            return False
        except Exception as e:
            self._healthy = False
            logger.error(f"Typesense health check error: {e}")
            return False

    def is_healthy(self):
        """
        Check if Typesense is currently healthy.

        Returns:
            bool: True if healthy, False otherwise
        """
        if self._healthy is None:
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

        except requests.exceptions.Timeout:
            logger.error(f"Typesense search timed out for query: '{query}'")
            self._healthy = False
            return None
        except requests.exceptions.ConnectionError:
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
                return None

        except Exception as e:
            logger.error(f"Error getting Typesense stats: {e}")
            return None


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
