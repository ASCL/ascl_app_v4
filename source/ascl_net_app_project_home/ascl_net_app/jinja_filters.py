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
	"""Convert literal ASCL identifiers in text to links, preserving existing HTML.

	Also converts literal '\\n' sequences (stored in the database) to HTML line breaks,
	matching the PHP production site's auto_paragraph behavior.
	"""
	if not text_value:
		return ""

	text = str(text_value)

	# Convert newlines to HTML breaks, matching PHP production's auto_paragraph behavior.
	text = text.replace('\r\n', '\n').replace('\r', '\n')
	text = text.replace('\n\n', '<br><br>')
	text = text.replace('\n', '<br>')

	def _repl(match):
		ascl_id = match.group(1)
		return f'<a href="/{ascl_id}">ascl:{ascl_id}</a>'

	# Match plain ASCL IDs like "1710.002" or "ascl:1710.002", but avoid URL paths.
	pattern = r"(?<![\w/])(?:ascl:)?(\d{4}\.\d{3})(?!\d)"
	linked = re.sub(pattern, _repl, text)
	return Markup(linked)


@blueprint.app_template_filter()
def auto_link(text_value):
	"""Convert bare URLs in text to clickable links, preserving existing HTML.

	Matches the PHP production site's auto_link() helper, used for the
	'Preferred citation method' field. URLs already inside anchor tags
	(or any tag attributes) are left alone.
	"""
	if not text_value:
		return ""

	text = str(text_value)

	url_pattern = re.compile(r'(https?://[^\s<>\'"\)\]]+)', re.IGNORECASE)

	def _link_url(match):
		url = match.group(1)
		# Keep trailing sentence punctuation out of the link
		trailing = ''
		while url and url[-1] in '.,;:':
			trailing = url[-1] + trailing
			url = url[:-1]
		return f'<a href="{url}" target="_blank" rel="noopener">{url}</a>{trailing}'

	# Split out existing anchors and other tags so only plain-text
	# segments are linkified.
	token_pattern = re.compile(r'(<a\b[^>]*>.*?</a>|<[^>]+>)', re.IGNORECASE | re.DOTALL)
	parts = token_pattern.split(text)
	for i in range(0, len(parts), 2):  # even indices are plain text
		parts[i] = url_pattern.sub(_link_url, parts[i])

	return Markup(''.join(parts))


@blueprint.app_template_filter()
def citation_urls(text_value):
	"""Return the list of URLs in a citation_method string, or None if the
	text contains prose beyond a simple list of URLs.

	Lets the 'Preferred citation method' field render one link per line when
	it is just a list of URLs joined by connectors like ',' or 'and';
	callers fall back to auto_link for anything with real prose.
	"""
	if not text_value:
		return None

	text = str(text_value)
	url_pattern = re.compile(r'(https?://[^\s<>\'"\)\]]+)', re.IGNORECASE)
	urls = url_pattern.findall(text)
	if not urls:
		return None

	# If anything besides trivial connectors remains once the URLs are
	# removed, the field is prose — let the caller render it as text.
	remainder = url_pattern.sub(' ', text)
	remainder = re.sub(r'\b(?:and|or)\b', ' ', remainder, flags=re.IGNORECASE)
	if re.sub(r'[\s,;&.]+', '', remainder):
		return None

	# Keep trailing sentence punctuation out of the links
	cleaned = []
	for url in urls:
		while url and url[-1] in '.,;:':
			url = url[:-1]
		cleaned.append(url)
	return cleaned


def _strip_html(text):
	"""Remove HTML tags from text."""
	return re.sub(r'<[^>]+>', '', text)


@blueprint.app_template_filter()
def search_excerpt(text_value, query, context_chars=250):
	"""Create an excerpt around the first occurrence of the search term with highlighting.

	Returns a Markup string with the search term wrapped in <mark> tags.
	If the text is short enough, returns the full text with highlighting.
	"""
	if not text_value or not query:
		return text_value or ""

	text = _strip_html(str(text_value))
	query_lower = query.lower()
	text_lower = text.lower()

	# Find first occurrence
	pos = text_lower.find(query_lower)
	if pos == -1:
		# Term not found in plain text — show beginning with no highlight
		snippet = text[:context_chars * 2]
		if len(text) > context_chars * 2:
			snippet += "..."
		# Escape HTML in the snippet
		from markupsafe import escape
		return Markup(str(escape(snippet)))

	# Build excerpt window around the match
	start = max(0, pos - context_chars)
	end = min(len(text), pos + len(query) + context_chars)

	snippet = text[start:end]

	# Add ellipsis if we trimmed
	prefix = "..." if start > 0 else ""
	suffix = "..." if end < len(text) else ""

	# Escape HTML in the snippet, then highlight the search term
	from markupsafe import escape
	escaped = str(escape(snippet))

	# Case-insensitive replacement with <mark> tags
	highlighted = re.sub(
		re.escape(query),
		lambda m: f'<mark>{m.group(0)}</mark>',
		escaped,
		flags=re.IGNORECASE
	)

	return Markup(f'{prefix}{highlighted}{suffix}')


