"""
Wayback Machine API — check and trigger archive.org captures.

POST /api/wayback/<ascl_id>  — submit URL to Save Page Now
GET  /api/wayback/<ascl_id>  — check last capture date
"""

import json
import logging
import urllib.request
from datetime import datetime, timezone

from flask import Blueprint, jsonify, current_app

from ..model.database import Database
from ..model.tables import CodeArchive

wayback_api = Blueprint('wayback_api', __name__)
logger = logging.getLogger(__name__)

WAYBACK_AVAILABLE_URL = 'https://archive.org/wayback/available'
WAYBACK_SAVE_URL = 'https://web.archive.org/save'


@wayback_api.route('/wayback/<ascl_id>', methods=['GET'])
def check_wayback(ascl_id):
    """Check the most recent Wayback Machine capture for a code's URL."""
    db = Database()
    session = db.session()

    code = session.query(CodeArchive).filter(CodeArchive.ascl_id == ascl_id).first()
    if not code:
        return jsonify({'error': 'not found'}), 404

    if not code.source_url:
        return jsonify({'error': 'no source URL for this code'}), 400

    # Query Wayback Availability API
    try:
        api_url = f'{WAYBACK_AVAILABLE_URL}?url={code.source_url}'
        req = urllib.request.Request(api_url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        logger.error(f"Wayback API error for {ascl_id}: {e}")
        return jsonify({'error': f'wayback API error: {str(e)}'}), 502

    snapshot = data.get('archived_snapshots', {}).get('closest')

    if snapshot:
        # Update the database with latest wayback info
        timestamp_str = snapshot.get('timestamp', '')
        if timestamp_str:
            try:
                wb_date = datetime.strptime(timestamp_str, '%Y%m%d%H%M%S')
                wb_date = wb_date.replace(tzinfo=timezone.utc)
                code.last_wayback = wb_date
            except ValueError:
                pass
        code.wayback_url = snapshot.get('url')
        session.commit()

    return jsonify({
        'ascl_id': ascl_id,
        'source_url': code.source_url,
        'snapshot': snapshot,
        'last_wayback': code.last_wayback.isoformat() if code.last_wayback else None,
        'wayback_url': code.wayback_url,
    })


@wayback_api.route('/wayback/<ascl_id>', methods=['POST'])
def save_wayback(ascl_id):
    """Submit a code's URL to the Wayback Machine Save Page Now API.

    Requires archive.org S3 API keys in app config:
        WAYBACK_ACCESS_KEY and WAYBACK_SECRET_KEY
    """
    db = Database()
    session = db.session()

    code = session.query(CodeArchive).filter(CodeArchive.ascl_id == ascl_id).first()
    if not code:
        return jsonify({'error': 'not found'}), 404

    if not code.source_url:
        return jsonify({'error': 'no source URL for this code'}), 400

    access_key = current_app.config.get('WAYBACK_ACCESS_KEY')
    secret_key = current_app.config.get('WAYBACK_SECRET_KEY')

    if not access_key or not secret_key:
        return jsonify({'error': 'archive.org API keys not configured'}), 500

    try:
        data = f'url={code.source_url}'.encode('utf-8')
        req = urllib.request.Request(WAYBACK_SAVE_URL, data=data, method='POST')
        req.add_header('Authorization', f'LOW {access_key}:{secret_key}')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        logger.error(f"Wayback save error for {ascl_id}: {e}")
        return jsonify({'error': f'wayback save error: {str(e)}'}), 502

    return jsonify({
        'ascl_id': ascl_id,
        'source_url': code.source_url,
        'save_result': result,
    })
