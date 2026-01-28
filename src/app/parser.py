"""Parser for pytest-reportlog JSONL files."""
import json
from sqlmodel import Session
from .models import Session as TestSession, TestReport, SessionStatus
from .formatter import format_longrepr
from .utils import (
    calculate_session_stats,
    get_current_utc_time,
    update_test_outcome,
    update_timestamp_bounds,
)


def parse_jsonl_report(lines: list[str], db: Session) -> TestSession:
    """Parse JSONL lines and create session with test reports.

    Args:
        lines: List of JSONL lines from pytest-reportlog
        db: Database session

    Returns:
        Created TestSession object

    Raises:
        json.JSONDecodeError: If JSONL is malformed
        ValueError: If required fields are missing
    """
    # Create new session
    session = TestSession()

    # Track test outcomes by nodeid to avoid double-counting
    test_outcomes = {}

    # Track timing for overall session duration
    min_start = None
    max_stop = None

    for line in lines:
        if not line.strip():
            continue

        record = json.loads(line)
        report_type = record.get("$report_type")

        if report_type == "SessionStart":
            # Extract session metadata
            session.pytest_version = record.get("pytest_version")

        elif report_type == "SessionFinish":
            # Extract final status
            session.exitstatus = record.get("exitstatus")
            session.status = SessionStatus.COMPLETED.value
            session.updated_at = get_current_utc_time()

        elif report_type == "TestReport":
            nodeid = record.get("nodeid", "")
            when = record.get("when", "")
            outcome = record.get("outcome", "")
            keywords = record.get("keywords", {})

            # Format longrepr using our formatter
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

            # Track min/max timestamps for session duration
            min_start, max_stop = update_timestamp_bounds(
                min_start, max_stop, start_time, stop_time
            )

            # Track outcomes by test for summary statistics
            update_test_outcome(test_outcomes, nodeid, when, outcome, keywords, record)

            db.add(test_report)

    # Calculate summary statistics using shared utility
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

    # Save session
    db.add(session)
    db.commit()
    db.refresh(session)

    return session
