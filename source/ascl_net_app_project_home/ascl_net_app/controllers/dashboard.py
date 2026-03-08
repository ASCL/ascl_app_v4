#!/usr/bin/python

import flask
from flask import render_template, session
from sqlalchemy import func, extract, desc, text, distinct
from datetime import datetime

dashboard_page = flask.Blueprint("dashboard_page", __name__, url_prefix="/dashboard")

# ADS journal abbreviations → full names
_JOURNAL_NAMES = {
	"ApJ": "The Astrophysical Journal",
	"ApJS": "The Astrophysical Journal Supplement Series",
	"MNRAS": "Monthly Notices of the Royal Astronomical Society",
	"A&A": "Astronomy & Astrophysics",
	"AJ": "The Astronomical Journal",
	"PASP": "Publications of the Astronomical Society of the Pacific",
	"PASA": "Publications of the Astronomical Society of Australia",
	"PASJ": "Publications of the Astronomical Society of Japan",
	"arXiv": "arXiv e-prints",
	"PhRvD": "Physical Review D",
	"PhRvL": "Physical Review Letters",
	"PhRvA": "Physical Review A",
	"PhRvB": "Physical Review B",
	"PhRvC": "Physical Review C",
	"PhRvE": "Physical Review E",
	"PhRvF": "Physical Review Fluids",
	"PhRvR": "Physical Review Research",
	"PhRvX": "Physical Review X",
	"PhRvP": "Physical Review Physics Education Research",
	"JCAP": "Journal of Cosmology and Astroparticle Physics",
	"RNAAS": "Research Notes of the AAS",
	"NatAs": "Nature Astronomy",
	"Natur": "Nature",
	"NatCo": "Nature Communications",
	"NatSD": "Nature Scientific Data",
	"NatSR": "Nature Scientific Reports",
	"NatRP": "Nature Reviews Physics",
	"NRvEE": "Nature Reviews Earth & Environment",
	"RAA": "Research in Astronomy and Astrophysics",
	"A&C": "Astronomy and Computing",
	"PSJ": "The Planetary Science Journal",
	"OJAp": "The Open Journal of Astrophysics",
	"JOSS": "Journal of Open Source Software",
	"Sci": "Science",
	"SciA": "Science Advances",
	"RASTI": "RAS Techniques and Instruments",
	"ASPC": "Astronomical Society of the Pacific Conference Series",
	"IAUS": "IAU Symposium Proceedings",
	"JApA": "Journal of Astrophysics and Astronomy",
	"Galax": "Galaxies",
	"PhDT": "PhD Thesis",
	"SPIE1": "Proc. SPIE",
	"SPIE": "Proc. SPIE",
	"JATIS": "Journal of Astronomical Telescopes, Instruments, and Systems",
	"exha": "Experimental Astronomy",
	"AstL": "Astronomy Letters",
	"Univ": "Universe",
	"AcA": "Acta Astronomica",
	"NewA": "New Astronomy",
	"AN": "Astronomische Nachrichten",
	"CoSka": "Contributions of the Astronomical Observatory Skalnat\u00e9 Pleso",
	"JPhCS": "Journal of Physics: Conference Series",
	"FrASS": "Frontiers in Astronomy and Space Sciences",
	"LRCA": "Living Reviews in Computational Astrophysics",
	"BSRSL": "Bulletin de la Soci\u00e9t\u00e9 Royale des Sciences de Li\u00e8ge",
	"AstBu": "Astrophysical Bulletin",
	"ARA&A": "Annual Review of Astronomy and Astrophysics",
	"Ap&SS": "Astrophysics and Space Science",
	"JHEAp": "Journal of High Energy Astrophysics",
	"EPJWC": "EPJ Web of Conferences",
	"ARep": "Astronomy Reports",
	"JAVSO": "Journal of the AAVSO",
	"Icar": "Icarus",
	"CQGra": "Classical and Quantum Gravity",
	"SoPh": "Solar Physics",
	"MmSAI": "Memorie della Societ\u00e0 Astronomica Italiana",
	"RMxAA": "Revista Mexicana de Astronom\u00eda y Astrof\u00edsica",
	"EPJC": "European Physical Journal C",
	"A&ARv": "Astronomy and Astrophysics Review",
	"PDU": "Physics of the Dark Universe",
	"SCPMA": "Science China Physics, Mechanics & Astronomy",
	"SSRv": "Space Science Reviews",
	"BAAS": "Bulletin of the AAS",
	"ExA": "Experimental Astronomy",
	"AdSpR": "Advances in Space Research",
	"LRR": "Living Reviews in Relativity",
	"LRSP": "Living Reviews in Solar Physics",
	"IJMPD": "International Journal of Modern Physics D",
	"PhPl": "Physics of Plasmas",
	"PNAS": "Proceedings of the National Academy of Sciences",
	"NewAR": "New Astronomy Reviews",
	"SpWea": "Space Weather",
	"sf2a": "SF2A Proceedings",
	"JKAS": "Journal of the Korean Astronomical Society",
	"RMxAC": "Revista Mexicana de Astronom\u00eda y Astrof\u00edsica Conference Series",
	"EPJA": "European Physical Journal A",
	"EPJP": "European Physical Journal Plus",
	"EPJST": "European Physical Journal Special Topics",
	"EPJD": "European Physical Journal D",
	"EPJH": "European Physical Journal H",
	"PhR": "Physics Reports",
	"JPhG": "Journal of Physics G: Nuclear and Particle Physics",
	"PTEP": "Progress of Theoretical and Experimental Physics",
	"Msngr": "The Messenger",
	"JAI": "Journal of Astronomical Instrumentation",
	"RSEnv": "Remote Sensing of Environment",
	"RaSc": "Radio Science",
	"GeoRL": "Geophysical Research Letters",
	"JHEP": "Journal of High Energy Physics",
	"RPPh": "Reports on Progress in Physics",
	"ARNPS": "Annual Review of Nuclear and Particle Science",
	"RvMP": "Reviews of Modern Physics",
	"Astro": "Astrobiology",
	"AstHe": "Astronomische Nachrichten",
	"CmPhy": "Communications Physics",
	"IBVS": "Information Bulletin on Variable Stars",
	"OEJV": "Open European Journal on Variable Stars",
	"TJAA": "Turkish Journal of Astronomy and Astrophysics",
	"OAst": "Open Astronomy",
	"SerAJ": "Serbian Astronomical Journal",
	"BlgAJ": "Bulgarian Astronomical Journal",
	"BAAA": "Bolet\u00edn de la Asociaci\u00f3n Argentina de Astronom\u00eda",
	"BASBr": "Bulletin of the Astronomical Society of Brazil",
	"AcASn": "Acta Astronomica Sinica",
	"ChJPh": "Chinese Journal of Physics",
	"ChPhL": "Chinese Physics Letters",
	"SSPMA": "SCIENTIA SINICA Physica, Mechanica & Astronomica",
	"JGRA": "Journal of Geophysical Research: Space Physics",
	"JGRE": "Journal of Geophysical Research: Planets",
	"P&SS": "Planetary and Space Science",
	"Heliy": "Heliyon",
	"RemS": "Remote Sensing",
	"GReGr": "General Relativity and Gravitation",
	"GrCo": "Gravitation and Cosmology",
	"CeMDA": "Celestial Mechanics and Dynamical Astronomy",
	"PhLB": "Physics Letters B",
	"NJPh": "New Journal of Physics",
	"Atmos": "Atmosphere",
	"JQSRT": "Journal of Quantitative Spectroscopy and Radiative Transfer",
	"SoftX": "SoftwareX",
	"ComAC": "Computational Astrophysics and Cosmology",
	"JChPh": "Journal of Chemical Physics",
	"JCTC": "Journal of Chemical Theory and Computation",
	"JFM": "Journal of Fluid Mechanics",
	"PhFl": "Physics of Fluids",
	"EcoEv": "Ecology and Evolution",
	"PLoSO": "PLoS ONE",
	"Bioin": "Bioinformatics",
	"JOSAB": "Journal of the Optical Society of America B",
	"ApOpt": "Applied Optics",
	"OptL": "Optics Letters",
	"OExpr": "Optics Express",
	"JPlPh": "Journal of Plasma Physics",
	"Senso": "Sensors",
	"Entrp": "Entropy",
	"Symm": "Symmetry",
	"Atoms": "Atoms",
	"Parti": "Particles",
	"Quant": "Quantum",
	"JInst": "Journal of Instrumentation",
	"Ene": "Energies",
	"ScTEn": "Science of The Total Environment",
	"Fluid": "Fluids",
	"PhyS": "Physica Scripta",
	"INASR": "Indian National Academy of Science Review",
	"JASS": "Journal of Astronomy and Space Sciences",
	"MLS&T": "Machine Learning: Science and Technology",
	"Fore": "Forecasting",
	"IzKry": "Izvestiya Krymskoi Astrofizicheskoi Observatorii",
	"ASSL": "Astrophysics and Space Science Library",
	"AcPol": "Acta Polytechnica",
	"WRR": "Water Resources Research",
	"AMT": "Atmospheric Measurement Techniques",
	"ACP": "Atmospheric Chemistry and Physics",
	"Geosc": "Geosciences",
	"GeoJI": "Geophysical Journal International",
	"JAtS": "Journal of the Atmospheric Sciences",
	"MWRv": "Monthly Weather Review",
	"Ge&Ae": "Geomagnetism and Aeronomy",
	"JASTP": "Journal of Atmospheric and Solar-Terrestrial Physics",
	"SoSyR": "Solar System Research",
	"PhyU": "Physics-Uspekhi",
	"JETPL": "JETP Letters",
	"Ap": "Astrophysics",
	"KFNTS": "Kinematika i Fizika Nebesnykh Tel Supplement",
	"KPCB": "Kinematics and Physics of Celestial Bodies",
	"BrJPh": "Brazilian Journal of Physics",
	"PrPNP": "Progress in Particle and Nuclear Physics",
	"ITSP": "IEEE Transactions on Signal Processing",
	"IEEEA": "IEEE Access",
	"PhB": "Physics Letters B",
	"tsc2": "The 2nd Thinkshop on Cool Stars",
	"EPSC": "European Planetary Science Congress",
	"icrc": "International Cosmic Ray Conference",
	"zndo": "Zenodo",
	"ascl": "ASCL",
	"yCat": "VizieR Online Data Catalog",
	"ivoa": "IVOA",
	"LNCS": "Lecture Notes in Computer Science",
	"AIPC": "AIP Conference Proceedings",
}


