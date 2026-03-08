"""
Central WordPress content processing utilities.

Handles shortcode expansion, paragraph formatting (wpautop),
and comment read/write for any WordPress content rendered by
the Flask app.
"""

import re

from markupsafe import Markup
from sqlalchemy import text

from ascl_net_app.model.database import Database

# WordPress table names
_WP_COMMENTS_TABLE = "ascl_wordpress.0hjpDo4yM_comments"

# ---------------------------------------------------------------------------
# Shortcodes
# ---------------------------------------------------------------------------

# [caption] — closed and unclosed forms
_CAPTION_CLOSED_RE = re.compile(
	r'\[caption[^\]]*\](.*?)\[/caption\]',
	re.DOTALL,
)
_CAPTION_UNCLOSED_RE = re.compile(
	r'\[caption[^\]]*\](.*?)(?=\n\n|\Z)',
	re.DOTALL,
)

# [video] — self-closing or with empty closing tag
# Ref: https://developer.wordpress.org/reference/functions/wp_video_shortcode/
_VIDEO_RE = re.compile(
	r'\[video\s+([^\]]*)\]\s*(?:\[/video\])?',
	re.DOTALL,
)
# Supported source format attributes (checked in order of preference)
_VIDEO_FORMATS = ['mp4', 'webm', 'ogg', 'flv']


def _process_caption(match):
	tag = match.group(0)
	inner = match.group(1).strip()

	# Extract shortcode attributes: id, class, align, width
	id_match = re.search(r'id="([^"]*)"', tag)
	class_match = re.search(r'class="([^"]*)"', tag)
	align_match = re.search(r'align="align(\w+)"', tag)
	width_match = re.search(r'width="(\d+)"', tag)

	classes = ["wp-caption"]
	if align_match:
		classes.append(f"align{align_match.group(1)}")
	if class_match:
		classes.append(class_match.group(1))

	styles = []
	if width_match:
		styles.append(f"max-width:{width_match.group(1)}px")

	id_attr = f' id="{id_match.group(1)}"' if id_match else ''
	class_attr = f' class="{" ".join(classes)}"'
	style_attr = f' style="{";".join(styles)}"' if styles else ''

	# Split: everything up to and including the closing </a> or <img.../> is the image;
	# any trailing text is the caption.
	img_match = re.match(r'(.*?(?:</a>|/>))\s*(.*)', inner, re.DOTALL)
	if img_match:
		img_html = img_match.group(1)
		caption_text = img_match.group(2).strip()
		figcaption = f'\n<figcaption>{caption_text}</figcaption>' if caption_text else ''
		return f'<figure{id_attr}{class_attr}{style_attr}>{img_html}{figcaption}</figure>'
	return f'<figure{id_attr}{class_attr}{style_attr}>{inner}</figure>'


def _process_video(match):
	attrs_str = match.group(1)

	# Parse shortcode attributes
	attrs = dict(re.findall(r'(\w+)="([^"]*)"', attrs_str))

	# Determine video source: explicit format attrs take priority, then 'src'
	sources = []
	mime_map = {'mp4': 'video/mp4', 'webm': 'video/webm', 'ogg': 'video/ogg', 'flv': 'video/x-flv'}
	for fmt in _VIDEO_FORMATS:
		if fmt in attrs:
			sources.append((attrs[fmt], mime_map[fmt]))
	if not sources and 'src' in attrs:
		# Guess MIME type from extension
		src = attrs['src']
		ext = src.rsplit('.', 1)[-1].lower() if '.' in src else ''
		mime = mime_map.get(ext, 'video/mp4')
		sources.append((src, mime))

	if not sources:
		return ''  # No video source found — WordPress returns void

	width = attrs.get('width', '640')
	height = attrs.get('height', '360')
	poster = attrs.get('poster', '')
	preload = attrs.get('preload', 'metadata')
	css_class = attrs.get('class', 'wp-video-shortcode')

	# Build <video> tag
	video_attrs = f'class="{css_class}" width="{width}" height="{height}" preload="{preload}" controls="controls"'
	if poster:
		video_attrs += f' poster="{poster}"'
	if attrs.get('autoplay'):
		video_attrs += ' autoplay="autoplay"'
	if attrs.get('loop'):
		video_attrs += ' loop="loop"'
	if attrs.get('muted', '').lower() in ('true', 'on', '1', 'muted'):
		video_attrs += ' muted="muted"'

	source_tags = '\n'.join(f'<source type="{mime}" src="{url}" />' for url, mime in sources)
	return f'<div style="width:{width}px;" class="wp-video">\n<video {video_attrs}>\n{source_tags}\n</video>\n</div>'