@blueprint.app_template_filter()
def highlight_search(text_value, query):
	"""Highlight all occurrences of the search term in the text with <mark> tags.

	Strips HTML from the input, then highlights.
	"""
	if not text_value or not query:
		return text_value or ""

	text = _strip_html(str(text_value))
	from markupsafe import escape
	escaped = str(escape(text))

	highlighted = re.sub(
		re.escape(query),
		lambda m: f'<mark>{m.group(0)}</mark>',
		escaped,
		flags=re.IGNORECASE
	)
	return Markup(highlighted)


@blueprint.app_template_filter()
def number_format(value):
	"""Format a number with thousands separators (e.g., 1234567 -> 1,234,567)"""
	if value is None:
		return "0"
	try:
		return "{:,}".format(int(value))
	except (ValueError, TypeError):
		return str(value)


def _escape_and_linkify(text):
	"""Escape HTML and convert URLs to clickable links.

	URLs are detected and wrapped in anchor tags that open in new tabs.
	The rest of the text is HTML-escaped.
	"""
	if not text:
		return ""

	# URL pattern - matches http/https URLs
	url_pattern = re.compile(
		r'(https?://[^\s<>\'")\]]+)',
		re.IGNORECASE
	)

	result = []
	last_end = 0

	for match in url_pattern.finditer(text):
		# Escape text before the URL
		before = text[last_end:match.start()]
		escaped_before = (before
			.replace('&', '&amp;')
			.replace('<', '&lt;')
			.replace('>', '&gt;'))
		result.append(escaped_before)

		# Add the URL as a link
		url = match.group(1)
		# Escape the URL for use in href attribute
		escaped_url = url.replace('&', '&amp;').replace('"', '&quot;')
		# Display URL - truncate if very long
		display_url = url if len(url) <= 60 else url[:57] + '...'
		display_url = (display_url
			.replace('&', '&amp;')
			.replace('<', '&lt;')
			.replace('>', '&gt;'))
		result.append(f'<a href="{escaped_url}" target="_blank" rel="noopener">{display_url}</a>')

		last_end = match.end()

	# Escape any remaining text after the last URL
	remaining = text[last_end:]
	escaped_remaining = (remaining
		.replace('&', '&amp;')
		.replace('<', '&lt;')
		.replace('>', '&gt;'))
	result.append(escaped_remaining)

	return ''.join(result)


@blueprint.app_template_filter()
def format_legacy_notes(notes_text):
	"""Parse and format legacy v3 notes into structured HTML.

	Legacy notes follow the format:
	YYYYMMDD initials: note content

	Example:
	20170603 aa: added citation info and additional ref
	20180408 kd: changed url from http to https

	Returns structured HTML table if parsing succeeds, otherwise returns
	the raw text in a pre-formatted block. URLs are automatically converted
	to clickable links that open in new tabs.
	"""
	if not notes_text:
		return ""

	from datetime import datetime

	# Pattern: 8 digits (date), space, 2-3 letters (initials), colon, content
	note_pattern = re.compile(r'^(\d{8})\s+([a-zA-Z]{2,3}):\s*(.*)$')

	lines = notes_text.strip().split('\n')
	parsed_notes = []
	unparsed_lines = []

	for line in lines:
		line = line.strip()
		if not line:
			continue

		match = note_pattern.match(line)
		if match:
			date_str, initials, content = match.groups()
			try:
				# Parse YYYYMMDD format
				date_obj = datetime.strptime(date_str, '%Y%m%d')
				formatted_date = date_obj.strftime('%Y-%m-%d')
			except ValueError:
				# If date parsing fails, keep original
				formatted_date = date_str

			parsed_notes.append({
				'date': formatted_date,
				'initials': initials.lower(),
				'content': content
			})
		else:
			unparsed_lines.append(line)

	# If we couldn't parse any notes, just return the raw text (escaped with links)
	if not parsed_notes and unparsed_lines:
		linkified_text = _escape_and_linkify(notes_text)
		return Markup(f'<pre class="legacy-notes-raw">{linkified_text}</pre>')

	# Build HTML output
	html_parts = []

	if parsed_notes:
		html_parts.append('<table class="legacy-notes-table">')
		html_parts.append('<thead><tr><th>Date</th><th>By</th><th>Note</th></tr></thead>')
		html_parts.append('<tbody>')
		for note in parsed_notes:
			# Escape content and convert URLs to links
			linkified_content = _escape_and_linkify(note['content'])
			html_parts.append(
				f'<tr>'
				f'<td class="note-date">{note["date"]}</td>'
				f'<td class="note-initials">{note["initials"]}</td>'
				f'<td class="note-content">{linkified_content}</td>'
				f'</tr>'
			)
		html_parts.append('</tbody>')
		html_parts.append('</table>')

	# Include any unparsed lines at the end (escaped with links)
	if unparsed_lines:
		linkified_unparsed = '\n'.join(
			_escape_and_linkify(line) for line in unparsed_lines
		)
		html_parts.append('<div class="legacy-notes-unparsed">')
		html_parts.append('<strong>Other notes:</strong>')
		html_parts.append('<pre>')
		html_parts.append(linkified_unparsed)
		html_parts.append('</pre>')
		html_parts.append('</div>')

	return Markup(''.join(html_parts))
