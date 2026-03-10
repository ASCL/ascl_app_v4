#!/usr/bin/python

"""
Data export endpoints.

Implements /code/json, /code/xml, /code/dci, /code/dci/<date>,
/code/ole/<date>, and /code/ads/<date>.

These replicate the v3 PHP data export formats for backward compatibility.
"""

import re
import html
from datetime import datetime, timedelta
from xml.sax.saxutils import escape as xml_escape

import flask
from flask import Response, session, abort
from sqlalchemy import text

exports_page = flask.Blueprint("exports_page", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session():
    from ascl_net_app.model.database import Database
    return Database().Session()


def _parse_date(date_str):
    """Parse a date string flexibly (supports 2024/01/15, 2024-01-15, etc.).

    Returns a datetime or None if invalid.
    """
    date_str = date_str.strip().strip("/")
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S",
                "%Y/%m", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _links_by_type(db_session, code_pk):
    """Return a dict mapping link_type short_name to list of URLs for a code."""
    rows = db_session.execute(text("""
        SELECT l.url, lt.short_name
        FROM link l
        LEFT JOIN link_type lt ON l.link_type_pk = lt.pk
        WHERE l.code_pk = :code_pk
        ORDER BY lt.pk, l.display_order, l.pk
    """), {"code_pk": code_pk}).mappings().all()

    result = {}
    for row in rows:
        key = row["short_name"] or "other"
        result.setdefault(key, []).append(row["url"])
    return result


def _keywords_for_code(db_session, code_pk):
    """Return list of keyword labels for a code."""
    rows = db_session.execute(text("""
        SELECT k.label
        FROM keyword k
        JOIN code_to_keyword ck ON k.pk = ck.keyword_pk
        WHERE ck.code_pk = :code_pk
        ORDER BY k.label
    """), {"code_pk": code_pk}).fetchall()
    return [row.label for row in rows]


def _pubdate(code):
    """Derive pubdate string MM/CCYY from ascl_id and century."""
    ascl_id = code.ascl_id  # e.g. "9903.001"
    century = getattr(code, "century", 20)
    month = ascl_id[2:4]
    year = str(century) + ascl_id[0:2]
    return f"{month}/{year}"


def _build_code_dict(code, db_session, include_keywords=True):
    """Build the common dict used by JSON and XML exports."""
    links = _links_by_type(db_session, code.pk)

    d = {
        "ascl_id": code.ascl_id,
        "title": code.title,
        "credit": code.credit,
        "abstract": code.abstract,
        "topic_id": code.topic_id,
        "bibcode": code.bibcode or "",
        "views": code.views,
        "preferred_citation": code.citation_method or "",
    }

    d["site_list"] = links.get("code-site", [])
    d["described_in"] = links.get("described-in", [])
    d["used_in"] = links.get("used-in", [])

    if include_keywords:
        d["keywords"] = _keywords_for_code(db_session, code.pk)

    return d


def _published_codes_query():
    """Return the base WHERE clause text for published codes."""
    return "published = 1 AND ascl_id != '0000.000'"


# ---------------------------------------------------------------------------
# /code/json — All published codes as JSON
# ---------------------------------------------------------------------------

@exports_page.route("/code/json")
def code_json():
    db_session = _get_session()

    codes = db_session.execute(text(
        f"SELECT pk, ascl_id, title, credit, abstract, topic_id, bibcode, "
        f"views, citation_method, century "
        f"FROM codes WHERE {_published_codes_query()} ORDER BY pk"
    )).mappings().all()

    result = {}
    for row in codes:
        code_pk = row["pk"]
        links = _links_by_type(db_session, code_pk)
        keywords = _keywords_for_code(db_session, code_pk)

        result[str(code_pk)] = {
            "ascl_id": row["ascl_id"],
            "title": row["title"],
            "credit": row["credit"],
            "abstract": row["abstract"],
            "topic_id": row["topic_id"],
            "bibcode": row["bibcode"] or "",
            "views": row["views"],
            "preferred_citation": row["citation_method"] or "",
            "site_list": links.get("code-site", []),
            "used_in": links.get("used-in", []),
            "described_in": links.get("described-in", []),
            "keywords": keywords,
        }

    return Response(
        flask.json.dumps(result),
        mimetype="application/json",
    )


# ---------------------------------------------------------------------------
# /code/xml — 100 most recent published codes as XML
# /code/dci — All published codes as XML
# /code/dci/<date> — Codes updated since <date> as XML
# ---------------------------------------------------------------------------

def _xml_export(limit=None, since_date=None):
    """Shared logic for XML exports."""
    db_session = _get_session()

    where = _published_codes_query()
    params = {}

    if since_date:
        where += " AND time_updated > :since"
        params["since"] = since_date.strftime("%Y-%m-%d %H:%M:%S")

    sql = (
        f"SELECT pk, ascl_id, title, credit, abstract, topic_id, bibcode, "
        f"views, citation_method, century "
        f"FROM codes WHERE {where} ORDER BY pk"
    )
    if limit:
        sql += f" LIMIT {int(limit)}"

    codes = db_session.execute(text(sql), params).mappings().all()

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<ascl>"]

    for row in codes:
        code_pk = row["pk"]
        links = _links_by_type(db_session, code_pk)
        keywords = _keywords_for_code(db_session, code_pk)

        ascl_id = row["ascl_id"]
        century = row["century"] or 20
        pubdate = f"{ascl_id[2:4]}/{century}{ascl_id[0:2]}"

        lines.append("<code>")
        lines.append(f"\t<ascl_id>{xml_escape(ascl_id)}</ascl_id>")
        lines.append(f"\t<title>{xml_escape(row['title'])}</title>")
        lines.append(f"\t<credit>{xml_escape(row['credit'])}</credit>")
        lines.append(f"\t<abstract>{xml_escape(row['abstract'])}</abstract>")
        lines.append(f"\t<bibcode>{xml_escape(row['bibcode'] or '')}</bibcode>")
        lines.append(f"\t<pubdate>{xml_escape(pubdate)}</pubdate>")
        lines.append(f"\t<topic_id>{xml_escape(str(row['topic_id'] or ''))}</topic_id>")
        lines.append(f"\t<views>{xml_escape(str(row['views']))}</views>")

        citation = row["citation_method"] or ""
        if citation:
            lines.append(f"\t<preferred_citation>{xml_escape(citation)}</preferred_citation>")

        for url in links.get("code-site", []):
            lines.append(f"\t<site>{xml_escape(url)}</site>")
        for url in links.get("used-in", []):
            lines.append(f"\t<used_in>{xml_escape(url)}</used_in>")
        for url in links.get("described-in", []):
            lines.append(f"\t<described_in>{xml_escape(url)}</described_in>")
        for kw in keywords:
            lines.append(f"\t<keywords>{xml_escape(kw)}</keywords>")

        lines.append("</code>")

    lines.append("</ascl>")

    return Response("\n".join(lines), mimetype="application/xml")


@exports_page.route("/code/xml")
def code_xml():
    return _xml_export(limit=100)


@exports_page.route("/code/dci")
def code_dci():
    return _xml_export()


@exports_page.route("/code/dci/<path:date_str>")
def code_dci_since(date_str):
    dt = _parse_date(date_str)
    if dt is None:
        abort(400, description="Invalid date.")
    return _xml_export(since_date=dt)


# ---------------------------------------------------------------------------
# /code/ole/<date> — JSON export (restricted to 1-month-old data for guests)
# ---------------------------------------------------------------------------

@exports_page.route("/code/ole/<path:date_str>")
def code_ole(date_str):
    dt = _parse_date(date_str)
    if dt is None:
        abort(400, description="Invalid date.")

    logged_in = "user_id" in session
    one_month_ago = datetime.now() - timedelta(days=30)

    if not logged_in and dt < one_month_ago:
        return Response("You need to be logged in to view old data.",
                        status=403, mimetype="text/plain")

    db_session = _get_session()
    since = dt.strftime("%Y-%m-%d %H:%M:%S")

    codes = db_session.execute(text(
        f"SELECT pk, ascl_id, title, credit, abstract, topic_id, bibcode, "
        f"views, century "
        f"FROM codes WHERE {_published_codes_query()} AND time_updated > :since ORDER BY pk"
    ), {"since": since}).mappings().all()

    result = {}
    for row in codes:
        code_pk = row["pk"]
        links = _links_by_type(db_session, code_pk)

        result[str(code_pk)] = {
            "ascl_id": row["ascl_id"],
            "title": row["title"],
            "credit": row["credit"],
            "abstract": row["abstract"],
            "topic_id": row["topic_id"],
            "bibcode": row["bibcode"] or "",
            "views": row["views"],
            "site_list": links.get("code-site", []),
            "used_in": links.get("used-in", []),
            "described_in": links.get("described-in", []),
        }

    return Response(
        flask.json.dumps(result),
        mimetype="application/json",
    )


# ---------------------------------------------------------------------------
# /code/ads/<date> — ADS plain-text export
# ---------------------------------------------------------------------------

# URL fragments that indicate a URL contains a bibcode
_BIBCODE_URL_PATTERNS = [
    "cdsbib?",
    "adsabs.harvard.edu/abs/",
    "ui.adsabs.harvard.edu/#abs/",
    "ui.adsabs.harvard.edu/abs/",
    "ads.ari.uni-heidelberg.de/abs/",
    "esoads.eso.org/abs/",
    "cdsads.u-strasbg.fr/abs/",
]


def _extract_bibcode_from_url(url):
    """If the URL contains a known ADS bibcode pattern, return the bibcode portion."""
    from urllib.parse import unquote
    for pattern in _BIBCODE_URL_PATTERNS:
        pos = url.find(pattern)
        if pos != -1:
            return unquote(url[pos + len(pattern):]).strip()
    return None


@exports_page.route("/code/ads/<path:date_str>")
def code_ads(date_str):
    dt = _parse_date(date_str)
    if dt is None:
        abort(400, description="Invalid date.")

    logged_in = "user_id" in session
    one_month_ago = datetime.now() - timedelta(days=30)

    if not logged_in and dt < one_month_ago:
        return Response("You need to be logged in to view old data.",
                        status=403, mimetype="text/plain")

    db_session = _get_session()
    since = dt.strftime("%Y-%m-%d %H:%M:%S")

    codes = db_session.execute(text(
        f"SELECT pk, ascl_id, title, credit, abstract, bibcode, doi, "
        f"citation_method, century "
        f"FROM codes WHERE {_published_codes_query()} AND time_updated > :since ORDER BY pk"
    ), {"since": since}).mappings().all()

    lines = [
        f"Date interpreted as: {since}",
        f"Returned {len(codes)} records",
        "",
    ]

    for row in codes:
        code_pk = row["pk"]
        links = _links_by_type(db_session, code_pk)
        keywords = _keywords_for_code(db_session, code_pk)

        ascl_id = row["ascl_id"]
        century = row["century"] or 20
        D = f"{ascl_id[2:4]}/{century}{ascl_id[0:2]}"

        credit = re.sub(r"<[^>]+>", "", row["credit"] or "")
        credit = html.unescape(credit)

        title = re.sub(r"<[^>]+>", "", row["title"] or "")
        title = html.unescape(title)
        title = re.sub(r"\s+", " ", title).strip()

        abstract = row["abstract"] or ""
        abstract = re.sub(r"[\n\r]+", "\n   ", abstract)
        # Preserve <a> tags, strip everything else
        abstract_clean = re.sub(r"<(?!/?a[ >])[^>]+>", "", abstract)
        abstract_clean = html.unescape(abstract_clean)

        # %R bibcode
        lines.append(f"%R {row['bibcode'] or ''}")
        # %A authors
        lines.append(f"%A {credit}")
        # %J journal
        lines.append(f"%J Astrophysics Source Code Library, record ascl:{ascl_id}")
        # %D date
        lines.append(f"%D {D}")
        # %T title
        lines.append(f"%T {title}")

        # %I links with bibcode extraction
        i_line = f"%I ELECTR: https://ascl.net/{ascl_id}"

        for url in links.get("described-in", []):
            bibcode = _extract_bibcode_from_url(url)
            if bibcode:
                i_line += f"; ASCL_D: {bibcode}"

        for url in links.get("used-in", []):
            bibcode = _extract_bibcode_from_url(url)
            if bibcode:
                i_line += f"; ASCL_U: {bibcode}"

        lines.append(i_line)

        # %B abstract
        lines.append(f"%B {abstract_clean}")

        # %K keywords
        kw_str = "Software"
        if keywords:
            kw_str += ", " + ", ".join(keywords)
        lines.append(f"%K {kw_str}")

        lines.append("")

    return Response("\n".join(lines), mimetype="text/plain; charset=utf-8")
