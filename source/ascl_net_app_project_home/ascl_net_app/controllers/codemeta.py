#!/usr/bin/python

"""
CodeMeta 2.0 and CITATION.cff export endpoints.

Implements:
  /<ascl_id>/codemeta.json  — CodeMeta 2.0 JSON
  /<ascl_id>/CITATION.cff   — Citation File Format (CFF) v1.1.0
  /<ascl_id>/citation.cff   — 301 redirect to CITATION.cff
"""

import json
import re

import flask
from flask import Response, redirect, abort, session
from sqlalchemy import text

codemeta_page = flask.Blueprint("codemeta_page", __name__)

_REPO_HOSTS = ("github", "gitlab", "bitbucket", "sourceforge")
_PLACEHOLDER = "PLACEHOLDER: Add {} here"


def _get_session():
    from ascl_net_app.model.database import Database
    return Database().Session()


def _get_code_and_links(ascl_id):
    """Fetch a code record and its links. Returns (row, links_dict) or aborts 404."""
    if not re.match(r"^\d{4}\.\d{3}$", ascl_id):
        abort(404)

    db_session = _get_session()

    # Allow admins to view unpublished codes
    logged_in = "user_id" in session
    where_published = "" if logged_in else "AND c.published = 1"

    row = db_session.execute(text(f"""
        SELECT c.pk, c.ascl_id, c.title, c.credit, c.abstract,
               c.bibcode, c.doi, c.citation_method
        FROM codes c
        WHERE c.ascl_id = :ascl_id {where_published}
        LIMIT 1
    """), {"ascl_id": ascl_id}).mappings().first()

    if not row:
        abort(404)

    # Get links grouped by type
    link_rows = db_session.execute(text("""
        SELECT l.url, lt.short_name
        FROM link l
        LEFT JOIN link_type lt ON l.link_type_pk = lt.pk
        WHERE l.code_pk = :code_pk
        ORDER BY lt.pk, l.display_order, l.pk
    """), {"code_pk": row["pk"]}).mappings().all()

    links = {}
    for lr in link_rows:
        key = lr["short_name"] or "other"
        links.setdefault(key, []).append(lr["url"])

    # Get authors from the author table (v4 normalized)
    authors = db_session.execute(text("""
        SELECT a.given, a.family, a.orcid
        FROM author a
        JOIN code_to_author ca ON ca.author_pk = a.pk
        WHERE ca.code_pk = :code_pk
        ORDER BY ca.display_order, a.pk
    """), {"code_pk": row["pk"]}).mappings().all()

    return row, links, authors


def _parse_credit_authors(credit_str):
    """Fallback: parse credit string 'Last, First; Last, First' into author dicts."""
    authors = []
    if not credit_str:
        return authors
    for author in credit_str.split(";"):
        parts = author.strip().split(",", 1)
        family = parts[0].strip()
        given = parts[1].strip() if len(parts) > 1 else ""
        authors.append({"family": family, "given": given, "orcid": None})
    return authors


# ---------------------------------------------------------------------------
# /<ascl_id>/codemeta.json
# ---------------------------------------------------------------------------

