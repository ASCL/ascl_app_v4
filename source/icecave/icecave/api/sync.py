"""
Sync API — single-code sync and sync log queries.

Full syncs are handled by the icecave_sync CLI tool via cron, not the API.

POST /api/sync/<ascl_id>  — trigger sync for a single code
GET  /api/sync/status     — is a single-code sync running?
GET  /api/sync/log        — recent sync run summaries
GET  /api/sync/log/<pk>   — detail for a specific sync run
"""

import os
import subprocess
import threading
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, current_app

from ..model.database import Database
from ..model.tables import CodeArchive, SyncRun, SyncEvent

sync_api = Blueprint('sync_api', __name__)

_sync_lock = threading.Lock()
_sync_running = False


def _sync_single_code(app, ascl_id):
    """Sync one code in a background thread."""
    global _sync_running

    with app.app_context():
        db = Database()
        session = db.session()
        root = app.config['ARCHIVE_ROOT']
        timeout = app.config.get('SYNC_TIMEOUT_SECONDS', 600)

        try:
            code = session.query(CodeArchive).filter(CodeArchive.ascl_id == ascl_id).first()
            if not code:
                return

            run = SyncRun(
                started_at=datetime.now(timezone.utc),
                trigger='api',
                total_repos=1,
            )
            session.add(run)
            session.flush()

            repo_path = os.path.join(root, 'codes', code.dir_name)
            if os.path.islink(repo_path):
                repo_path = os.path.realpath(repo_path)

            now = datetime.now(timezone.utc)

            if not os.path.exists(repo_path):
                event = SyncEvent(
                    sync_run_pk=run.pk, code_archive_pk=code.pk,
                    result='error', error_message=f'directory missing: {code.dir_name}',
                )
                code.status = 'error'
                code.last_checked = now
                code.error_message = event.error_message
                session.add(event)
                run.errors = 1
            else:
                try:
                    result = subprocess.run(
                        ['git', 'remote', 'update'],
                        cwd=repo_path, capture_output=True, text=True, timeout=timeout,
                    )
                except subprocess.TimeoutExpired:
                    event = SyncEvent(
                        sync_run_pk=run.pk, code_archive_pk=code.pk,
                        result='error', error_message=f'timed out after {timeout}s',
                    )
                    code.status = 'error'
                    code.last_checked = now
                    code.error_message = event.error_message
                    session.add(event)
                    run.errors = 1
                else:
                    if result.returncode != 0:
                        error_msg = result.stderr.strip()[:500]
                        event = SyncEvent(
                            sync_run_pk=run.pk, code_archive_pk=code.pk,
                            result='error', error_message=error_msg,
                        )
                        code.status = 'error'
                        code.last_checked = now
                        code.error_message = error_msg
                        session.add(event)
                        run.errors = 1
                    else:
                        had_updates = '->' in result.stderr
                        if had_updates:
                            total_size = sum(
                                os.path.getsize(os.path.join(dp, f))
                                for dp, _, fns in os.walk(repo_path) for f in fns
                                if os.path.isfile(os.path.join(dp, f))
                            )
                            code.last_updated = now
                            code.size_bytes = total_size
                            run.updated = 1
                            event_result = 'updated'
                        else:
                            run.unchanged = 1
                            event_result = 'unchanged'

                        code.status = 'active'
                        code.last_checked = now
                        code.error_message = None
                        event = SyncEvent(
                            sync_run_pk=run.pk, code_archive_pk=code.pk,
                            result=event_result,
                        )
                        session.add(event)

            run.finished_at = datetime.now(timezone.utc)
            session.commit()

        finally:
            with _sync_lock:
                _sync_running = False


@sync_api.route('/sync/<ascl_id>', methods=['POST'])
def trigger_sync_single(ascl_id):
    """Trigger sync for a single code."""
    global _sync_running

    db = Database()
    session = db.session()
    code = session.query(CodeArchive).filter(CodeArchive.ascl_id == ascl_id).first()
    if not code:
        return jsonify({'error': 'not found'}), 404

    if code.archive_type != 'git':
        return jsonify({'error': f'cannot sync archive_type={code.archive_type}'}), 400

    with _sync_lock:
        if _sync_running:
            return jsonify({'error': 'a sync is already in progress'}), 409
        _sync_running = True

    app = current_app._get_current_object()
    thread = threading.Thread(target=_sync_single_code, args=(app, ascl_id))
    thread.daemon = True
    thread.start()

    return jsonify({'status': f'sync started for {ascl_id}'}), 202


@sync_api.route('/sync/status')
def sync_status():
    """Check if a sync is currently running."""
    return jsonify({'running': _sync_running})


@sync_api.route('/sync/log')
def sync_log():
    """Recent sync run summaries."""
    db = Database()
    session = db.session()

    limit = min(50, int(request.args.get('limit', 20)))
    runs = (
        session.query(SyncRun)
        .order_by(SyncRun.started_at.desc())
        .limit(limit)
        .all()
    )

    return jsonify({'runs': [r.to_dict() for r in runs]})


@sync_api.route('/sync/log/<int:pk>')
def sync_log_detail(pk):
    """Detail for a specific sync run, including per-code events."""
    db = Database()
    session = db.session()

    run = session.query(SyncRun).get(pk)
    if not run:
        return jsonify({'error': 'not found'}), 404

    events = (
        session.query(SyncEvent, CodeArchive.ascl_id, CodeArchive.code_title)
        .join(CodeArchive, SyncEvent.code_archive_pk == CodeArchive.pk)
        .filter(SyncEvent.sync_run_pk == pk)
        .order_by(SyncEvent.timestamp)
        .all()
    )

    result = run.to_dict()
    result['events'] = [
        {
            'ascl_id': ascl_id,
            'code_title': title,
            'timestamp': event.timestamp.isoformat(),
            'result': event.result,
            'error_message': event.error_message,
        }
        for event, ascl_id, title in events
    ]

    return jsonify(result)
