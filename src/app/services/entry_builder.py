"""Service for building test entries from test reports."""
from ..models import TestReport
from ..utils import determine_test_outcome, group_test_reports_by_phase


def _calculate_total_duration(setup_report, call_report, teardown_report) -> float:
    """Calculate total duration across all test phases."""
    total = 0.0
    if setup_report:
        total += setup_report.duration
    if call_report:
        total += call_report.duration
    if teardown_report:
        total += teardown_report.duration
    return total


def _create_phase_error_entry(nodeid: str, report, phase: str) -> dict:
    """Create test entry for setup/teardown error."""
    return {
        "nodeid": f"{nodeid}::{phase}",
        "display_name": nodeid,
        "location": report.location,
        "outcome": "error",
        "result_label": "ERROR",
        "duration": report.duration,
        "report": report,
        "is_phase_error": True,
        "phase": phase,
    }


def _create_call_phase_entry(nodeid: str, setup_report, call_report, teardown_report) -> dict:
    """Create test entry for call phase."""
    # Use shared utility to determine outcome
    has_wasxfail = hasattr(call_report, "wasxfail") and call_report.wasxfail
    result_label, outcome = determine_test_outcome(
        call_report.outcome,
        call_report.keywords,
        has_wasxfail
    )

    total_duration = _calculate_total_duration(setup_report, call_report, teardown_report)

    return {
        "nodeid": nodeid,
        "display_name": nodeid,
        "location": call_report.location,
        "outcome": outcome,
        "result_label": result_label,
        "duration": total_duration,
        "report": call_report,
        "setup_report": setup_report,
        "call_report": call_report,
        "teardown_report": teardown_report,
        "is_phase_error": False,
        "phase": "call",
    }


def _create_setup_phase_entry(nodeid: str, setup_report, teardown_report) -> dict:
    """Create test entry for tests without call phase (skipped or xfail(run=False))."""
    has_wasxfail = hasattr(setup_report, "wasxfail") and setup_report.wasxfail
    result_label, outcome = determine_test_outcome(
        setup_report.outcome,
        setup_report.keywords,
        has_wasxfail
    )

    total_duration = _calculate_total_duration(setup_report, None, teardown_report)

    return {
        "nodeid": nodeid,
        "display_name": nodeid,
        "location": setup_report.location,
        "outcome": outcome,
        "result_label": result_label,
        "duration": total_duration,
        "report": setup_report,
        "setup_report": setup_report,
        "call_report": None,
        "teardown_report": teardown_report,
        "is_phase_error": False,
        "phase": "setup",
    }


def build_test_entries(test_reports: list[TestReport]) -> list[dict]:
    """Build test entries from test reports.

    This helper function converts raw TestReport objects into structured
    test entries suitable for rendering, grouping by nodeid and phase.
    """
    # Group reports by nodeid using shared utility
    grouped_reports = group_test_reports_by_phase(test_reports)

    # Build test entries
    test_entries = []

    for nodeid, phases in grouped_reports.items():
        setup_report = phases.get("setup")
        call_report = phases.get("call")
        teardown_report = phases.get("teardown")

        # Add setup error entry if setup failed
        if setup_report and setup_report.outcome == "failed":
            test_entries.append(_create_phase_error_entry(nodeid, setup_report, "setup"))

        # Add main test entry (based on call phase)
        if call_report:
            test_entries.append(_create_call_phase_entry(nodeid, setup_report, call_report, teardown_report))
        elif setup_report and not call_report and setup_report.outcome != "failed":
            # Tests without call phase (e.g., xfail(run=False) or skipped in setup)
            test_entries.append(_create_setup_phase_entry(nodeid, setup_report, teardown_report))

        # Add teardown error entry if teardown failed
        if teardown_report and teardown_report.outcome == "failed":
            test_entries.append(_create_phase_error_entry(nodeid, teardown_report, "teardown"))

    return test_entries