def process_shortcodes(content: str) -> str:
	"""Expand WordPress shortcodes in *content* to HTML."""
	if not content:
		return content
	# [caption] — closed form first, then unclosed
	content = _CAPTION_CLOSED_RE.sub(_process_caption, content)
	content = _CAPTION_UNCLOSED_RE.sub(_process_caption, content)
	# [video]
	content = _VIDEO_RE.sub(_process_video, content)
	return content


# ---------------------------------------------------------------------------
# wpautop — WordPress paragraph formatting
# ---------------------------------------------------------------------------

_ALLBLOCKS = (
	'table|thead|tfoot|caption|col|colgroup|tbody|tr|td|th|div|dl|dd|dt'
	'|ul|ol|li|pre|form|map|area|blockquote|address|style|p|h[1-6]|hr'
	'|fieldset|legend|section|article|aside|hgroup|header|footer|nav'
	'|figure|figcaption|details|menu|summary'
)

# Matches any HTML tag (opening, closing, self-closing, comments).
# Used by _replace_in_html_tags to protect newlines inside tags.
_HTML_TAG_RE = re.compile(
	r'<(?:[^<>]|(?:<!--.*?-->))*>',
	re.DOTALL,
)


def _replace_in_html_tags(text, replacements):
	"""Replace characters inside HTML tags only (equivalent to wp_replace_in_html_tags).

	This prevents newlines inside tag attributes from being treated as
	paragraph or line breaks.
	"""
	def _replace_tag(match):
		s = match.group(0)
		for old, new in replacements.items():
			s = s.replace(old, new)
		return s
	return _HTML_TAG_RE.sub(_replace_tag, text)


def wpautop(content: str, br=True) -> str:
	"""Port of WordPress wpautop() from wp-includes/formatting.php.

	Converts double newlines to <p> blocks and (optionally) single
	newlines to <br />.  Block-level HTML is preserved.  Shortcodes
	are expanded first.
	"""
	if not content or not content.strip():
		return ""

	content = process_shortcodes(content)

	# Pad the end to simplify regexes.
	text = content + "\n"

	# --- Protect <pre> tags with placeholders ---
	pre_tags = {}
	if '<pre' in text:
		parts = text.split('</pre>')
		last = parts.pop()
		text = ''
		for i, part in enumerate(parts):
			start = part.find('<pre')
			if start == -1:
				text += part
				continue
			name = f"<pre wp-pre-tag-{i}></pre>"
			pre_tags[name] = part[start:] + '</pre>'
			text += part[:start] + name
		text += last

	# Multiple <br> → paragraph break.
	text = re.sub(r'<br\s*/?>\s*<br\s*/?>', "\n\n", text)

	# Add double newline before block-level opening tags.
	text = re.sub(rf'(<(?:{_ALLBLOCKS})[\s/>])', r'\n\n\1', text, flags=re.I)

	# Add double newline after block-level closing tags.
	text = re.sub(rf'(</(?:{_ALLBLOCKS})>)', r'\1\n\n', text, flags=re.I)

	# Add double newline after <hr> (self-closing).
	text = re.sub(r'(<hr\s*/?>)', r'\1\n\n', text, flags=re.I)

	# Standardize newlines.
	text = text.replace("\r\n", "\n").replace("\r", "\n")

	# Protect newlines inside HTML tags (attributes, etc.).
	text = _replace_in_html_tags(text, {"\n": " <!-- wpnl --> "})

	# Collapse whitespace around <figcaption>.
	if '<figcaption' in text:
		text = re.sub(r'\s*(<figcaption[^>]*>)', r'\1', text)
		text = re.sub(r'</figcaption>\s*', '</figcaption>', text)

	# Collapse whitespace around <audio>/<video>/<source>/<track>.
	if '<source' in text or '<track' in text:
		text = re.sub(r'([<\[](?:audio|video)[^>\]]*[>\]])\s*', r'\1', text)
		text = re.sub(r'\s*([<\[]/(?:audio|video)[>\]])', r'\1', text)
		text = re.sub(r'\s*(<(?:source|track)[^>]*>)\s*', r'\1', text)

	# Collapse to at most two consecutive newlines.
	text = re.sub(r'\n\n+', "\n\n", text)

	# Split into paragraphs and wrap each in <p>.
	paragraphs = re.split(r'\n\s*\n', text)
	text = ''
	for p in paragraphs:
		p = p.strip("\n")
		if p:
			text += f'<p>{p}</p>\n'

	# Remove empty <p> blocks.
	text = re.sub(r'<p>\s*</p>', '', text)

	# Add closing <p> inside <div>, <address>, or <form> if missing.
	text = re.sub(r'<p>([^<]+)</(div|address|form)>', r'<p>\1</p></\2>', text)

	# Unwrap <p> from around block-level tags.
	text = re.sub(rf'<p>\s*(</?(?:{_ALLBLOCKS})[^>]*>)\s*</p>', r'\1', text, flags=re.I)

	# Fix <li> wrapped in <p>.
	text = re.sub(r'<p>(<li.+?)</p>', r'\1', text)

	# Fix <blockquote> wrapped in <p>.
	text = re.sub(r'<p><blockquote([^>]*)>', r'<blockquote\1><p>', text, flags=re.I)
	text = text.replace('</blockquote></p>', '</p></blockquote>')

	# Remove opening <p> before block tags.
	text = re.sub(rf'<p>\s*(</?(?:{_ALLBLOCKS})[^>]*>)', r'\1', text, flags=re.I)

	# Remove closing </p> after block tags.
	text = re.sub(rf'(</?(?:{_ALLBLOCKS})[^>]*>)\s*</p>', r'\1', text, flags=re.I)

	# Optionally insert <br />.
	if br:
		# Protect newlines inside <script>, <style>, <svg>, <math>.
		def _preserve_newlines(m):
			return m.group(0).replace("\n", "<WPPreserveNewline />")
		text = re.sub(r'<(script|style|svg|math).*?</\1>', _preserve_newlines, text, flags=re.S)

		# Normalize <br> variants.
		text = text.replace('<br>', '<br />').replace('<br/>', '<br />')

		# Add <br /> before newlines not already preceded by one.
		text = re.sub(r'(?<!<br />)\s*\n', "<br />\n", text)

		# Restore preserved newlines.
		text = text.replace('<WPPreserveNewline />', "\n")

	# Remove <br /> right after an opening or closing block tag.
	text = re.sub(rf'(</?(?:{_ALLBLOCKS})[^>]*>)\s*<br />', r'\1', text, flags=re.I)

	# Remove <br /> right before certain closing/opening block tags.
	text = re.sub(r'<br />(\s*</?(?:p|li|div|dl|dd|dt|th|pre|td|ul|ol)[^>]*>)', r'\1', text, flags=re.I)

	# Clean trailing newline before </p>.
	text = re.sub(r'\n</p>$', '</p>', text)

	# Restore <pre> tags.
	for placeholder, original in pre_tags.items():
		text = text.replace(placeholder, original)

	# Restore newlines inside HTML tags.
	if '<!-- wpnl -->' in text:
		text = text.replace(' <!-- wpnl --> ', "\n").replace('<!-- wpnl -->', "\n")

	return text


