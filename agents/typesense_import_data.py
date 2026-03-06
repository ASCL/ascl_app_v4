#!/usr/bin/env python3
"""
Typesense Data Import Script
Imports published codes from MySQL database to Typesense search index.

Usage:
    python typesense_import_data.py [--batch-size 100] [--limit N]
"""

import sys
import os
import requests
import json
import argparse
from datetime import datetime
import pickle
from pathlib import Path

try:
    from ascl_core.database.connections import Trillian2DBConnection as db
    from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode, Keyword, ASCLCodeToKeyword
except ModuleNotFoundError:
    # Local-dev fallback when ascl_core is not installed.
    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "ascl_core" / "source"))
    from ascl_core.database.connections import Trillian2DBConnection as db
    from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode, Keyword, ASCLCodeToKeyword

# Typesense configuration
TYPESENSE_URL = os.environ.get('TYPESENSE_URL', 'http://127.0.0.1:8108').rstrip('/')
TYPESENSE_API_KEY = os.environ.get('TYPESENSE_API_KEY', '')

# Headers for API requests
HEADERS = {
    'X-TYPESENSE-API-KEY': TYPESENSE_API_KEY,
    'Content-Type': 'application/json'
}

def parse_php_serialized_list(serialized_str):
    """
    Parse PHP serialized array/list into Python list.
    Simple parser for common PHP array format: a:N:{i:0;s:L:"value";...}

    Returns list of strings, or empty list if parsing fails.
    """
    if not serialized_str or serialized_str == '':
        return []

    try:
        # Try to parse with pickle (won't work but good to try)
        # For now, use simple string extraction
        # Format: a:3:{i:0;s:6:"Python";i:1;s:1:"C";i:2;s:10:"JavaScript";}

        items = []
        parts = serialized_str.split('s:')

        for part in parts[1:]:  # Skip first element (array header)
            # Extract string value between quotes
            if ':"' in part and '";' in part:
                value = part.split(':"')[1].split('";')[0]
                items.append(value)

        return items
    except Exception as e:
        # If parsing fails, return empty list
        return []

def convert_timestamp_to_unix(dt):
    """Convert datetime to Unix timestamp (seconds since epoch)."""
    if dt is None:
        return None
    if isinstance(dt, str):
        # Parse string to datetime
        try:
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                dt = datetime.strptime(dt, '%Y-%m-%d')
            except ValueError:
                return None

    # Convert to Unix timestamp
    return int(dt.timestamp())

def prepare_document(code, keywords_dict):
    """
    Convert ASCLCode object to Typesense document format.

    Args:
        code: ASCLCode SQLAlchemy object
        keywords_dict: Dict mapping code.pk to list of keyword names

    Returns:
        dict: Document ready for Typesense import
    """
    # Get keywords for this code
    code_keywords = keywords_dict.get(code.pk, [])

    # Convert time_added to Unix timestamp
    time_added_unix = convert_timestamp_to_unix(code.time_added)

    # Build document
    doc = {
        'pk': code.pk,
        'ascl_id': code.ascl_id,
        'title': code.title or '',
        'published': code.published or 0,
        'time_added': time_added_unix or 0,
    }

    # Add optional fields only if they have values
    if code.abstract:
        doc['abstract'] = code.abstract

    if code.credit:
        doc['credit'] = code.credit

    if code.bibcode:
        doc['bibcode'] = code.bibcode

    if code_keywords:
        doc['keywords'] = code_keywords

    # Generate URL for linking back to code page
    doc['url'] = f'/{code.ascl_id}'

    return doc

def fetch_keywords_mapping(session):
    """
    Fetch all code-to-keywords mappings from database.

    Returns:
        dict: {code_pk: [keyword_name1, keyword_name2, ...]}
    """
    print("Loading keywords mapping from database...")

    # Query all keyword relationships for current schema:
    # code_to_keyword(code_pk, keyword_pk) -> keyword(pk, label)
    query = (
        session.query(
            ASCLCodeToKeyword.code_pk,
            Keyword.label
        )
        .join(Keyword, ASCLCodeToKeyword.keyword_pk == Keyword.pk)
        .all()
    )

    # Build dictionary
    keywords_dict = {}
    for code_id, keyword_name in query:
        if code_id not in keywords_dict:
            keywords_dict[code_id] = []
        keywords_dict[code_id].append(keyword_name)

    print(f"✅ Loaded keywords for {len(keywords_dict)} codes")
    return keywords_dict

