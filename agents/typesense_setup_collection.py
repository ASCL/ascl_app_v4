#!/usr/bin/env python3
"""
Typesense Collection Setup Script
Creates the 'codes' collection with proper schema for ASCL search.

Usage:
    python typesense_setup_collection.py
"""

import requests
import json

# Typesense configuration
TYPESENSE_HOST = 'localhost'
TYPESENSE_PORT = 8108
TYPESENSE_API_KEY = 'oWBN1v9zT9C3ZM48gblWobm4ibxcrFcn11hGpb3HiPzT9UOL'
TYPESENSE_URL = f'http://{TYPESENSE_HOST}:{TYPESENSE_PORT}'

# Headers for API requests
HEADERS = {
    'X-TYPESENSE-API-KEY': TYPESENSE_API_KEY,
    'Content-Type': 'application/json'
}

# Collection schema
COLLECTION_SCHEMA = {
    "name": "codes",
    "fields": [
        # Primary key
        {"name": "pk", "type": "int32", "facet": False},

        # ASCL ID (for display, not search key)
        {"name": "ascl_id", "type": "string", "facet": True, "index": True},

        # Core searchable fields
        {"name": "title", "type": "string", "facet": False, "index": True},
        {"name": "abstract", "type": "string", "facet": False, "index": True, "optional": True},
        {"name": "credit", "type": "string", "facet": False, "index": True, "optional": True},

        # Metadata fields for filtering
        {"name": "published", "type": "int32", "facet": True, "index": True},
        {"name": "time_added", "type": "int64", "facet": False, "index": True, "sort": True},

        # Searchable text fields
        {"name": "bibcode", "type": "string", "facet": True, "index": True, "optional": True},

        # Keywords (facets) - stored as array of strings
        {"name": "keywords", "type": "string[]", "facet": True, "index": True, "optional": True},

        # Full-text fields (for comprehensive search)
        {"name": "described_in", "type": "string", "facet": False, "index": True, "optional": True},

        # URL for linking back to code page
        {"name": "url", "type": "string", "facet": False, "index": False, "optional": True},
    ],
    "default_sorting_field": "time_added",
    "token_separators": ["-", "_", "."]  # Treat hyphens, underscores, dots as word separators
}

def check_typesense_health():
    """Check if Typesense is running and healthy."""
    try:
        response = requests.get(f'{TYPESENSE_URL}/health')
        if response.status_code == 200 and response.json().get('ok'):
            print("✅ Typesense is running and healthy")
            return True
        else:
            print(f"❌ Typesense health check failed: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to Typesense at {TYPESENSE_URL}")
        return False
    except Exception as e:
        print(f"❌ Error checking Typesense health: {e}")
        return False

def check_collection_exists():
    """Check if the 'codes' collection already exists."""
    try:
        response = requests.get(
            f'{TYPESENSE_URL}/collections/codes',
            headers=HEADERS
        )
        if response.status_code == 200:
            print("⚠️  Collection 'codes' already exists")
            return True
        return False
    except Exception as e:
        return False

def delete_collection():
    """Delete existing collection (for testing/recreation)."""
    try:
        response = requests.delete(
            f'{TYPESENSE_URL}/collections/codes',
            headers=HEADERS
        )
        if response.status_code == 200:
            print("✅ Deleted existing 'codes' collection")
            return True
        else:
            print(f"❌ Failed to delete collection: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error deleting collection: {e}")
        return False

def create_collection():
    """Create the 'codes' collection with the defined schema."""
    try:
        response = requests.post(
            f'{TYPESENSE_URL}/collections',
            headers=HEADERS,
            data=json.dumps(COLLECTION_SCHEMA)
        )

        if response.status_code == 201:
            print("✅ Successfully created 'codes' collection")
            print(f"\nCollection schema:")
            print(json.dumps(COLLECTION_SCHEMA, indent=2))
            return True
        else:
            print(f"❌ Failed to create collection: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error creating collection: {e}")
        return False

def get_collection_info():
    """Retrieve and display collection information."""
    try:
        response = requests.get(
            f'{TYPESENSE_URL}/collections/codes',
            headers=HEADERS
        )

        if response.status_code == 200:
            collection_info = response.json()
            print("\n✅ Collection 'codes' information:")
            print(f"  - Name: {collection_info['name']}")
            print(f"  - Number of documents: {collection_info['num_documents']}")
            print(f"  - Number of fields: {len(collection_info['fields'])}")
            print(f"  - Default sorting field: {collection_info.get('default_sorting_field', 'none')}")
            return True
        else:
            print(f"❌ Failed to get collection info: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error getting collection info: {e}")
        return False

def main():
    """Main setup flow."""
    print("=" * 60)
    print("ASCL Typesense Collection Setup")
    print("=" * 60)
    print()

    # Step 1: Check Typesense health
    if not check_typesense_health():
        print("\n❌ Typesense is not running. Please start it first.")
        return False

    print()

    # Step 2: Check if collection exists
    if check_collection_exists():
        response = input("\nDo you want to delete and recreate the collection? (yes/no): ")
        if response.lower() in ['yes', 'y']:
            if not delete_collection():
                return False
            print()
        else:
            print("Keeping existing collection.")
            get_collection_info()
            return True

    # Step 3: Create collection
    print("Creating 'codes' collection...")
    if not create_collection():
        return False

    print()

    # Step 4: Verify collection was created
    get_collection_info()

    print()
    print("=" * 60)
    print("✅ Setup complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Run the import script to populate the collection with data")
    print("2. Test search queries via the Typesense API")
    print("3. Integrate search into Flask application")

    return True

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
