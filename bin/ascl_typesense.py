"""
ascl typesense — Manage the Typesense search index.

Subcommands:
    ascl typesense reset    Drop and recreate the collection, then re-index
    ascl typesense index    (Re-)index all published codes into Typesense
    ascl typesense status   Show collection info and document count
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


# ---------------------------------------------------------------------------
# Collection schema
# ---------------------------------------------------------------------------

COLLECTION_SCHEMA = {
    "name": "codes",
    "fields": [
        {"name": "pk", "type": "int32", "facet": False},
        {"name": "ascl_id", "type": "string", "facet": True, "index": True},
        {"name": "title", "type": "string", "facet": False, "index": True},
        {"name": "abstract", "type": "string", "facet": False, "index": True, "optional": True},
        {"name": "credit", "type": "string", "facet": False, "index": True, "optional": True},
        {"name": "published", "type": "int32", "facet": True, "index": True},
        {"name": "time_added", "type": "int64", "facet": False, "index": True, "sort": True},
        {"name": "bibcode", "type": "string", "facet": True, "index": True, "optional": True},
        {"name": "keywords", "type": "string[]", "facet": True, "index": True, "optional": True},
        {"name": "described_in", "type": "string", "facet": False, "index": True, "optional": True},
        {"name": "url", "type": "string", "facet": False, "index": False, "optional": True},
    ],
    "default_sorting_field": "time_added",
    "token_separators": ["-", "_", "."],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_headers(api_key):
    return {"X-TYPESENSE-API-KEY": api_key, "Content-Type": "application/json"}


def _get_ts_config(config, args):
    """Resolve Typesense URL, API key, and collection from CLI args / config."""
    target_name, cfg = _resolve_target_for_ts(args, config)

    url = (args.url if hasattr(args, "url") and args.url
           else cfg.get("typesense_url", "http://127.0.0.1:8108")).rstrip("/")
    api_key = os.environ.get("TYPESENSE_API_KEY", cfg.get("typesense_api_key", ""))
    collection = cfg.get("typesense_collection", "codes")

    if not api_key:
        print(_red("TYPESENSE_API_KEY not set. Export it or add typesense_api_key to config."))
        sys.exit(1)
    if not url:
        print(_red("No typesense_url in config and --url not provided."))
        sys.exit(1)

    return url, api_key, collection


def _resolve_target_for_ts(args, config):
    """Pick the deployment target (for reading typesense_url etc.)."""
    target = getattr(args, "target", None)
    if not target:
        target = config.get("default_target", "vps")
    cfg = config.get(target, {})
    return target, cfg


def _strip_html(text):
    return re.sub(r"<[^>]+>", "", text)


def _ts_to_unix(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(dt, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return int(dt.timestamp())


def _prepare_document(code, keywords_dict):
    """Convert an ASCLCode ORM object to a Typesense document dict."""
    doc = {
        "id": str(code.pk),
        "pk": code.pk,
        "ascl_id": code.ascl_id,
        "title": code.title or "",
        "published": code.published or 0,
        "time_added": _ts_to_unix(code.time_added) or 0,
    }
    if code.abstract:
        doc["abstract"] = _strip_html(code.abstract)
    if code.credit:
        doc["credit"] = code.credit
    if code.bibcode:
        doc["bibcode"] = code.bibcode
    kw = keywords_dict.get(code.pk)
    if kw:
        doc["keywords"] = kw
    doc["url"] = f"/{code.ascl_id}"
    return doc


def _get_db_session():
    """Get a SQLAlchemy session via ascl_core (no Flask dependency)."""
    try:
        from ascl_core.database.connections import Trillian2DBConnection as db
        from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode, Keyword, ASCLCodeToKeyword
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root / "ascl_core" / "source"))
        # also need dm-dbcore on the path
        dm_dbcore = repo_root / "dm-dbcore"
        if dm_dbcore.is_dir() and str(dm_dbcore) not in sys.path:
            sys.path.insert(0, str(dm_dbcore))
        from ascl_core.database.connections import Trillian2DBConnection as db
        from ascl_core.database.ascldb.ASCLModelClasses import ASCLCode, Keyword, ASCLCodeToKeyword

    return db.Session(), ASCLCode, Keyword, ASCLCodeToKeyword


def _fetch_keywords(session, ASCLCodeToKeyword, Keyword):
    """Return {code_pk: [keyword_name, ...]}."""
    rows = (
        session.query(ASCLCodeToKeyword.code_pk, Keyword.label)
        .join(Keyword, ASCLCodeToKeyword.keyword_pk == Keyword.pk)
        .all()
    )
    mapping = {}
    for code_pk, label in rows:
        mapping.setdefault(code_pk, []).append(label)
    return mapping


# ---------------------------------------------------------------------------
# Terminal colours (imported from parent module at runtime if available)
# ---------------------------------------------------------------------------

def _bold(t):  return f"\033[1m{t}\033[0m"
def _green(t): return f"\033[92m{t}\033[0m"
def _yellow(t): return f"\033[93m{t}\033[0m"
def _red(t):   return f"\033[91m{t}\033[0m"
def _step(msg): print(f"\n{_bold('==>')} {msg}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_reset(args):
    """Drop collection, recreate schema, and re-index all codes."""
    from ascl_typesense import cmd_index  # re-use index after reset

    config = _load_config()
    url, api_key, collection = _get_ts_config(config, args)
    headers = _ts_headers(api_key)

    # Drop
    _step(f"Dropping collection '{collection}'")
    r = requests.delete(f"{url}/collections/{collection}", headers=headers)
    if r.status_code == 200:
        print(f"  Deleted.")
    elif r.status_code == 404:
        print(f"  Collection didn't exist — nothing to drop.")
    else:
        print(_red(f"  Delete failed: {r.status_code} {r.text}"))
        sys.exit(1)

    # Create
    _step(f"Creating collection '{collection}'")
    schema = dict(COLLECTION_SCHEMA, name=collection)
    r = requests.post(f"{url}/collections", headers=headers, data=json.dumps(schema))
    if r.status_code == 201:
        print(f"  Created.")
    else:
        print(_red(f"  Create failed: {r.status_code} {r.text}"))
        sys.exit(1)

    # Index
    cmd_index(args)


def cmd_index(args):
    """Index (or re-index) all published codes into Typesense."""
    if requests is None:
        print(_red("The 'requests' package is required. pip install requests"))
        sys.exit(1)

    config = _load_config()
    url, api_key, collection = _get_ts_config(config, args)
    headers = _ts_headers(api_key)
    batch_size = getattr(args, "batch_size", 100) or 100

    _step("Connecting to database")
    session, ASCLCode, Keyword, ASCLCodeToKeyword = _get_db_session()
    print("  Connected.")

    _step("Loading keywords")
    keywords_dict = _fetch_keywords(session, ASCLCodeToKeyword, Keyword)
    print(f"  Keywords for {len(keywords_dict)} codes.")

    _step("Querying published codes")
    codes = (
        session.query(ASCLCode)
        .filter(ASCLCode.published == 1)
        .order_by(ASCLCode.time_added.desc())
        .all()
    )
    total = len(codes)
    print(f"  {total} codes to index.")

    _step(f"Importing (batch size {batch_size})")
    total_ok = total_err = 0

    for i in range(0, total, batch_size):
        batch = codes[i : i + batch_size]
        docs = [_prepare_document(c, keywords_dict) for c in batch]
        payload = "\n".join(json.dumps(d) for d in docs)

        r = requests.post(
            f"{url}/collections/{collection}/documents/import",
            headers=headers,
            params={"action": "upsert"},
            data=payload,
        )
        if r.status_code == 200:
            results = [json.loads(line) for line in r.text.strip().split("\n")]
            ok = sum(1 for x in results if x.get("success"))
            err = sum(1 for x in results if not x.get("success"))
            total_ok += ok
            total_err += err
            for x in results:
                if not x.get("success"):
                    print(_yellow(f"    error: pk={x.get('document',{}).get('pk')}: {x.get('error')}"))
        else:
            print(_red(f"  Batch failed: {r.status_code} {r.text}"))
            total_err += len(batch)

        print(f"  {min(i + batch_size, total)}/{total}  ({total_ok} ok, {total_err} errors)")

    session.close()

    _step("Verifying")
    r = requests.get(f"{url}/collections/{collection}", headers=headers)
    if r.status_code == 200:
        info = r.json()
        print(f"  Collection '{collection}': {info['num_documents']} documents")

    print(f"\n{_green('Index complete.')}  {total_ok} indexed, {total_err} errors.")


def cmd_status(args):
    """Show Typesense collection status."""
    if requests is None:
        print(_red("The 'requests' package is required. pip install requests"))
        sys.exit(1)

    config = _load_config()
    url, api_key, collection = _get_ts_config(config, args)
    headers = _ts_headers(api_key)

    # Health
    try:
        r = requests.get(f"{url}/health", timeout=2)
        if r.status_code == 200 and r.json().get("ok"):
            print(f"  Server: {_green('healthy')} ({url})")
        else:
            print(f"  Server: {_red('unhealthy')} ({r.text})")
            return
    except Exception as e:
        print(f"  Server: {_red('unreachable')} ({e})")
        return

    # Collection info
    r = requests.get(f"{url}/collections/{collection}", headers=headers)
    if r.status_code == 200:
        info = r.json()
        print(f"  Collection: {info['name']}")
        print(f"  Documents: {info['num_documents']}")
        print(f"  Fields: {len(info['fields'])}")
    elif r.status_code == 404:
        print(f"  Collection '{collection}': {_yellow('does not exist')}")
    elif r.status_code == 401:
        print(f"  Collection '{collection}': {_red('API key rejected (401)')}")
    else:
        print(f"  Collection '{collection}': {_red(f'{r.status_code} {r.text}')}")


# ---------------------------------------------------------------------------
# Wiring (called from main ascl CLI)
# ---------------------------------------------------------------------------

# _load_config is imported from the parent — set by register_subcommands()
_load_config = None


def register_subcommands(subparsers, load_config_fn):
    """Register 'typesense' subcommand group on the main argparse parser."""
    global _load_config
    _load_config = load_config_fn

    p = subparsers.add_parser("typesense", help="Manage Typesense search index")
    ts_sub = p.add_subparsers(dest="ts_command")

    # ascl typesense reset
    rp = ts_sub.add_parser("reset", help="Drop collection, recreate, and re-index")
    rp.add_argument("--url", help="Typesense URL (overrides config)")
    rp.add_argument("--batch-size", type=int, default=100, help="Import batch size")
    rp.set_defaults(func=cmd_reset)

    # ascl typesense index
    ip = ts_sub.add_parser("index", help="(Re-)index all published codes")
    ip.add_argument("--url", help="Typesense URL (overrides config)")
    ip.add_argument("--batch-size", type=int, default=100, help="Import batch size")
    ip.set_defaults(func=cmd_index)

    # ascl typesense status
    sp = ts_sub.add_parser("status", help="Show collection info and document count")
    sp.add_argument("--url", help="Typesense URL (overrides config)")
    sp.set_defaults(func=cmd_status)

    # Default handler when no subcommand given
    p.set_defaults(func=lambda args: p.print_help())
