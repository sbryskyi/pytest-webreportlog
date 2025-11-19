"""Parser for pytest-reportlog JSONL files."""
import json
from datetime import datetime
from sqlmodel import Session
from .models import Session as TestSession, TestReport, SessionStatus
from .formatter import format_longrepr


def parse_jsonl_report(lines: list[str], db: Session) -> TestSession:
    """Parse JSONL lines and create session with test reports.

    Args:
        lines: List of JSONL lines from pytest-reportlog
        db: Database session

    Returns:
        Created TestSession object
    """
    # Create new session
    session = TestSession()

    # Track test outcomes by nodeid to avoid double-counting
    test_outcomes = {}  # nodeid -> {call_outcome, has_setup_error, has_teardown_error, has_xfail_marker}

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
            session.updated_at = datetime.utcnow()

        elif report_type == "TestReport":
            nodeid = record.get("nodeid", "")
            when = record.get("when", "")
            outcome = record.get("outcome", "")
            keywords = record.get("keywords", {})

            # Format longrepr using our formatter
            longrepr_raw = record.get("longrepr")
            longrepr_formatted = format_longrepr(longrepr_raw)

            # Create test report
            start_time = record.get("start")
            stop_time = record.get("stop")

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
                wasxfail=record.get("wasxfail"),  # For xfail(run=False) tests
            )

            # Track min/max timestamps for session duration
            if start_time is not None:
                if min_start is None or start_time < min_start:
                    min_start = start_time
            if stop_time is not None:
                if max_stop is None or stop_time > max_stop:
                    max_stop = stop_time

            # Track outcomes by test for summary statistics
            if nodeid not in test_outcomes:
                test_outcomes[nodeid] = {
                    "call_outcome": None,
                    "has_setup_error": False,
                    "has_teardown_error": False,
                    "has_xfail_marker": "xfail" in keywords,
                    "has_wasxfail": False,  # Track if test has wasxfail field (for xfail(run=False))
                    "setup_skipped": False,  # Track if test was skipped in setup phase
                }

            if when == "call":
                test_outcomes[nodeid]["call_outcome"] = outcome
            elif when == "setup":
                if outcome == "failed":
                    test_outcomes[nodeid]["has_setup_error"] = True
                elif outcome == "skipped":
                    test_outcomes[nodeid]["setup_skipped"] = True
                # Check for wasxfail in setup phase (for xfail(run=False) tests)
                if "wasxfail" in record:
                    test_outcomes[nodeid]["has_wasxfail"] = True
            elif when == "teardown" and outcome == "failed":
                test_outcomes[nodeid]["has_teardown_error"] = True

            db.add(test_report)

    # Calculate summary statistics
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
        has_wasxfail = test_data["has_wasxfail"]
        setup_skipped = test_data["setup_skipped"]

        # Count based on call phase outcome and xfail marker
        if has_xfail_marker:
            # Tests with xfail marker
            if call_outcome == "skipped":
                # Expected to fail and did fail = xfailed
                xfailed += 1
            elif call_outcome == "passed":
                # Expected to fail but passed = xpassed
                xpassed += 1
            elif call_outcome == "failed":
                # Strict xfail that passed (pytest reports as failed with [XPASS(strict)])
                failed += 1
            elif call_outcome is None and has_wasxfail:
                # xfail(run=False) - test was not run but marked as xfail
                xfailed += 1
        else:
            # Regular tests without xfail marker
            if call_outcome == "passed":
                passed += 1
            elif call_outcome == "failed":
                failed += 1
            elif call_outcome == "skipped":
                skipped += 1
            elif call_outcome is None and setup_skipped:
                # Test was skipped in setup phase (no call phase)
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

    # Save session
    db.add(session)
    db.commit()
    db.refresh(session)

    return session
