#!/usr/bin/env python3
"""
ADS API Diagnostic Script

This script tests the NASA ADS API connection and identifies issues.
Use this to diagnose the "Not found" error.

Usage:
    python3 test_ads_api.py

or for Python 2.7:
    python2.7 test_ads_api.py
"""

import sys
import os

print("=" * 80)
print("ADS API Diagnostic Script")
print("=" * 80)
print()

# Check Python version
print(f"Python version: {sys.version}")
print()

# Check if ads module is installed
print("Checking for ads module...")
try:
    import ads
    print(f"✓ ads module found (version: {getattr(ads, '__version__', 'unknown')})")
except ImportError as e:
    print(f"✗ ads module NOT found: {e}")
    print()
    print("SOLUTION: Install with: pip install ads")
    sys.exit(1)
print()

# Check for API key file
print("Checking for ADS API key...")
dev_key_path = os.path.expanduser("~/.ads/dev_key")
env_key = os.environ.get('ADS_DEV_KEY')

if os.path.exists(dev_key_path):
    with open(dev_key_path, 'r') as f:
        key_content = f.read().strip()
    print(f"✓ API key file found at: {dev_key_path}")
    print(f"  Key length: {len(key_content)} characters")
    print(f"  Key preview: {key_content[:10]}...{key_content[-10:] if len(key_content) > 20 else ''}")
elif env_key:
    print(f"✓ API key found in environment variable ADS_DEV_KEY")
    print(f"  Key length: {len(env_key)} characters")
    print(f"  Key preview: {env_key[:10]}...{env_key[-10:] if len(env_key) > 20 else ''}")
else:
    print(f"✗ API key NOT found")
    print(f"  Checked locations:")
    print(f"    - File: {dev_key_path}")
    print(f"    - Environment: ADS_DEV_KEY")
    print()
    print("SOLUTION: Get API key from https://ui.adsabs.harvard.edu/user/settings/token")
    print("          Save it to ~/.ads/dev_key or set ADS_DEV_KEY environment variable")
    sys.exit(1)
print()

# Test basic API connection
print("Testing basic API connection...")
try:
    # Try a simple query
    papers = ads.SearchQuery(q="star", rows=1)

    # Try to iterate (this will make the actual API call)
    for paper in papers:
        print(f"✓ Basic API connection successful")
        print(f"  Test query returned: {paper.bibcode if hasattr(paper, 'bibcode') else 'unknown'}")
        break
except Exception as e:
    print(f"✗ Basic API connection FAILED: {e}")
    print()
    print("ERROR DETAILS:")
    print(f"  Error type: {type(e).__name__}")
    print(f"  Error message: {str(e)}")

    # Check for common errors
    if "Not found" in str(e):
        print()
        print("DIAGNOSIS: 'Not found' error usually means:")
        print("  1. API key is invalid or expired")
        print("  2. API endpoint has changed")
        print("  3. Network/proxy issue blocking access to https://api.adsabs.harvard.edu/")
        print()
        print("SOLUTIONS:")
        print("  1. Get a new API key from https://ui.adsabs.harvard.edu/user/settings/token")
        print("  2. Update ads library: pip install --upgrade ads")
        print("  3. Check network connectivity: curl https://api.adsabs.harvard.edu/v1/status")

    sys.exit(1)
print()

# Test ASCL-specific query
print("Testing ASCL-specific query (bibstem:ascl.soft)...")
try:
    papers = ads.SearchQuery(
        q="bibstem:ascl.soft",
        sort="citation_count",
        rows=5,
        fl=['title', 'bibcode', 'citation_count']
    )

    count = 0
    for paper in papers:
        count += 1
        title = paper.title[0] if isinstance(paper.title, list) else paper.title
        print(f"  [{count}] {paper.bibcode}: {title}")
        if count >= 5:
            break

    if count > 0:
        print(f"✓ ASCL query successful (found {count} entries)")
    else:
        print(f"✗ ASCL query returned 0 results")
        print("  This may indicate:")
        print("    - Query syntax has changed")
        print("    - ASCL bibstem has changed")
        print("    - No ASCL entries in ADS (unlikely)")

except Exception as e:
    print(f"✗ ASCL query FAILED: {e}")
    print()
    print("ERROR DETAILS:")
    print(f"  Error type: {type(e).__name__}")
    print(f"  Error message: {str(e)}")

    if "Not found" in str(e):
        print()
        print("DIAGNOSIS: The query 'bibstem:ascl.soft' may no longer be valid")
        print("SOLUTIONS:")
        print("  1. Try alternative query: bibstem:ascl")
        print("  2. Check ADS for ASCL entries manually: https://ui.adsabs.harvard.edu/search/q=bibstem:ascl.soft")
        print("  3. Check ASCL documentation: https://ascl.net/")

    sys.exit(1)
print()

# Test with max_pages parameter (the original script uses this)
print("Testing with max_pages parameter (as used in ascl_citations.py)...")
try:
    papers = ads.SearchQuery(
        q="bibstem:ascl.soft",
        sort="citation_count",
        rows=10,
        max_pages=1,
        fl=['title', 'bibcode', 'citation_count', 'citation']
    )

    count = 0
    has_citations = 0
    for paper in papers:
        count += 1
        if hasattr(paper, 'citation_count') and paper.citation_count and paper.citation_count > 0:
            has_citations += 1
        if count >= 10:
            break

    print(f"✓ Query with max_pages successful")
    print(f"  Entries found: {count}")
    print(f"  Entries with citations: {has_citations}")

except Exception as e:
    print(f"✗ Query with max_pages FAILED: {e}")
    print()
    print("ERROR DETAILS:")
    print(f"  Error type: {type(e).__name__}")
    print(f"  Error message: {str(e)}")
    sys.exit(1)
print()

# Check API rate limits
print("Checking API configuration...")
try:
    print(f"  API token configured: {bool(ads.config.token)}")
    # Note: Don't print the actual token for security
except Exception as e:
    print(f"  Could not check API config: {e}")
print()

print("=" * 80)
print("DIAGNOSTICS COMPLETE - All tests passed!")
print("=" * 80)
print()
print("The ads library and API key are configured correctly.")
print("The original script should work if run on this system.")
print()
print("If the original script still fails:")
print("  1. Ensure the database credentials are correct")
print("  2. Ensure the peewee library is installed (pip install peewee)")
print("  3. Check the database server is accessible")
print()

