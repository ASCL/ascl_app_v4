#!/usr/bin/python

"""
Public form for suggesting corrections/updates to existing code entries.

Replaces the old phpBB-based correction system. Submissions go into the
code_correction / code_correction_link tables for admin review.
"""

import re
from urllib.parse import urlparse

import flask
import requests
from flask import render_template, request, abort
from sqlalchemy import text

suggest_edit_page = flask.Blueprint("suggest_edit_page", __name__)

CHALLENGE_ANSWER = "physicsisphun"


def _get_session():
    from ascl_net_app.model.database import Database
    return Database().Session()


def _fetch_code(db_session, ascl_id):
    """Fetch a published code row by ascl_id. Returns a mapping or None."""
    return db_session.execute(text("""
        SELECT pk, ascl_id, title, credit, abstract, citation_method
        FROM codes
        WHERE ascl_id = :ascl_id AND published = 1
        LIMIT 1
    """), {"ascl_id": ascl_id}).mappings().first()


def _fetch_link_types(db_session):
    """Return all link types ordered by pk."""
    return db_session.execute(text(
        "SELECT pk, short_name, name FROM link_type ORDER BY pk"
    )).mappings().all()


def _fetch_current_links(db_session, code_pk):
    """Return dict mapping link_type_pk to list of URLs for a code."""
    rows = db_session.execute(text("""
        SELECT l.url, l.link_type_pk
        FROM link l
        WHERE l.code_pk = :code_pk
        ORDER BY l.link_type_pk, l.display_order, l.pk
    """), {"code_pk": code_pk}).mappings().all()

    result = {}
    for row in rows:
        result.setdefault(row["link_type_pk"], []).append(row["url"])
    return result


def _normalize_urls(text_block):
    """Split textarea content into sorted, deduplicated, stripped URL list."""
    if not text_block:
        return []
    return [u for u in (line.strip() for line in text_block.strip().splitlines()) if u]


def _normalize_url(url):
    """Ensure a URL has a scheme. Tries https first, falls back to http."""
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https", "ftp"):
        return url

    # No scheme — try https first
    https_url = f"https://{url}"
    try:
        resp = requests.head(https_url, timeout=5, allow_redirects=True)
        if resp.status_code < 400:
            return https_url
    except requests.RequestException:
        pass

    # Fall back to http
    http_url = f"http://{url}"
    try:
        resp = requests.head(http_url, timeout=5, allow_redirects=True)
        if resp.status_code < 400:
            return http_url
    except requests.RequestException:
        pass

    # Neither worked — default to https
    return https_url


