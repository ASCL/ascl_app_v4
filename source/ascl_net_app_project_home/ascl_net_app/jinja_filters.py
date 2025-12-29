#!/usr/bin/python

'''
This file contains all custom Jinja2 filters.

Following the template below, new filters can be added here
and will be automatically registered.
'''

import flask
import jinja2
import re

# Jinja2 3.0+ moved Markup to markupsafe
try:
    from markupsafe import Markup
except ImportError:
    from jinja2 import Markup

# If the filter is to return HTML code and you don't want it autmatically
# escaped, return the value as "return Markup(value)".

blueprint = flask.Blueprint('jinja_filters', __name__)

# Ref: http://stackoverflow.com/questions/12288454/how-to-import-custom-jinja2-filters-from-another-file-and-using-flask

# Jinja2 3.0+ deprecated contextfilter - use pass_context instead
try:
    from jinja2 import pass_context
    contextfilter = pass_context
except ImportError:
    contextfilter = jinja2.contextfilter

# place these two decorators above every filter
@contextfilter
@blueprint.app_template_filter()
def j2split(context, value, delimiter=None):
	if delimiter == None:
		return value.split()
	else:
		return value.split(delimiter)

@contextfilter
@blueprint.app_template_filter()
def j2join(context, value, delimiter=","):
    return delimiter.join(value)

@contextfilter
@blueprint.app_template_filter()
def format_ascl_id(context, ascl_id):
    """Format ASCL ID as YYMM.NNN (e.g., 1404.008)"""
    if ascl_id is None:
        return "0000.000"

    # Handle string input (already formatted or integer string)
    if isinstance(ascl_id, str):
        if '.' in ascl_id:
            return ascl_id  # Already formatted
        ascl_id = int(ascl_id)

    # Convert integer to formatted string
    # ASCL IDs are stored as integers like 1404008 -> "1404.008"
    ascl_str = str(ascl_id).zfill(7)  # Pad to 7 digits
    return f"{ascl_str[:4]}.{ascl_str[4:]}"

@contextfilter
@blueprint.app_template_filter()
def format_date_header(context, date_str):
    """Format date string as 'YYYY Mon DD' (e.g., '2025 Dec 01')

    Matches PHP production format: date("Y M d", strtotime($k))
    Input: YYYY-MM-DD string (e.g., '2025-12-01')
    Output: 'YYYY Mon DD' (e.g., '2025 Dec 01')
    """
    from datetime import datetime

    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%Y %b %d')
    except (ValueError, TypeError):
        return date_str  # Return as-is if parsing fails

@contextfilter
@blueprint.app_template_filter()
def link_author_credit(context, credit_string):
	"""Convert author credits to linked author names

	Matches PHP production function: link_author_credit($string)
	Input: "Author One; Author Two; Author Three"
	Output: '<a href="/code/cs/Author%20One">Author One</a>; <a href="/code/cs/Author%20Two">Author Two</a>; ...'

	Each author name becomes a link to a credit search page (/code/cs/{name})
	where users can find all codes by that author.
	"""
	from urllib.parse import quote

	if not credit_string:
		return ''

	# Split by semicolon
	authors = credit_string.split(';')

	# Build linked author list
	linked_authors = []
	for author in authors:
		author = author.strip()
		if author:
			# URL-encode the author name and create link
			encoded_name = quote(author)
			linked_authors.append(f'<a href="/code/cs/{encoded_name}" class="local">{author}</a>')

	# Join with semicolons
	return Markup('; '.join(linked_authors))


@blueprint.app_template_filter()
def link_ascl_ids(text_value):
	"""Convert literal ASCL identifiers in text to links, preserving existing HTML."""
	if not text_value:
		return ""

	def _repl(match):
		ascl_id = match.group(1)
		return f'<a href="/{ascl_id}">ascl:{ascl_id}</a>'

	linked = re.sub(r"(?:ascl:)?(\\d{4}\\.\\d{3})", _repl, str(text_value))
	return Markup(linked)


@blueprint.app_template_filter()
def number_format(value):
	"""Format a number with thousands separators (e.g., 1234567 -> 1,234,567)"""
	if value is None:
		return "0"
	try:
		return "{:,}".format(int(value))
	except (ValueError, TypeError):
		return str(value)
