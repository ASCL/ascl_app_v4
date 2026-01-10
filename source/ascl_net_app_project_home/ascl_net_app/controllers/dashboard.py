#!/usr/bin/python

import flask
from flask import render_template
from sqlalchemy import func, extract, desc
from datetime import datetime

dashboard_page = flask.Blueprint("dashboard_page", __name__, url_prefix="/dashboard")


def _get_db_session():
	from ascl_core.database.connections import Trillian2Connection as db
	return db.Session()


def _get_models():
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb
	return ascldb


@dashboard_page.route("/", methods=["GET"])
def dashboard_home():
	"""Public statistics dashboard showing ASCL metrics and trends."""
	db_session = _get_db_session()
	ascldb = _get_models()

	# === Overall Statistics ===
	stats = {}

	# Total codes, views, and published counts
	overall = (
		db_session.query(
			func.count(ascldb.ASCLCode.pk).label("total_codes"),
			func.sum(ascldb.ASCLCode.views).label("total_views"),
			func.sum(func.IF(ascldb.ASCLCode.published == 1, 1, 0)).label("published_codes"),
			func.sum(func.IF(ascldb.ASCLCode.published == 0, 1, 0)).label("unpublished_codes"),
			func.sum(func.IF(ascldb.ASCLCode.archived == 1, 1, 0)).label("archived_codes"),
		)
		.one()
	)
	stats["total_codes"] = overall.total_codes or 0
	stats["total_views"] = overall.total_views or 0
	stats["published_codes"] = overall.published_codes or 0
	stats["unpublished_codes"] = overall.unpublished_codes or 0
	stats["archived_codes"] = overall.archived_codes or 0

	# Total citations
	stats["total_citations"] = (
		db_session.query(func.count(ascldb.Citation.id))
		.scalar() or 0
	)

	# Total keywords
	stats["total_keywords"] = (
		db_session.query(func.count(ascldb.Keyword.id))
		.scalar() or 0
	)

	# Total links
	stats["total_links"] = (
		db_session.query(func.count(ascldb.Link.id))
		.scalar() or 0
	)

	# === Codes Added by Year (from ascl_id, last 10 years) ===
	# Matches production PHP: concat(century, substring(ascl_id, 1, 2))
	# ASCL ID format: YYMM.NNN (e.g., 2312.001 = December 2023)
	from sqlalchemy import text

	current_year = datetime.now().year
	cutoff_year = current_year - 10

	# Use raw SQL to match PHP exactly (avoids SQLAlchemy column reference issues)
	sql = text("""
		SELECT CONCAT(century, SUBSTRING(ascl_id, 1, 2)) AS year,
		       COUNT(pk) AS count
		FROM codes
		WHERE CONCAT(century, SUBSTRING(ascl_id, 1, 2)) > :cutoff_year
		  AND ascl_id != '0000.000'
		GROUP BY year
		ORDER BY year ASC
	""")

	result = db_session.execute(sql, {"cutoff_year": str(cutoff_year)})
	stats["codes_by_year"] = [
		{"year": int(row.year), "count": row.count}
		for row in result
	]

	# === Citations by Year (from 2012 onwards) ===
	# Matches production PHP dashboard
	sql_citations = text("""
		SELECT year, COUNT(*) AS count
		FROM citations
		WHERE type = 'ascl_entry'
		  AND year >= 2012
		GROUP BY year
		ORDER BY year ASC
	""")

	result_citations = db_session.execute(sql_citations)
	stats["citations_by_year"] = [
		{"year": int(row.year), "count": row.count}
		for row in result_citations
	]

	# === Most Viewed Codes ===
	most_viewed = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.published == 1)
		.filter(ascldb.ASCLCode.ascl_id != '0000.000')
		.order_by(desc(ascldb.ASCLCode.views))
		.limit(10)
		.all()
	)
	stats["most_viewed"] = most_viewed

	# === Most Cited Codes (codes with most citations) ===
	most_cited = (
		db_session.query(
			ascldb.ASCLCode,
			func.count(ascldb.Citation.id).label("citation_count")
		)
		.join(ascldb.Citation, ascldb.ASCLCode.pk == ascldb.Citation.code_pk, isouter=True)
		.filter(ascldb.ASCLCode.published == 1)
		.filter(ascldb.ASCLCode.ascl_id != '0000.000')
		.group_by(ascldb.ASCLCode.pk)
		.order_by(desc("citation_count"))
		.limit(10)
		.all()
	)
	stats["most_cited"] = [
		{"code": row.ASCLCode, "citation_count": row.citation_count}
		for row in most_cited
	]

	# === Recently Added Codes ===
	recently_added = (
		db_session.query(ascldb.ASCLCode)
		.filter(ascldb.ASCLCode.published == 1)
		.filter(ascldb.ASCLCode.ascl_id != '0000.000')
		.order_by(desc(ascldb.ASCLCode.time_added))
		.limit(10)
		.all()
	)
	stats["recently_added"] = recently_added

	# === Top Keywords ===
	top_keywords = (
		db_session.query(
			ascldb.Keyword,
			func.count(ascldb.ASCLCodeToKeyword.code_id).label("code_count")
		)
		.join(ascldb.ASCLCodeToKeyword, ascldb.Keyword.id == ascldb.ASCLCodeToKeyword.keyword_id)
		.group_by(ascldb.Keyword.id)
		.order_by(desc("code_count"))
		.limit(20)
		.all()
	)
	stats["top_keywords"] = [
		{"keyword": row.Keyword, "code_count": row.code_count}
		for row in top_keywords
	]

	# === Codes with Missing Metadata ===
	missing_doi = (
		db_session.query(func.count(ascldb.ASCLCode.pk))
		.filter(ascldb.ASCLCode.published == 1)
		.filter((ascldb.ASCLCode.doi == None) | (ascldb.ASCLCode.doi == ""))
		.scalar() or 0
	)
	missing_bibcode = (
		db_session.query(func.count(ascldb.ASCLCode.pk))
		.filter(ascldb.ASCLCode.published == 1)
		.filter((ascldb.ASCLCode.bibcode == None) | (ascldb.ASCLCode.bibcode == ""))
		.scalar() or 0
	)
	stats["missing_metadata"] = {
		"doi": missing_doi,
		"bibcode": missing_bibcode,
	}

	# === Current Year Stats ===
	current_year = datetime.now().year
	codes_this_year = (
		db_session.query(func.count(ascldb.ASCLCode.pk))
		.filter(extract("year", ascldb.ASCLCode.time_added) == current_year)
		.filter(ascldb.ASCLCode.published == 1)
		.scalar() or 0
	)
	stats["codes_this_year"] = codes_this_year

	db_session.close()

	return render_template("dashboard.html", stats=stats)
