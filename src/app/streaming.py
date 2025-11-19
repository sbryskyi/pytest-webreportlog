"""Streaming event processor for real-time test results."""
import json
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Session, select
from .models import Session as TestSession, TestReport, SessionStatus
from .formatter import format_longrepr


# In-memory cache for active sessions
# Maps session_id to dict of test outcomes for summary calculation
active_sessions: Dict[int, Dict[str, Any]] = {}


def process_event(event_line: str, session_id: Optional[int], db: Session) -> tuple[TestSession, str]:
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
        session.updated_at = datetime.utcnow()

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
        test_outcomes = session_data["test_outcomes"]

        # Update min/max timestamps for session duration
        if start_time is not None:
            if session_data["min_start"] is None or start_time < session_data["min_start"]:
                session_data["min_start"] = start_time
        if stop_time is not None:
            if session_data["max_stop"] is None or stop_time > session_data["max_stop"]:
                session_data["max_stop"] = stop_time

        # Track outcomes by test for summary statistics
        if nodeid not in test_outcomes:
            test_outcomes[nodeid] = {
                "call_outcome": None,
                "has_setup_error": False,
                "has_teardown_error": False,
                "has_xfail_marker": "xfail" in keywords,
            }

        if when == "call":
            test_outcomes[nodeid]["call_outcome"] = outcome
        elif when == "setup" and outcome == "failed":
            test_outcomes[nodeid]["has_setup_error"] = True
        elif when == "teardown" and outcome == "failed":
            test_outcomes[nodeid]["has_teardown_error"] = True

        # Recalculate summary statistics and duration
        _update_session_stats(session, test_outcomes, session_data["min_start"], session_data["max_stop"])
        session.updated_at = datetime.utcnow()

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


def _update_session_stats(session: TestSession, test_outcomes: Dict[str, Any],
                          min_start: Optional[float] = None, max_stop: Optional[float] = None):
    """Update session summary statistics based on test outcomes and calculate duration."""
    passed = 0
    failed = 0
    skipped = 0
    xfailed = 0
    xpassed = 0
    errors = 0

    for test_data in test_outcomes.values():
        call_outcome = test_data["call_outcome"]
        has_setup_error = test_data["has_setup_error"]
        has_teardown_error = test_data["has_teardown_error"]
        has_xfail_marker = test_data["has_xfail_marker"]

        # Count based on call phase outcome and xfail marker
        if has_xfail_marker:
            if call_outcome == "skipped":
                xfailed += 1
            elif call_outcome == "passed":
                xpassed += 1
        else:
            if call_outcome == "passed":
                passed += 1
            elif call_outcome == "failed":
                failed += 1
            elif call_outcome == "skipped":
                skipped += 1

        # Count setup/teardown errors separately
        if has_setup_error:
            errors += 1
        if has_teardown_error:
            errors += 1

    session.total_tests = len(test_outcomes)
    session.passed = passed
    session.failed = failed
    session.skipped = skipped
    session.xfailed = xfailed
    session.xpassed = xpassed
    session.errors = errors

    # Calculate overall session duration from timestamps
    if min_start is not None and max_stop is not None:
        session.duration = max_stop - min_start