@codemeta_page.route("/<ascl_id>/codemeta.json")
def codemeta_json(ascl_id):
    row, links, db_authors = _get_code_and_links(ascl_id)

    # Use normalized authors if available, fall back to credit parsing
    if db_authors:
        authors_raw = [dict(a) for a in db_authors]
    else:
        authors_raw = _parse_credit_authors(row["credit"])

    # Build author array
    authors = []
    for a in authors_raw:
        author_obj = {
            "@type": "Person",
            "givenName": a["given"] or "",
            "familyName": a["family"] or "",
        }
        if a.get("orcid"):
            author_obj["@id"] = f"https://orcid.org/{a['orcid']}"
        else:
            author_obj["@id"] = _PLACEHOLDER.format("ORCID (https://orcid.org/xxxxxx)")
        authors.append(author_obj)

    # Citation
    if row["citation_method"]:
        citation = row["citation_method"]
    elif row["bibcode"]:
        citation = f"https://ui.adsabs.harvard.edu/abs/{row['bibcode']}"
    else:
        citation = ""

    # Separate repos from other links
    site_links = links.get("code-site", [])
    repos = []
    related = []
    for url in site_links:
        if any(host in url.lower() for host in _REPO_HOSTS):
            repos.append(url)
        else:
            related.append(url)

    result = {
        "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
        "@type": "SoftwareSourceCode",
        "name": row["title"],
        "description": row["abstract"],
        "identifier": f"ascl:{row['ascl_id']}",
        "author": authors,
        "citation": citation,
        "codeRepository": repos if repos else _PLACEHOLDER.format("code repository"),
    }

    if related:
        result["relatedLink"] = related
    else:
        result["relatedLink"] = [_PLACEHOLDER.format("related links (if any)")]

    # Reference publications (described-in links)
    described_in = links.get("described-in", [])
    if described_in:
        refpubs = []
        for url in described_in:
            refpubs.append({
                "@type": "ScholarlyArticle",
                "url": url,
                "@id": _PLACEHOLDER.format("DOI (https://doi.org/xxxxxx)"),
            })
        result["referencePublication"] = refpubs

    # Placeholder fields
    result["version"] = _PLACEHOLDER.format("version")
    result["license"] = _PLACEHOLDER.format(
        "license (ideally as a URL to the SPDX page - e.g. https://spdx.org/licenses/MIT.html)"
    )

    return Response(
        json.dumps(result, ensure_ascii=False, indent=4),
        mimetype="application/json",
    )


# ---------------------------------------------------------------------------
# /<ascl_id>/CITATION.cff
# ---------------------------------------------------------------------------

@codemeta_page.route("/<ascl_id>/CITATION.cff")
def citation_cff(ascl_id):
    row, links, db_authors = _get_code_and_links(ascl_id)

    # Use normalized authors if available, fall back to credit parsing
    if db_authors:
        authors_raw = [dict(a) for a in db_authors]
    else:
        authors_raw = _parse_credit_authors(row["credit"])

    lines = ["cff-version: 1.1.0"]

    # Message
    if row["citation_method"]:
        msg = row["citation_method"]
    elif row["bibcode"]:
        msg = f"https://ui.adsabs.harvard.edu/abs/{row['bibcode']}"
    else:
        msg = f"https://ascl.net/{row['ascl_id']}"
    lines.append(f'message: "Please cite the following works when using this software: {msg}"')

    # Authors
    lines.append("authors:")
    for a in authors_raw:
        lines.append(f"- family-names: {a['family'] or ''}")
        lines.append(f"  given-names: {a['given'] or ''}")

    # Title
    lines.append(f'title: "{row["title"]}"')

    # Placeholders for version / date-released
    lines.append("version: PLACEHOLDER")
    lines.append("date-released: PLACEHOLDER")

    # Identifiers
    lines.append("identifiers:")
    lines.append(' - type: "ascl-id"')
    lines.append(f'   value: "{row["ascl_id"]}"')
    lines.append(' - type: "doi"')
    if row["doi"]:
        lines.append(f'   value: "{row["doi"]}"')
    else:
        lines.append("   value: PLACEHOLDER")
    if row["bibcode"]:
        lines.append(' - type: "bibcode"')
        lines.append(f'   value: "{row["bibcode"]}"')

    # Abstract
    lines.append(f'abstract: "{row["abstract"]}"')

    return Response("\n".join(lines) + "\n", mimetype="text/plain")


# ---------------------------------------------------------------------------
# /<ascl_id>/citation.cff → 301 to CITATION.cff
# ---------------------------------------------------------------------------

@codemeta_page.route("/<ascl_id>/citation.cff")
def citation_cff_redirect(ascl_id):
    return redirect(f"/{ascl_id}/CITATION.cff", code=301)
