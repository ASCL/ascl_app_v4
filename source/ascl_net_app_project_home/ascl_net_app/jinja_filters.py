#!/usr/bin/python

'''
This file contains all custom Jinja2 filters.

Following the template below, new filters can be added here
and will be automatically registered.
'''

import flask
import jinja2

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

