"""History-related routes."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import case, func
from sqlmodel import Session, col, select

from ..database import get_session as get_db_session
from ..models import Session as TestSession
from ..models import TestReport
from ..templates_config import templates
from ..utils import build_facets, determine_test_outcome

router = APIRouter()


def _get_latest_test_results(db: Session) -> dict:
    """Get latest test results for all nodeids using a subquery.

    Returns:
        Dict mapping nodeid to (outcome, keywords, location)
    """
    # Subquery: highest session_id (most recent) per nodeid for call-phase reports
    latest_subq = (
        select(
            TestReport.nodeid,
            func.max(TestReport.session_id).label("max_session_id"),
        )
        .where(TestReport.when == "call")
        .group_by(TestReport.nodeid)
        .subquery()
    )

    statement = (
        select(TestReport)
        .join(
            latest_subq,
            (col(TestReport.nodeid) == latest_subq.c.nodeid)
            & (col(TestReport.session_id) == latest_subq.c.max_session_id),
        )
        .where(TestReport.when == "call")
    )

    return {
        report.nodeid: (report.outcome, report.keywords, report.location)
        for report in db.exec(statement).all()
    }


def _calculate_duration_stats(all_durations: dict) -> tuple[dict, dict, dict]:
    """Calculate average, max, and min duration statistics.

    Args:
        all_durations: Dict with keys (setup, call, teardown, total) and lists of durations

    Returns:
        Tuple of (avg_durations, max_durations, min_durations)
    """
    avg_durations = {
        phase: sum(durations) / len(durations) if durations else 0
        for phase, durations in all_durations.items()
    }

    max_durations = {
        phase: max(durations) if durations else 0
        for phase, durations in all_durations.items()
    }

    min_durations = {
        phase: min(durations) if durations else 0
        for phase, durations in all_durations.items()
    }

    return avg_durations, max_durations, min_durations


@router.get("/history", response_class=HTMLResponse)
async def view_all_history(
    request: Request,
    sort_by: str = "nodeid",
    sort_dir: Literal["asc", "desc"] = "asc",
    db: Session = Depends(get_db_session),
):
    """Show overview of all tests with aggregated statistics."""
    # Get all unique nodeids with aggregated stats
    statement = (
        # SQLModel's select() overloads only cover up to 4 columns; this query
        # selects 5, so the call falls outside the typed overloads.
        select(  # type: ignore[call-overload]
            col(TestReport.nodeid),
            func.count(func.distinct(TestReport.session_id)).label("total_runs"),
            func.sum(case((col(TestReport.outcome) == "passed", 1), else_=0)).label(
                "passed_runs"
            ),
            func.avg(TestReport.duration).label("avg_call_duration"),
            func.max(TestSession.created_at).label("last_run"),
        )
        .join(TestSession)
        .where(TestReport.when == "call")
        .group_by(TestReport.nodeid)
    )

    # Apply sorting
    order_col: Any
    if sort_by == "nodeid":
        order_col = col(TestReport.nodeid)
    elif sort_by == "total_runs":
        order_col = func.count(func.distinct(TestReport.session_id))
    elif sort_by == "pass_rate":
        order_col = (
            func.sum(case((col(TestReport.outcome) == "passed", 1), else_=0))
            * 100.0
            / func.count(func.distinct(TestReport.session_id))
        )
    elif sort_by == "avg_duration":
        order_col = func.avg(TestReport.duration)
    elif sort_by == "last_run":
        order_col = func.max(TestSession.created_at)
    else:
        order_col = col(TestReport.nodeid)

    if sort_dir == "desc":
        statement = statement.order_by(order_col.desc())
    else:
        statement = statement.order_by(order_col.asc())

    results = db.exec(statement).all()

    # Get latest results for all tests in a single efficient query
    latest_results = _get_latest_test_results(db)

    # Build test summary entries
    test_summaries = []
    for row in results:
        nodeid = row.nodeid
        total_runs = row.total_runs
        passed_runs = row.passed_runs
        pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0
        avg_call_duration = row.avg_call_duration or 0.0
        last_run = row.last_run

        # Get latest result from our efficient lookup
        if nodeid in latest_results:
            outcome, keywords, location = latest_results[nodeid]
            result_label, _ = determine_test_outcome(outcome, keywords)
        else:
            location = ["", 0, ""]
            result_label = "UNKNOWN"

        test_summaries.append(
            {
                "nodeid": nodeid,
                "location": location,
                "total_runs": total_runs,
                "passed_runs": passed_runs,
                "pass_rate": pass_rate,
                "avg_duration": avg_call_duration,
                "last_run": last_run,
                "latest_result": result_label,
            }
        )

    return templates.TemplateResponse(
        request,
        "history_overview.html",
        {
            "request": request,
            "test_summaries": test_summaries,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        },
    )


@router.get("/history/{nodeid:path}", response_class=HTMLResponse)
async def view_history(
    request: Request, nodeid: str, db: Session = Depends(get_db_session)
):
    """Show historical test results for a specific test across all sessions."""
    # Query all test reports for this nodeid across all sessions
    statement = (
        select(TestReport, TestSession)
        .join(TestSession)
        .where(TestReport.nodeid == nodeid)
        .order_by(col(TestSession.created_at).desc(), TestReport.when)
    )

    results = db.exec(statement).all()

    if not results:
        raise HTTPException(
            status_code=404, detail=f"No test history found for {nodeid}"
        )

    # Get location from first report
    first_report = results[0][0]
    location = first_report.location

    # Group by session and aggregate phases
    session_runs: dict[int, dict[str, Any]] = {}
    for report, session in results:
        assert session.id is not None  # persisted sessions always have an id
        if session.id not in session_runs:
            session_runs[session.id] = {
                "session": session,
                "setup": None,
                "call": None,
                "teardown": None,
            }
        session_runs[session.id][report.when] = report

    # Build history entries with aggregated data
    history_entries = []
    all_durations: dict[str, list[float]] = {
        "setup": [],
        "call": [],
        "teardown": [],
        "total": [],
    }

    for run in session_runs.values():
        session = run["session"]
        setup_report = run["setup"]
        call_report = run["call"]
        teardown_report = run["teardown"]

        # Calculate durations
        setup_duration = setup_report.duration if setup_report else 0.0
        call_duration = call_report.duration if call_report else 0.0
        teardown_duration = teardown_report.duration if teardown_report else 0.0
        total_duration = setup_duration + call_duration + teardown_duration

        # Determine outcome from call phase using shared utility
        if call_report:
            result_label, outcome = determine_test_outcome(
                call_report.outcome, call_report.keywords
            )
        else:
            outcome = "unknown"
            result_label = "UNKNOWN"

        # Check for setup/teardown errors
        has_error = (setup_report and setup_report.outcome == "failed") or (
            teardown_report and teardown_report.outcome == "failed"
        )

        history_entries.append(
            {
                "session": session,
                "outcome": outcome,
                "result_label": result_label,
                "has_error": has_error,
                "setup_duration": setup_duration,
                "call_duration": call_duration,
                "teardown_duration": teardown_duration,
                "total_duration": total_duration,
                "setup_report": setup_report,
                "call_report": call_report,
                "teardown_report": teardown_report,
            }
        )

        # Track all durations for stats calculation
        all_durations["setup"].append(setup_duration)
        all_durations["call"].append(call_duration)
        all_durations["teardown"].append(teardown_duration)
        all_durations["total"].append(total_duration)

    # Calculate statistics
    total_runs = len(history_entries)
    passed_runs = sum(1 for e in history_entries if e["outcome"] == "passed")
    pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0

    avg_durations, max_durations, min_durations = _calculate_duration_stats(
        all_durations
    )

    facets = build_facets([e["session"] for e in history_entries])

    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "request": request,
            "nodeid": nodeid,
            "location": location,
            "history_entries": history_entries,
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "pass_rate": pass_rate,
            "avg_durations": avg_durations,
            "max_durations": max_durations,
            "min_durations": min_durations,
            "facets": facets,
        },
    )