def _get_db_session():
	from ascl_net_app.model.database import Database
	return Database().Session()


def _get_models():
	import ascl_core.database.ascldb.ASCLModelClasses as ascldb
	return ascldb


def _build_dashboard_context():
	"""Build the template context dict for the dashboard (reusable by admin route)."""
	db_session = _get_db_session()
	ascldb = _get_models()

	# === Overall Statistics ===
	stats = {}

	# Total codes and published counts
	overall = (
		db_session.query(
			func.count(ascldb.ASCLCode.pk).label("total_codes"),
			func.sum(func.IF(ascldb.ASCLCode.published == 1, 1, 0)).label("published_codes"),
			func.sum(func.IF(ascldb.ASCLCode.published == 0, 1, 0)).label("unpublished_codes"),
			func.sum(func.IF(ascldb.ASCLCode.archived == 1, 1, 0)).label("archived_codes"),
		)
		.one()
	)
	stats["total_codes"] = overall.total_codes or 0
	stats["published_codes"] = overall.published_codes or 0
	stats["unpublished_codes"] = overall.unpublished_codes or 0
	stats["archived_codes"] = overall.archived_codes or 0

	# Total citations
	stats["total_citations"] = (
		db_session.query(func.count(ascldb.Citation.pk))
		.scalar() or 0
	)

	# Total keywords
	stats["total_keywords"] = (
		db_session.query(func.count(ascldb.Keyword.pk))
		.scalar() or 0
	)

	# Total links
	stats["total_links"] = (
		db_session.query(func.count(ascldb.Link.pk))
		.scalar() or 0
	)

	# Codes indexed in ADS (have a bibcode)
	ads_indexed = (
		db_session.query(func.count(ascldb.ASCLCode.pk))
		.filter(ascldb.ASCLCode.published == 1)
		.filter(ascldb.ASCLCode.ascl_id != '0000.000')
		.filter(ascldb.ASCLCode.bibcode != None)
		.filter(ascldb.ASCLCode.bibcode != '')
		.scalar() or 0
	)
	stats["ads_indexed"] = ads_indexed
	stats["ads_indexed_pct"] = round(100.0 * int(ads_indexed) / int(stats["published_codes"])) if stats["published_codes"] else 0

	# Codes with at least one citation
	codes_with_citations = (
		db_session.query(func.count(distinct(ascldb.Citation.code_pk)))
		.filter(ascldb.Citation.type == 'ascl_entry')
		.scalar() or 0
	)
	stats["codes_with_citations"] = codes_with_citations
	stats["codes_with_citations_pct"] = round(100.0 * int(codes_with_citations) / int(stats["published_codes"])) if stats["published_codes"] else 0

	# Pending submissions (unpublished, not archived)
	pending = (
		db_session.query(func.count(ascldb.ASCLCode.pk))
		.filter(ascldb.ASCLCode.published == 0)
		.filter(ascldb.ASCLCode.ascl_id != '0000.000')
		.filter((ascldb.ASCLCode.archived == 0) | (ascldb.ASCLCode.archived == None))
		.scalar() or 0
	)
	stats["pending_submissions"] = pending

	# === Codes Added by Year (from ascl_id, most recent 5 years with data) ===
	# Matches production PHP: concat(century, substring(ascl_id, 1, 2))
	# ASCL ID format: YYMM.NNN (e.g., 2312.001 = December 2023)

	# Get all years with data, then take the most recent 5
	sql = text("""
		SELECT CONCAT(century, SUBSTRING(ascl_id, 1, 2)) AS year,
		       COUNT(pk) AS count
		FROM codes
		WHERE ascl_id != '0000.000'
		GROUP BY year
		ORDER BY year DESC
		LIMIT 5
	""")

	result = db_session.execute(sql)
	# Reverse to show in ascending order (oldest to newest)
	stats["codes_by_year"] = sorted([
		{"year": int(row.year), "count": row.count}
		for row in result
	], key=lambda x: x["year"])

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

	# === Citations by Journal (top 10 + "Other" for pie; full list for table) ===
	sql_journals = text("""
		SELECT journal, COUNT(*) AS cnt
		FROM citations
		WHERE type = 'ascl_entry'
		GROUP BY journal
		ORDER BY cnt DESC
	""")
	result_journals = db_session.execute(sql_journals)
	journal_rows = [{"journal": row.journal.rstrip('.'), "count": row.cnt} for row in result_journals]
	total_journal_citations = sum(r["count"] for r in journal_rows)
	for j in journal_rows:
		j["full_name"] = _JOURNAL_NAMES.get(j["journal"], "")
		j["pct"] = round(100.0 * j["count"] / total_journal_citations, 1) if total_journal_citations else 0

	# Pie chart: top 10 + Other
	top_journals = list(journal_rows[:10])
	other_count = sum(r["count"] for r in journal_rows[10:])
	if other_count:
		other_pct = round(100.0 * other_count / total_journal_citations, 1) if total_journal_citations else 0
		top_journals.append({"journal": "Other", "full_name": "", "count": other_count, "pct": other_pct})
	stats["citations_by_journal"] = top_journals
	stats["all_journal_citations"] = journal_rows

	# === Most Cited Codes (codes with most citations) ===
	most_cited = (
		db_session.query(
			ascldb.ASCLCode,
			func.count(ascldb.Citation.pk).label("citation_count")
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

	# === Admin-Only Stats (only when logged in) ===
	is_admin = bool(session.get("user_id"))
	admin_stats = None
	if is_admin:
		admin_stats = {}

		# Codes awaiting IDs (ascl_id = '0000.000')
		awaiting_total = (
			db_session.query(func.count(ascldb.ASCLCode.pk))
			.filter(ascldb.ASCLCode.ascl_id == '0000.000')
			.scalar() or 0
		)
		awaiting_unpublished = (
			db_session.query(func.count(ascldb.ASCLCode.pk))
			.filter(ascldb.ASCLCode.ascl_id == '0000.000')
			.filter(ascldb.ASCLCode.published == 0)
			.scalar() or 0
		)
		admin_stats["awaiting_ids_total"] = awaiting_total
		admin_stats["awaiting_ids_published"] = awaiting_total - awaiting_unpublished
		admin_stats["awaiting_ids_unpublished"] = awaiting_unpublished

		# Missing citation method (published codes with assigned IDs)
		admin_stats["missing_citation_method"] = (
			db_session.query(func.count(ascldb.ASCLCode.pk))
			.filter(ascldb.ASCLCode.ascl_id != '0000.000')
			.filter((ascldb.ASCLCode.citation_method == None) | (ascldb.ASCLCode.citation_method == ''))
			.scalar() or 0
		)

		# Missing both "described in" (link_type 4) and "used in" (link_type 5)
		codes_with_di_or_ui = (
			db_session.query(distinct(ascldb.Link.code_pk))
			.filter(ascldb.Link.link_type_pk.in_([4, 5]))
			.subquery()
		)
		admin_stats["missing_described_used"] = (
			db_session.query(func.count(ascldb.ASCLCode.pk))
			.filter(~ascldb.ASCLCode.pk.in_(db_session.query(codes_with_di_or_ui)))
			.scalar() or 0
		)
		admin_stats["missing_described_used_pub"] = (
			db_session.query(func.count(ascldb.ASCLCode.pk))
			.filter(~ascldb.ASCLCode.pk.in_(db_session.query(codes_with_di_or_ui)))
			.filter(ascldb.ASCLCode.ascl_id != '0000.000')
			.scalar() or 0
		)

		# Codes submitted by authors (notes containing "Submitted by:")
		admin_stats["submitted_by_authors"] = (
			db_session.query(func.count(ascldb.ASCLCode.pk))
			.filter(ascldb.ASCLCode.notes.like('Submitted by:%'))
			.scalar() or 0
		)
		admin_stats["submitted_by_authors_with_ids"] = (
			db_session.query(func.count(ascldb.ASCLCode.pk))
			.filter(ascldb.ASCLCode.notes.like('Submitted by:%'))
			.filter(ascldb.ASCLCode.ascl_id != '0000.000')
			.scalar() or 0
		)

	db_session.close()

	return {"stats": stats, "admin_stats": admin_stats, "is_admin": is_admin}


@dashboard_page.route("/", methods=["GET"])
def dashboard_home():
	"""Public statistics dashboard showing ASCL metrics and trends."""
	ctx = _build_dashboard_context()
	return render_template("dashboard.html", **ctx)
