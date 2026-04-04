"""
SQLAlchemy ORM models for the Icecave database.

These tables track the archival status of ASCL codes and sync history.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, BigInteger, Enum, ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CodeArchive(Base):
    """Tracks the archival status of each ASCL code."""

    __tablename__ = 'code_archive'

    pk = Column(Integer, primary_key=True, autoincrement=True)
    ascl_id = Column(String(8), nullable=False, unique=True, index=True)
    code_title = Column(String(255), nullable=False)
    short_name = Column(String(100), nullable=True)
    archive_type = Column(
        Enum('git', 'download', 'webonly', name='archive_type_enum'),
        nullable=False,
    )
    source_url = Column(String(500), nullable=False, default='')
    dir_name = Column(String(200), nullable=False)
    last_checked = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, nullable=True)
    last_wayback = Column(DateTime, nullable=True)
    wayback_url = Column(String(500), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    status = Column(
        Enum('pending', 'active', 'stale', 'error', 'missing', name='status_enum'),
        nullable=False,
        default='pending',
    )
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    sync_events = relationship('SyncEvent', back_populates='code_archive', order_by='SyncEvent.timestamp.desc()')

    def to_dict(self):
        return {
            'pk': self.pk,
            'ascl_id': self.ascl_id,
            'code_title': self.code_title,
            'short_name': self.short_name,
            'archive_type': self.archive_type,
            'source_url': self.source_url,
            'dir_name': self.dir_name,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None,
            'last_wayback': self.last_wayback.isoformat() if self.last_wayback else None,
            'wayback_url': self.wayback_url,
            'size_bytes': self.size_bytes,
            'status': self.status,
            'error_message': self.error_message,
        }


class SyncRun(Base):
    """Records each execution of the sync process."""

    __tablename__ = 'sync_run'

    pk = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    total_repos = Column(Integer, nullable=True)
    updated = Column(Integer, default=0)
    unchanged = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    trigger = Column(
        Enum('cron', 'manual', 'api', name='trigger_enum'),
        nullable=False,
        default='cron',
    )

    events = relationship('SyncEvent', back_populates='sync_run', order_by='SyncEvent.timestamp')

    def to_dict(self):
        return {
            'pk': self.pk,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'total_repos': self.total_repos,
            'updated': self.updated,
            'unchanged': self.unchanged,
            'errors': self.errors,
            'trigger': self.trigger,
        }


class SyncEvent(Base):
    """Individual sync result for one code in one run."""

    __tablename__ = 'sync_event'

    pk = Column(Integer, primary_key=True, autoincrement=True)
    sync_run_pk = Column(Integer, ForeignKey('sync_run.pk'), nullable=False)
    code_archive_pk = Column(Integer, ForeignKey('code_archive.pk'), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    result = Column(
        Enum('updated', 'unchanged', 'error', name='sync_result_enum'),
        nullable=False,
    )
    error_message = Column(Text, nullable=True)

    sync_run = relationship('SyncRun', back_populates='events')
    code_archive = relationship('CodeArchive', back_populates='sync_events')

    __table_args__ = (
        Index('ix_sync_event_run', 'sync_run_pk'),
        Index('ix_sync_event_code', 'code_archive_pk'),
    )
