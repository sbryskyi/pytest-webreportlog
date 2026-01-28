"""Utility functions for test result processing."""
from typing import Any
from datetime import datetime, timezone


def determine_test_outcome(
    outcome: str | None,
    keywords: dict | None = None,
    has_wasxfail: bool = False
) -> tuple[str, str]:
    """Determine test result label and outcome category based on outcome and xfail status.

    Args:
        outcome: The test outcome (passed, failed, skipped, etc.)
        keywords: Test keywords dict (may contain 'xfail' marker)
        has_wasxfail: Whether test has wasxfail field (for xfail(run=False))

    Returns:
        Tuple of (result_label, outcome_category)
        - result_label: Display label (PASS, FAIL, SKIP, XFAIL, XPASS, ERROR, UNKNOWN)
        - outcome_category: Category for statistics (passed, failed, skipped, xfailed, xpassed, error, unknown)
    """
    if keywords is None:
        keywords = {}

    has_xfail = "xfail" in keywords

    if has_xfail:
        # Tests with xfail marker
        if outcome == "skipped":
            # Expected to fail and did fail
            return "XFAIL", "xfailed"
        elif outcome == "passed":
            # Expected to fail but passed
            return "XPASS", "xpassed"
        elif outcome == "failed":
            # Strict xfail that passed (pytest reports as failed with [XPASS(strict)])
            return "FAIL", "failed"
        elif outcome is None and has_wasxfail:
            # xfail(run=False) - test was not run but marked as xfail
            return "XFAIL", "xfailed"
        else:
            return outcome.upper() if outcome else "UNKNOWN", outcome or "unknown"
    else:
        # Regular tests without xfail marker
        if outcome == "passed":
            return "PASS", "passed"
        elif outcome == "failed":
            return "FAIL", "failed"
        elif outcome == "skipped":
            return "SKIP", "skipped"
        elif outcome is None:
            return "UNKNOWN", "unknown"
        else:
            return outcome.upper(), outcome


def calculate_session_stats(test_outcomes: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Calculate session summary statistics from test outcomes.

    Args:
        test_outcomes: Dict mapping nodeid to test data with keys:
            - call_outcome: Outcome from call phase
            - has_setup_error: Whether setup phase failed
            - has_teardown_error: Whether teardown phase failed
            - has_xfail_marker: Whether test has xfail marker
            - has_wasxfail: Whether test has wasxfail field (optional)
            - setup_skipped: Whether test was skipped in setup (optional)

    Returns:
        Dict with keys: total_tests, passed, failed, skipped, xfailed, xpassed, errors
    """
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
        has_wasxfail = test_data.get("has_wasxfail", False)
        setup_skipped = test_data.get("setup_skipped", False)

        # Handle tests with wasxfail (either from xfail(run=False) or pytest.xfail() in setup)
        # These are always counted as xfailed, regardless of xfail marker
        if has_wasxfail and call_outcome is None:
            xfailed += 1
        # Count based on call phase outcome and xfail marker
        elif has_xfail_marker:
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

    return {
        "total_tests": len(test_outcomes),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "xfailed": xfailed,
        "xpassed": xpassed,
        "errors": errors,
    }


def get_current_utc_time() -> datetime:
    """Get current UTC time with timezone awareness.

    Returns:
        Current datetime in UTC with timezone info
    """
    return datetime.now(timezone.utc)


def group_test_reports_by_phase(test_reports) -> dict[str, dict[str, Any]]:
    """Group test reports by nodeid and phase.

    Args:
        test_reports: List of TestReport objects

    Returns:
        Dict mapping nodeid to dict with setup/call/teardown reports
    """
    grouped = {}
    for report in test_reports:
        if report.nodeid not in grouped:
            grouped[report.nodeid] = {"setup": None, "call": None, "teardown": None}
        grouped[report.nodeid][report.when] = report
    return grouped


def create_test_outcome_entry(keywords: dict) -> dict:
    """Create a new test outcome tracking entry.

    Args:
        keywords: Test keywords dict from the test report

    Returns:
        Dict with initial test outcome tracking fields
    """
    return {
        "call_outcome": None,
        "has_setup_error": False,
        "has_teardown_error": False,
        "has_xfail_marker": "xfail" in keywords,
        "has_wasxfail": False,
        "setup_skipped": False,
    }


def update_test_outcome(
    test_outcomes: dict,
    nodeid: str,
    when: str,
    outcome: str,
    keywords: dict,
    record: dict
) -> None:
    """Update test outcomes tracking based on a test report.

    Args:
        test_outcomes: Dict mapping nodeid to test outcome data
        nodeid: Test node ID
        when: Test phase (setup, call, teardown)
        outcome: Test outcome (passed, failed, skipped)
        keywords: Test keywords dict
        record: Full record dict from JSONL (for wasxfail field)
    """
    if nodeid not in test_outcomes:
        test_outcomes[nodeid] = create_test_outcome_entry(keywords)

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


def update_timestamp_bounds(
    current_min: float | None,
    current_max: float | None,
    start: float | None,
    stop: float | None
) -> tuple[float | None, float | None]:
    """Update min/max timestamp bounds with new values.

    Args:
        current_min: Current minimum timestamp or None
        current_max: Current maximum timestamp or None
        start: New start timestamp or None
        stop: New stop timestamp or None

    Returns:
        Tuple of (new_min, new_max) timestamps
    """
    new_min = current_min
    new_max = current_max

    if start is not None:
        if new_min is None or start < new_min:
            new_min = start

    if stop is not None:
        if new_max is None or stop > new_max:
            new_max = stop

    return new_min, new_max
