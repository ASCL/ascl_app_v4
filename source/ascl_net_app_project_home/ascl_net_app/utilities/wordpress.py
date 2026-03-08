"""
Central WordPress content processing utilities.

Handles shortcode expansion and paragraph formatting (wpautop)
for any WordPress content rendered by the Flask app.
"""

import re

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


def process_shortcodes(content: str) -> str:
	"""Expand WordPress shortcodes in *content* to HTML."""
	if not content:
		return content
	# Closed shortcodes first, then unclosed
	content = _CAPTION_CLOSED_RE.sub(_process_caption, content)
	content = _CAPTION_UNCLOSED_RE.sub(_process_caption, content)
	return content


# ---------------------------------------------------------------------------
# wpautop — WordPress paragraph formatting
# ---------------------------------------------------------------------------

_BLOCK_TAGS = re.compile(
	r"^<(?:p|div|ul|ol|li|blockquote|table|pre|h[1-6]|hr|figure|figcaption|details|summary)[\s>/]",
	re.IGNORECASE,
)


def wpautop(content: str) -> str:
	"""Mimic WordPress wpautop(): double newlines become <p> blocks,
	single newlines become <br /> within paragraphs.  Shortcodes are
	expanded before paragraph formatting."""
	if not content:
		return ""
	content = process_shortcodes(content)
	content = content.replace("\r\n", "\n").strip()
	parts = re.split(r"\n\s*\n", content)
	paragraphs = []
	for part in parts:
		part = part.strip()
		if not part:
			continue
		if _BLOCK_TAGS.match(part):
			part = re.sub(r"\n", "<br />\n", part)
			paragraphs.append(part)
		else:
			part = re.sub(r"\n", "<br />\n", part)
			paragraphs.append(f"<p>{part}</p>")
	return "\n".join(paragraphs)


def strip_tags(text_value: str) -> str:
	"""Remove all HTML tags from *text_value*."""
	if not text_value:
		return ""
	return re.sub(r"<[^>]+>", "", text_value)
