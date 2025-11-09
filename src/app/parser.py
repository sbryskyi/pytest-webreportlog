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
            test_report = TestReport(
                session=session,
                nodeid=nodeid,
                location=record.get("location", []),
                keywords=keywords,
                when=when,
                outcome=outcome,
                duration=record.get("duration", 0.0),
                start=record.get("start"),
                stop=record.get("stop"),
                longrepr=longrepr_formatted,
                sections=record.get("sections", []),
            )

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

        # Count based on call phase outcome and xfail marker
        if has_xfail_marker:
            # Tests with xfail marker
            if call_outcome == "skipped":
                # Expected to fail and did fail = xfailed
                xfailed += 1
            elif call_outcome == "passed":
                # Expected to fail but passed = xpassed
                xpassed += 1
        else:
            # Regular tests without xfail marker
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

    # Save session
    db.add(session)
    db.commit()
    db.refresh(session)

    return session
