"""
In-app per-IP abuse detector and blocker.

Counts unhandled-exception events per source IP over a sliding window. When a
threshold is crossed, inserts a row into `ip_block`. A small in-process cache
short-circuits subsequent requests from blocked IPs without a DB query.

Designed for cPanel/Phusion Passenger: no shared memory, no Redis, no Nginx
controls — all coordination happens through MySQL so the policy is global
across worker processes.

Disabled by default. Enable with config flag ABUSE_BLOCKER_ENABLED=True
(or env var of the same name; see _app_setup_utils config loading).
"""

import logging
import random
import threading
import time

from flask import request
from sqlalchemy import text
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class AbuseBlocker:
	"""Per-IP rate limiter backed by MySQL with an in-process blocklist cache."""

	def __init__(self):
		self._enabled = False
		self._window_minutes = 10
		self._threshold = 10
		self._block_minutes = 60
		self._cache_refresh_seconds = 60
		self._trust_xff = False
		self._cache = {}              # ip -> blocked_until (unix ts, float)
		self._cache_loaded_at = 0.0
		self._cache_lock = threading.Lock()
		self._engine = None

	def configure(self, app):
		cfg = app.config
		self._enabled = bool(cfg.get('ABUSE_BLOCKER_ENABLED', False))
		if not self._enabled:
			return
		self._window_minutes = int(cfg.get('ABUSE_DETECT_WINDOW_MINUTES', 10))
		self._threshold = int(cfg.get('ABUSE_DETECT_THRESHOLD', 10))
		self._block_minutes = int(cfg.get('ABUSE_BLOCK_DURATION_MINUTES', 60))
		self._cache_refresh_seconds = int(cfg.get('ABUSE_CACHE_REFRESH_SECONDS', 60))
		self._trust_xff = bool(cfg.get('TRUST_X_FORWARDED_FOR', False))

		from ascl_net_app.model.database import Database
		self._engine = Database().db.engine

		app.logger.info(
			"AbuseBlocker enabled "
			f"(window={self._window_minutes}m, threshold={self._threshold}, "
			f"block={self._block_minutes}m, trust_xff={self._trust_xff})"
		)

	@property
	def enabled(self):
		return self._enabled

	@property
	def block_minutes(self):
		return self._block_minutes

	def get_client_ip(self):
		if self._trust_xff:
			xff = request.headers.get('X-Forwarded-For')
			if xff:
				# First entry is the original client; the rest are proxies.
				return xff.split(',')[0].strip()
		return request.remote_addr

	def is_blocked(self, ip):
		if not self._enabled or not ip:
			return False
		now = time.time()
		with self._cache_lock:
			if now - self._cache_loaded_at > self._cache_refresh_seconds:
				self._refresh_cache_locked(now)
			blocked_until = self._cache.get(ip)
		return blocked_until is not None and blocked_until > now

	def record_error(self, ip):
		if not self._enabled or not ip:
			return
		try:
			with self._engine.begin() as conn:
				conn.execute(
					text("INSERT INTO ip_error_event (ip) VALUES (:ip)"),
					{"ip": ip},
				)
				count = conn.execute(
					text(
						"SELECT COUNT(*) FROM ip_error_event "
						"WHERE ip = :ip AND ts > NOW() - INTERVAL :w MINUTE"
					),
					{"ip": ip, "w": self._window_minutes},
				).scalar()
				if count and count >= self._threshold:
					reason = f"{count} errors in {self._window_minutes}m"
					conn.execute(
						text(
							"INSERT INTO ip_block (ip, blocked_until, reason) "
							"VALUES (:ip, NOW() + INTERVAL :m MINUTE, :r) "
							"ON DUPLICATE KEY UPDATE "
							"  blocked_until = GREATEST(blocked_until, VALUES(blocked_until)), "
							"  reason = VALUES(reason)"
						),
						{"ip": ip, "m": self._block_minutes, "r": reason},
					)
					logger.warning(f"AbuseBlocker: blocked {ip} ({reason})")
					# Force cache refresh on this worker's next request so we
					# don't keep serving the offender between refreshes.
					with self._cache_lock:
						self._cache_loaded_at = 0.0
			# Probabilistic cleanup keeps the table from growing unbounded
			# without needing a cron job.
			if random.random() < 0.01:
				self._cleanup()
		except Exception as e:
			logger.warning(f"AbuseBlocker.record_error failed: {e}")

	def unblock(self, ip):
		"""Remove an active block. Called from admin UI."""
		if not self._enabled:
			return
		try:
			with self._engine.begin() as conn:
				conn.execute(text("DELETE FROM ip_block WHERE ip = :ip"), {"ip": ip})
			with self._cache_lock:
				self._cache.pop(ip, None)
				self._cache_loaded_at = 0.0
		except Exception as e:
			logger.warning(f"AbuseBlocker.unblock failed: {e}")

	def list_active_blocks(self):
		if not self._enabled or self._engine is None:
			return []
		try:
			with self._engine.connect() as conn:
				rows = conn.execute(
					text(
						"SELECT ip, blocked_at, blocked_until, reason "
						"FROM ip_block WHERE blocked_until > NOW() "
						"ORDER BY blocked_until DESC"
					)
				).all()
			return [dict(r._mapping) for r in rows]
		except Exception as e:
			logger.warning(f"AbuseBlocker.list_active_blocks failed: {e}")
			return []

	def _refresh_cache_locked(self, now):
		try:
			with self._engine.connect() as conn:
				rows = conn.execute(
					text(
						"SELECT ip, UNIX_TIMESTAMP(blocked_until) AS until_ts "
						"FROM ip_block WHERE blocked_until > NOW()"
					)
				).all()
			self._cache = {r.ip: float(r.until_ts) for r in rows}
			self._cache_loaded_at = now
		except Exception as e:
			logger.warning(f"AbuseBlocker._refresh_cache failed: {e}")

	def _cleanup(self):
		try:
			with self._engine.begin() as conn:
				# Keep events covering the active window plus a buffer for
				# diagnostics. Drop blocks that expired long ago.
				conn.execute(
					text(
						"DELETE FROM ip_error_event "
						"WHERE ts < NOW() - INTERVAL :w MINUTE"
					),
					{"w": max(self._window_minutes * 3, 30)},
				)
				conn.execute(
					text(
						"DELETE FROM ip_block "
						"WHERE blocked_until < NOW() - INTERVAL 1 DAY"
					)
				)
		except Exception as e:
			logger.debug(f"AbuseBlocker._cleanup failed: {e}")


_instance = AbuseBlocker()


def get_blocker():
	return _instance


def install_hooks(app):
	"""Wire up before_request / teardown_request handlers if enabled."""
	blocker = get_blocker()
	blocker.configure(app)
	if not blocker.enabled:
		app.logger.info("AbuseBlocker disabled (set ABUSE_BLOCKER_ENABLED=True to enable)")
		return

	@app.before_request
	def _check_blocklist():
		ip = blocker.get_client_ip()
		if blocker.is_blocked(ip):
			retry_after = str(blocker.block_minutes * 60)
			return ('Too Many Requests\n', 429, {
				'Retry-After': retry_after,
				'Content-Type': 'text/plain; charset=utf-8',
			})

	@app.teardown_request
	def _record_unhandled(exc):
		# Only count exceptions Flask did not turn into a deliberate HTTP
		# response — i.e. the same kind Sentry captures.
		if exc is None or isinstance(exc, HTTPException):
			return
		try:
			ip = blocker.get_client_ip()
			if ip:
				blocker.record_error(ip)
		except Exception:
			# Never let our own bookkeeping crash a teardown.
			pass