def strip_tags(text_value: str) -> str:
	"""Remove all HTML tags from *text_value*."""
	if not text_value:
		return ""
	return re.sub(r"<[^>]+>", "", text_value)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def fetch_comments(post_id):
	"""Fetch approved comments for a WordPress post, returning a threaded tree.

	Each node is a dict with keys: id, author, author_url, date, content, children.
	"""
	sql = text(
		f"""
		SELECT comment_ID, comment_author, comment_author_url, comment_date,
			comment_content, comment_parent
		FROM {_WP_COMMENTS_TABLE}
		WHERE comment_post_ID = :post_id AND comment_approved = '1' AND comment_type IN ('comment', '')
		ORDER BY comment_date ASC
		"""
	)
	with Database().db.engine.connect() as conn:
		rows = conn.execute(sql, {"post_id": post_id}).mappings().all()

	by_id = {}
	roots = []
	for row in rows:
		node = {
			"id": row["comment_ID"],
			"author": row["comment_author"] or "Anonymous",
			"author_url": row["comment_author_url"] or "",
			"date": row["comment_date"],
			"content": Markup(wpautop(row["comment_content"] or "")),
			"children": [],
		}
		by_id[node["id"]] = node
		parent_id = row["comment_parent"]
		if parent_id and parent_id in by_id:
			by_id[parent_id]["children"].append(node)
		else:
			roots.append(node)
	return roots


def insert_comment(post_id, author, email, url, content, ip="", user_agent=""):
	"""Insert a new comment into the WordPress comments table.

	The comment is inserted as approved (comment_approved='1').
	"""
	sql = text(
		f"""
		INSERT INTO {_WP_COMMENTS_TABLE}
			(comment_post_ID, comment_author, comment_author_email, comment_author_url,
			 comment_author_IP, comment_date, comment_date_gmt, comment_content,
			 comment_karma, comment_approved, comment_agent, comment_type, comment_parent, user_id)
		VALUES
			(:post_id, :author, :email, :url,
			 :ip, NOW(), UTC_TIMESTAMP(), :content,
			 0, '1', :agent, 'comment', 0, 0)
		"""
	)
	with Database().db.engine.connect() as conn:
		conn.execute(sql, {
			"post_id": post_id,
			"author": author[:200],
			"email": email[:100],
			"url": url[:200],
			"ip": ip,
			"content": content,
			"agent": user_agent[:255],
		})
		conn.commit()
