"""Database retention: bring the database back under a size cap.

Strategy (tiered, most-recent-preserving):
  1. Strip heavy logs (``longrepr`` + ``sections``) from the oldest eligible sessions
     first — this reclaims the bulk of the space while keeping each session's summary
     and per-test outcomes/durations intact for the History pages.
  2. If that is still not enough, delete whole sessions oldest-first.
Finally VACUUM so the freed pages are returned to the OS and the on-disk size actually
drops below the cap.

The newest ``keep_recent`` sessions and any in-progress session are never touched.
"""
import logging

from sqlalchemy import delete, func, update
from sqlmodel import Session, select

from ..database import get_database_size_bytes, vacuum
from ..models import Session as TestSession
from ..models import SessionStatus, TestReport
from ..utils import format_size

logger = logging.getLogger(__name__)

# Rough per-row / per-session overhead added to deletion estimates so that
# deleting fully-stripped sessions still counts toward getting under the cap.
_REPORT_OVERHEAD = 128
_SESSION_OVERHEAD = 256


def _strippable_bytes(db: Session, session_id: int) -> int:
    """Bytes reclaimable by stripping logs/tracebacks from one session."""
    return db.exec(
        select(
            func.coalesce(func.sum(func.length(TestReport.longrepr)), 0)
            + func.coalesce(func.sum(func.length(TestReport.sections)), 0)
        ).where(TestReport.session_id == session_id)
    ).one()


def _session_bytes(db: Session, session_id: int) -> int:
    """Estimated total bytes freed by deleting one session entirely."""
    report_count = db.exec(
        select(func.count())
        .select_from(TestReport)
        .where(TestReport.session_id == session_id)
    ).one()
    content = db.exec(
        select(
            func.coalesce(func.sum(func.length(TestReport.longrepr)), 0)
            + func.coalesce(func.sum(func.length(TestReport.sections)), 0)
            + func.coalesce(func.sum(func.length(TestReport.nodeid)), 0)
            + func.coalesce(func.sum(func.length(TestReport.location)), 0)
            + func.coalesce(func.sum(func.length(TestReport.keywords)), 0)
        ).where(TestReport.session_id == session_id)
    ).one()
    return content + report_count * _REPORT_OVERHEAD + _SESSION_OVERHEAD


def _eligible_sessions(db: Session, keep_recent: int) -> list[TestSession]:
    """Completed/interrupted sessions, oldest first, excluding the newest keep_recent."""
    protected_ids = set(
        db.exec(
            select(TestSession.id)
            .order_by(TestSession.created_at.desc())
            .limit(max(keep_recent, 0))
        ).all()
    )
    sessions = db.exec(
        select(TestSession)
        .where(TestSession.status != SessionStatus.IN_PROGRESS.value)
        .order_by(TestSession.created_at.asc())
    ).all()
    return [s for s in sessions if s.id not in protected_ids]


def prune_database(db: Session, max_bytes: int, keep_recent: int = 10) -> dict:
    """Prune the database to fit under ``max_bytes``. Returns a report dict."""
    before = get_database_size_bytes()
    if before is None:
        return _report(
            max_bytes, None, None, [], [],
            "Database size is unknown (not a file-backed database).",
        )
    if before <= max_bytes:
        return _report(max_bytes, before, before, [], [], "Already under the size cap.")

    eligible = _eligible_sessions(db, keep_recent)
    stripped: list[int] = []
    deleted: list[int] = []

    # Phase A — strip logs from the oldest eligible sessions.
    over = before - max_bytes
    for session in eligible:
        if over <= 0:
            break
        freed = _strippable_bytes(db, session.id)
        if freed <= 0:
            continue
        db.exec(
            update(TestReport)
            .where(TestReport.session_id == session.id)
            .values(longrepr=None, sections=[])
        )
        session.logs_pruned = True
        db.add(session)
        stripped.append(session.id)
        over -= freed
    db.commit()
    vacuum()

    # Phase B — if still over, delete whole sessions oldest-first.
    after_strip = get_database_size_bytes()
    if after_strip is not None and after_strip > max_bytes:
        over = after_strip - max_bytes
        for session in eligible:
            if over <= 0:
                break
            over -= _session_bytes(db, session.id)
            db.exec(delete(TestReport).where(TestReport.session_id == session.id))
            db.delete(session)
            deleted.append(session.id)
        db.commit()
        vacuum()

    after = get_database_size_bytes()
    message = None
    if after is not None and after > max_bytes:
        message = (
            "Could not reach the cap; the protected recent sessions exceed it. "
            "Lower keep_recent or raise the cap."
        )
    return _report(max_bytes, before, after, stripped, deleted, message)


def _report(
    cap: int,
    before: int | None,
    after: int | None,
    stripped: list[int],
    deleted: list[int],
    message: str | None,
) -> dict:
    freed = before - after if (before is not None and after is not None) else None
    return {
        "cap_bytes": cap,
        "cap_human": format_size(cap),
        "before_bytes": before,
        "before_human": format_size(before),
        "after_bytes": after,
        "after_human": format_size(after),
        "freed_bytes": freed,
        "freed_human": format_size(freed),
        "stripped": stripped,
        "stripped_count": len(stripped),
        "deleted": deleted,
        "deleted_count": len(deleted),
        "under_cap": (after <= cap) if after is not None else None,
        "message": message,
    }
