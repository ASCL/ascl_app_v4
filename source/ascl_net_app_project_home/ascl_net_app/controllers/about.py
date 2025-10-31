#!/usr/bin/python

import flask
from flask import render_template

about_page = flask.Blueprint("about_page", __name__)

@about_page.route("/about", methods=['GET'])
def about():
	''' About page. '''
	return render_template("about.html")
