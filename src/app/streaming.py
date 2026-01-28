"""Streaming event processor for real-time test results."""
import json
from typing import Any
from sqlmodel import Session
from .models import Session as TestSession, TestReport, SessionStatus
from .formatter import format_longrepr
from .utils import (
    calculate_session_stats,
    get_current_utc_time,
    update_test_outcome,
    update_timestamp_bounds,
)


# In-memory cache for active sessions
# Maps session_id to dict of test outcomes for summary calculation
active_sessions: dict[int, dict[str, Any]] = {}


def process_event(event_line: str, session_id: int | None, db: Session) -> tuple[TestSession, str]:
    """Process a single JSONL event line.

    Args:
        event_line: Single JSONL line from pytest-reportlog
        session_id: Existing session ID or None to create new
        db: Database session

    Returns:
        Tuple of (session, event_type)
    """
    if not event_line.strip():
        raise ValueError("Empty event line")

    record = json.loads(event_line)
    report_type = record.get("$report_type")

    if report_type == "SessionStart":
        # Create new session or get existing
        if session_id:
            session = db.get(TestSession, session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
        else:
            session = TestSession(
                pytest_version=record.get("pytest_version"),
                status=SessionStatus.IN_PROGRESS.value
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            # Initialize tracking for this session
            active_sessions[session.id] = {
                "test_outcomes": {},
                "min_start": None,
                "max_stop": None,
            }

        return session, "session_start"

    elif report_type == "SessionFinish":
        if not session_id:
            raise ValueError("SessionFinish without session_id")

        session = db.get(TestSession, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.exitstatus = record.get("exitstatus")
        session.status = SessionStatus.COMPLETED.value
        session.updated_at = get_current_utc_time()

        # Clean up from active sessions
        if session.id in active_sessions:
            del active_sessions[session.id]

        db.add(session)
        db.commit()
        db.refresh(session)

        return session, "session_finish"

    elif report_type == "TestReport":
        if not session_id:
            raise ValueError("TestReport without session_id")

        session = db.get(TestSession, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        nodeid = record.get("nodeid", "")
        when = record.get("when", "")
        outcome = record.get("outcome", "")
        keywords = record.get("keywords", {})

        # Format longrepr
        longrepr_raw = record.get("longrepr")
        longrepr_formatted = format_longrepr(longrepr_raw)

        # Get timestamps
        start_time = record.get("start")
        stop_time = record.get("stop")

        # Create test report
        test_report = TestReport(
            session=session,
            nodeid=nodeid,
            location=record.get("location", []),
            keywords=keywords,
            when=when,
            outcome=outcome,
            duration=record.get("duration", 0.0),
            start=start_time,
            stop=stop_time,
            longrepr=longrepr_formatted,
            sections=record.get("sections", []),
            wasxfail=record.get("wasxfail"),
        )

        db.add(test_report)

        # Initialize session tracking if not exists
        if session.id not in active_sessions:
            active_sessions[session.id] = {
                "test_outcomes": {},
                "min_start": None,
                "max_stop": None,
            }

        session_data = active_sessions[session.id]

        # Update min/max timestamps for session duration
        session_data["min_start"], session_data["max_stop"] = update_timestamp_bounds(
            session_data["min_start"], session_data["max_stop"], start_time, stop_time
        )

        # Track outcomes by test for summary statistics
        update_test_outcome(
            session_data["test_outcomes"], nodeid, when, outcome, keywords, record
        )

        # Recalculate summary statistics and duration
        _update_session_stats(
            session,
            session_data["test_outcomes"],
            session_data["min_start"],
            session_data["max_stop"]
        )
        session.updated_at = get_current_utc_time()

        db.add(session)
        db.commit()
        db.refresh(session)

        return session, f"test_report_{when}"

    elif report_type == "CollectReport":
        # Collection reports can be ignored - just return the current session
        if not session_id:
            # If we don't have a session yet, we'll need to create a placeholder
            # or wait for SessionStart. For now, raise an error.
            raise ValueError("CollectReport without session_id")

        session = db.get(TestSession, session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        return session, "collect_report"

    else:
        raise ValueError(f"Unknown report type: {report_type}")


def _update_session_stats(
    session: TestSession,
    test_outcomes: dict[str, Any],
    min_start: float | None = None,
    max_stop: float | None = None
):
    """Update session summary statistics based on test outcomes and calculate duration."""
    # Use shared calculation utility
    stats = calculate_session_stats(test_outcomes)
    session.total_tests = stats["total_tests"]
    session.passed = stats["passed"]
    session.failed = stats["failed"]
    session.skipped = stats["skipped"]
    session.xfailed = stats["xfailed"]
    session.xpassed = stats["xpassed"]
    session.errors = stats["errors"]

    # Calculate overall session duration from timestamps
    if min_start is not None and max_stop is not None:
        session.duration = max_stop - min_start