@suggest_edit_page.route("/<ascl_id>/suggest-edit", methods=["GET", "POST"])
def suggest_edit(ascl_id):
    if not re.match(r"^\d{4}\.\d{3}$", ascl_id):
        abort(404)

    db_session = _get_session()
    code = _fetch_code(db_session, ascl_id)
    if not code:
        abort(404)

    link_types = _fetch_link_types(db_session)
    current_links = _fetch_current_links(db_session, code["pk"])

    # Build link_types list with current URLs for template
    link_type_data = []
    for lt in link_types:
        urls = current_links.get(lt["pk"], [])
        link_type_data.append({
            "pk": lt["pk"],
            "short_name": lt["short_name"],
            "name": lt["name"],
            "current_urls": urls if urls else [""],
        })

    # Split credit into individual author names for the template
    credit_str = code["credit"] or ""
    credit_names = [n.strip() for n in credit_str.split(";") if n.strip()]
    if not credit_names:
        credit_names = [""]  # at least one empty field

    template_ctx = {
        "page_title": f"Suggest Edit — {code['title']}",
        "code": code,
        "link_types": link_type_data,
        "credit_names": credit_names,
        "err": None,
        "msg": None,
        "hide_form": False,
        "form_data": {},
    }

    if request.method == "POST":
        # Collect individual credit fields and join with "; "
        raw_credits = request.form.getlist("credit")
        submitted_names = [n.strip() for n in raw_credits if n.strip()]
        credit_joined = "; ".join(submitted_names)

        # Update credit_names for re-rendering on error
        template_ctx["credit_names"] = submitted_names if submitted_names else [""]

        form_data = {
            "title": request.form.get("title", "").strip(),
            "credit": credit_joined,
            "abstract": request.form.get("abstract", "").strip(),
            "citation_method": request.form.get("citation_method", "").strip(),
            "email": request.form.get("email", "").strip(),
            "name": request.form.get("name", "").strip(),
            "notes": request.form.get("notes", "").strip(),
            "challenge": request.form.get("challenge", "").strip(),
        }
        # Collect link fields (multiple inputs per link type)
        link_submissions = {}
        url_normalizations = []
        for lt in link_type_data:
            field_name = f"links_{lt['pk']}"
            raw_urls = request.form.getlist(field_name)
            cleaned = []
            for u in raw_urls:
                u = u.strip()
                if not u:
                    continue
                normalized = _normalize_url(u)
                if normalized != u:
                    url_normalizations.append(f"{u} → {normalized}")
                cleaned.append(normalized)
            link_submissions[lt["pk"]] = cleaned
            # Update current_urls for re-rendering on error
            lt["current_urls"] = cleaned if cleaned else [""]

        # Include link submissions in form_data for change detection
        for lt in link_type_data:
            form_data[f"links_{lt['pk']}"] = "\n".join(link_submissions.get(lt["pk"], []))

        template_ctx["form_data"] = form_data

        # Validation
        errors = []
        if not form_data["name"]:
            errors.append("Your name is required.")
        if not form_data["email"]:
            errors.append("Email address is required.")
        elif "@" not in form_data["email"]:
            errors.append("Please enter a valid email address.")

        challenge_response = form_data["challenge"].lower().replace(" ", "")
        if not form_data["challenge"]:
            errors.append("Bot challenge response is required.")
        elif challenge_response != CHALLENGE_ANSWER:
            errors.append("Bot challenge response was incorrect.")

        if errors:
            template_ctx["err"] = "<p>" + "</p><p>".join(errors) + "</p>"
        else:
            # Determine which scalar fields changed
            scalar_changes = {}
            for field in ("title", "credit", "abstract", "citation_method"):
                current_val = (code[field] or "").strip()
                proposed_val = form_data[field]
                if proposed_val and proposed_val != current_val:
                    scalar_changes[field] = proposed_val

            # Determine which link types changed
            link_changes = {}
            original_links = _fetch_current_links(db_session, code["pk"])
            for lt in link_type_data:
                original_urls = original_links.get(lt["pk"], [])
                proposed_urls = link_submissions.get(lt["pk"], [])
                if proposed_urls != original_urls:
                    link_changes[lt["pk"]] = "\n".join(proposed_urls)

            if not scalar_changes and not link_changes:
                template_ctx["err"] = "<p>No changes detected. Please modify at least one field.</p>"
            else:
                # Insert correction record
                db_session.execute(text("""
                    INSERT INTO code_correction
                        (code_pk, title, credit, abstract, citation_method,
                         submitter_email, submitter_name, submitter_notes)
                    VALUES
                        (:code_pk, :title, :credit, :abstract, :citation_method,
                         :email, :name, :notes)
                """), {
                    "code_pk": code["pk"],
                    "title": scalar_changes.get("title"),
                    "credit": scalar_changes.get("credit"),
                    "abstract": scalar_changes.get("abstract"),
                    "citation_method": scalar_changes.get("citation_method"),
                    "email": form_data["email"],
                    "name": form_data["name"] or None,
                    "notes": form_data["notes"] or None,
                })

                # Get the inserted correction pk
                correction_pk = db_session.execute(
                    text("SELECT LAST_INSERT_ID()")
                ).scalar()

                # Insert link changes
                for link_type_pk, urls_text in link_changes.items():
                    db_session.execute(text("""
                        INSERT INTO code_correction_link
                            (correction_pk, link_type_pk, urls)
                        VALUES
                            (:correction_pk, :link_type_pk, :urls)
                    """), {
                        "correction_pk": correction_pk,
                        "link_type_pk": link_type_pk,
                        "urls": urls_text,
                    })

                # If any URLs were auto-normalized, add a bot curator note
                if url_normalizations:
                    bot_pk = db_session.execute(
                        text("SELECT pk FROM users WHERE username = 'ASCLbot' LIMIT 1")
                    ).scalar()
                    norm_lines = "; ".join(url_normalizations)
                    db_session.execute(text("""
                        INSERT INTO code_note
                            (code_pk, correction_pk, user_pk, note_type_pk, note)
                        VALUES
                            (:code_pk, :correction_pk, :bot_pk, 3, :note)
                    """), {
                        "code_pk": code["pk"],
                        "correction_pk": correction_pk,
                        "bot_pk": bot_pk,
                        "note": f"Auto-normalized URLs: {norm_lines}",
                    })

                db_session.commit()

                template_ctx["msg"] = (
                    "<p>Thank you! Your suggested changes have been submitted "
                    "for editor review.</p>"
                )
                template_ctx["hide_form"] = True

    return render_template("suggest_edit.html", **template_ctx)
