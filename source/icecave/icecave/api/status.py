"""
Status API — read-only endpoints for archive status.

GET /api/health          — uptime, disk usage, last sync
GET /api/status          — summary stats + paginated code list
GET /api/status/<ascl_id> — detail for one code
"""

import os
import shutil
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app
from sqlalchemy import func

from ..model.database import Database
from ..model.tables import CodeArchive, SyncRun, SyncEvent

status_api = Blueprint('status_api', __name__)


@status_api.route('/health')
def health():
    """Basic health check — unauthenticated."""
    root = current_app.config['ARCHIVE_ROOT']

    disk = shutil.disk_usage(root)

    db = Database()
    session = db.session()
    last_run = session.query(SyncRun).order_by(SyncRun.started_at.desc()).first()

    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'archive_root': root,
        'disk': {
            'total_gb': round(disk.total / 1e9, 1),
            'used_gb': round(disk.used / 1e9, 1),
            'free_gb': round(disk.free / 1e9, 1),
            'percent_used': round(disk.used / disk.total * 100, 1),
        },
        'last_sync': last_run.to_dict() if last_run else None,
    })


@status_api.route('/status')
def status_summary():
    """Summary stats and paginated code list.

    Query params:
        status   — filter by status (pending, active, stale, error, missing)
        type     — filter by archive_type (git, download, webonly)
        q        — search code title or ASCL ID
        page     — page number (default 1)
        per_page — results per page (default 50, max 500)
        sort     — sort field (ascl_id, last_updated, last_checked, size_bytes, status)
        order    — asc or desc (default asc)
    """
    db = Database()
    session = db.session()

    # Summary counts
    type_counts = dict(
        session.query(CodeArchive.archive_type, func.count())
        .group_by(CodeArchive.archive_type).all()
    )
    status_counts = dict(
        session.query(CodeArchive.status, func.count())
        .group_by(CodeArchive.status).all()
    )
    total_size = session.query(func.sum(CodeArchive.size_bytes)).scalar() or 0
    total_codes = session.query(func.count(CodeArchive.pk)).scalar()

    # Build filtered query
    query = session.query(CodeArchive)

    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter(CodeArchive.status == status_filter)

    type_filter = request.args.get('type')
    if type_filter:
        query = query.filter(CodeArchive.archive_type == type_filter)

    search = request.args.get('q')
    if search:
        pattern = f'%{search}%'
        query = query.filter(
            (CodeArchive.code_title.ilike(pattern)) |
            (CodeArchive.ascl_id.ilike(pattern)) |
            (CodeArchive.short_name.ilike(pattern))
        )

    # Sorting
    sort_field = request.args.get('sort', 'ascl_id')
    sort_order = request.args.get('order', 'asc')
    sort_column = getattr(CodeArchive, sort_field, CodeArchive.ascl_id)
    if sort_order == 'desc':
        sort_column = sort_column.desc()
    query = query.order_by(sort_column)

    # Pagination
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(10000, max(1, int(request.args.get('per_page', 50))))
    total_filtered = query.count()
    codes = query.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        'summary': {
            'total_codes': total_codes,
            'total_size_gb': round(total_size / 1e9, 2),
            'by_type': type_counts,
            'by_status': status_counts,
        },
        'codes': [c.to_dict() for c in codes],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_filtered,
            'pages': (total_filtered + per_page - 1) // per_page,
        },
    })


@status_api.route('/status/<ascl_id>')
def status_detail(ascl_id):
    """Detail for a single code, including recent sync history."""
    db = Database()
    session = db.session()

    code = session.query(CodeArchive).filter(CodeArchive.ascl_id == ascl_id).first()
    if not code:
        return jsonify({'error': 'not found'}), 404

    # Get recent sync events for this code
    events = (
        session.query(SyncEvent)
        .filter(SyncEvent.code_archive_pk == code.pk)
        .order_by(SyncEvent.timestamp.desc())
        .limit(20)
        .all()
    )

    # Check if directory exists on disk
    root = current_app.config['ARCHIVE_ROOT']
    dir_path = os.path.join(root, 'codes', code.dir_name)
    on_disk = os.path.exists(dir_path)
    is_symlink = os.path.islink(dir_path)
    symlink_target = os.readlink(dir_path) if is_symlink else None

    result = code.to_dict()
    result['on_disk'] = on_disk
    result['is_symlink'] = is_symlink
    result['symlink_target'] = symlink_target
    result['recent_events'] = [
        {
            'timestamp': e.timestamp.isoformat(),
            'result': e.result,
            'error_message': e.error_message,
        }
        for e in events
    ]

    return jsonify(result)