def import_batch(documents, action='upsert'):
    """
    Import a batch of documents to Typesense.

    Args:
        documents: List of document dicts
        action: 'create', 'update', or 'upsert' (default)

    Returns:
        tuple: (success_count, error_count)
    """
    if not documents:
        return 0, 0

    # Prepare JSONL payload (one JSON object per line)
    jsonl_lines = [json.dumps(doc) for doc in documents]
    jsonl_payload = '\n'.join(jsonl_lines)

    # Import documents
    url = f'{TYPESENSE_URL}/collections/codes/documents/import'
    params = {'action': action}

    try:
        response = requests.post(
            url,
            headers=HEADERS,
            params=params,
            data=jsonl_payload
        )

        if response.status_code == 200:
            # Parse results (one JSON object per line)
            results = [json.loads(line) for line in response.text.strip().split('\n')]

            success_count = sum(1 for r in results if r.get('success') is True)
            error_count = sum(1 for r in results if r.get('success') is False)

            # Print errors if any
            if error_count > 0:
                print(f"\n⚠️  Errors in batch:")
                for r in results:
                    if not r.get('success'):
                        print(f"  - Document {r.get('document', {}).get('pk')}: {r.get('error')}")

            return success_count, error_count
        else:
            print(f"❌ Batch import failed: {response.status_code}")
            print(f"Response: {response.text}")
            return 0, len(documents)

    except Exception as e:
        print(f"❌ Error importing batch: {e}")
        return 0, len(documents)

def main():
    """Main import flow."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Import ASCL codes to Typesense')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Number of documents to import per batch (default: 100)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of codes to import (for testing)')
    parser.add_argument('--published-only', action='store_true', default=True,
                        help='Import only published codes (default: True)')
    args = parser.parse_args()

    print("=" * 60)
    print("ASCL Typesense Data Import")
    print("=" * 60)
    print()

    if not TYPESENSE_API_KEY:
        print("❌ TYPESENSE_API_KEY is not set. Export it and rerun.")
        return False

    # Connect to database
    print("Connecting to MySQL database...")
    session = db.Session()
    print("✅ Database connected")
    print()

    # Fetch keywords mapping
    keywords_dict = fetch_keywords_mapping(session)
    print()

    # Query codes
    print("Querying codes from database...")
    query = session.query(ASCLCode)

    if args.published_only:
        query = query.filter(ASCLCode.published == 1)
        print("  Filtering: published=1 only")

    query = query.order_by(ASCLCode.time_added.desc())

    if args.limit:
        query = query.limit(args.limit)
        print(f"  Limit: {args.limit} codes (for testing)")

    codes = query.all()
    total_codes = len(codes)

    print(f"✅ Found {total_codes} codes to import")
    print()

    # Import in batches
    print(f"Importing in batches of {args.batch_size}...")
    print()

    batch = []
    total_success = 0
    total_errors = 0
    processed = 0

    for code in codes:
        # Convert to Typesense document
        doc = prepare_document(code, keywords_dict)
        batch.append(doc)

        # Import batch when full
        if len(batch) >= args.batch_size:
            success, errors = import_batch(batch, action='upsert')
            total_success += success
            total_errors += errors
            processed += len(batch)

            print(f"Progress: {processed}/{total_codes} codes "
                  f"({total_success} success, {total_errors} errors)")

            batch = []

    # Import remaining documents
    if batch:
        success, errors = import_batch(batch, action='upsert')
        total_success += success
        total_errors += errors
        processed += len(batch)

        print(f"Progress: {processed}/{total_codes} codes "
              f"({total_success} success, {total_errors} errors)")

    print()
    print("=" * 60)
    print("✅ Import complete!")
    print("=" * 60)
    print(f"Total codes processed: {processed}")
    print(f"Successfully imported: {total_success}")
    print(f"Errors: {total_errors}")

    # Verify collection stats
    print()
    print("Verifying collection...")
    try:
        response = requests.get(
            f'{TYPESENSE_URL}/collections/codes',
            headers=HEADERS
        )
        if response.status_code == 200:
            info = response.json()
            print(f"✅ Collection 'codes' now has {info['num_documents']} documents")
    except Exception as e:
        print(f"⚠️  Could not verify collection: {e}")

    session.close()
    return total_errors == 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
