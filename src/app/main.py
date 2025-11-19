"""FastAPI application for pytest-webreportlog web service."""
import json
import re
import asyncio
from pathlib import Path
from typing import Annotated, Optional
from fastapi import FastAPI, Depends, UploadFile, File, Request, HTTPException, Body
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from ansi2html import Ansi2HTMLConverter
from markupsafe import Markup
from pydantic import BaseModel

from .database import create_db_and_tables, get_session as get_db_session, engine
from .models import Session as TestSession, TestReport
from .parser import parse_jsonl_report
from .streaming import process_event


app = FastAPI(title="pytest-webreportlog Web Viewer")

# Templates
templates = Jinja2Templates(directory="src/app/templates")

# Create ANSI to HTML converter (reuse instance for performance)
ansi_converter = Ansi2HTMLConverter(inline=True, scheme='xterm')

# Add custom Jinja filter to convert ANSI color codes to HTML
def strip_ansi(text):
    """Convert ANSI color codes to HTML styling."""
    try:
        if text is None:
            return ""
        # Convert to string if not already
        if not isinstance(text, str):
            text = str(text)
        # Convert ANSI codes to HTML with inline styles
        html = ansi_converter.convert(text, full=False)
        # Return as safe HTML so Jinja doesn't escape it
        return Markup(html)
    except Exception as e:
        # Log error and return escaped original text
        print(f"Error in strip_ansi: {e}, type: {type(text)}, value: {repr(text)[:100]}")
        return str(text) if text is not None else ""

templates.env.filters['strip_ansi'] = strip_ansi

# Static files (for future use)
app.mount("/static", StaticFiles(directory="src/app/static"), name="static")


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    create_db_and_tables()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db_session)):
    """Show list of all test sessions."""
    statement = select(TestSession).order_by(TestSession.created_at.desc())
    sessions = db.exec(statement).all()

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "sessions": sessions}
    )


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
async def view_session(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db_session)
):
    """Show detailed view of a specific test session."""
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all test reports for this session
    statement = select(TestReport).where(
        TestReport.session_id == session_id
    ).order_by(TestReport.nodeid, TestReport.when)

    test_reports = db.exec(statement).all()

    # Build test entries using helper function
    test_entries = build_test_entries(test_reports)

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "session": session,
            "test_entries": test_entries
        }
    )


@app.get("/history", response_class=HTMLResponse)
async def view_all_history(
    request: Request,
    sort_by: str = "nodeid",
    sort_dir: str = "asc",
    db: Session = Depends(get_db_session)
):
    """Show overview of all tests with aggregated statistics."""
    from sqlalchemy import func, case

    # Get all unique nodeids with aggregated stats
    # We need to group by nodeid and calculate:
    # - Total runs (count of test reports for call phase)
    # - Pass rate (percentage of passed tests)
    # - Average duration (avg of setup + call + teardown)
    # - Latest result (most recent outcome)
    # - Last run date (max session date)

    # First, get all call phase reports with their aggregated durations
    statement = (
        select(
            TestReport.nodeid,
            func.count(func.distinct(TestReport.session_id)).label("total_runs"),
            func.sum(case((TestReport.outcome == "passed", 1), else_=0)).label("passed_runs"),
            func.avg(TestReport.duration).label("avg_call_duration"),
            func.max(TestSession.created_at).label("last_run")
        )
        .join(TestSession)
        .where(TestReport.when == "call")
        .group_by(TestReport.nodeid)
    )

    # Apply sorting
    if sort_by == "nodeid":
        order_col = TestReport.nodeid
    elif sort_by == "total_runs":
        order_col = func.count(func.distinct(TestReport.session_id))
    elif sort_by == "pass_rate":
        order_col = func.sum(case((TestReport.outcome == "passed", 1), else_=0)) * 100.0 / func.count(func.distinct(TestReport.session_id))
    elif sort_by == "avg_duration":
        order_col = func.avg(TestReport.duration)
    elif sort_by == "last_run":
        order_col = func.max(TestSession.created_at)
    else:
        order_col = TestReport.nodeid

    if sort_dir == "desc":
        statement = statement.order_by(order_col.desc())
    else:
        statement = statement.order_by(order_col.asc())

    results = db.exec(statement).all()

    # Build test summary entries
    test_summaries = []
    for row in results:
        nodeid = row.nodeid
        total_runs = row.total_runs
        passed_runs = row.passed_runs
        pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0
        avg_call_duration = row.avg_call_duration or 0.0
        last_run = row.last_run

        # Get the latest result for this test
        latest_statement = (
            select(TestReport)
            .join(TestSession)
            .where(TestReport.nodeid == nodeid)
            .where(TestReport.when == "call")
            .order_by(TestSession.created_at.desc())
            .limit(1)
        )
        latest_result = db.exec(latest_statement).first()

        if latest_result:
            location = latest_result.location
            outcome = latest_result.outcome
            has_xfail = "xfail" in latest_result.keywords
            if has_xfail:
                if outcome == "skipped":
                    result_label = "XFAIL"
                elif outcome == "passed":
                    result_label = "XPASS"
                elif outcome == "failed":
                    result_label = "FAIL"  # Strict xfail that passed
                else:
                    result_label = outcome.upper()
            else:
                result_label = {
                    "passed": "PASS",
                    "failed": "FAIL",
                    "skipped": "SKIP",
                }.get(outcome, outcome.upper())
        else:
            location = ["", 0, ""]  # Default location if no results found
            result_label = "UNKNOWN"

        test_summaries.append({
            "nodeid": nodeid,
            "location": location,
            "total_runs": total_runs,
            "passed_runs": passed_runs,
            "pass_rate": pass_rate,
            "avg_duration": avg_call_duration,
            "last_run": last_run,
            "latest_result": result_label,
        })

    return templates.TemplateResponse(
        "history_overview.html",
        {
            "request": request,
            "test_summaries": test_summaries,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        }
    )


@app.get("/history/{nodeid:path}", response_class=HTMLResponse)
async def view_history(
    request: Request,
    nodeid: str,
    db: Session = Depends(get_db_session)
):
    """Show historical test results for a specific test across all sessions."""
    # Query all test reports for this nodeid across all sessions
    statement = (
        select(TestReport, TestSession)
        .join(TestSession)
        .where(TestReport.nodeid == nodeid)
        .order_by(TestSession.created_at.desc(), TestReport.when)
    )

    results = db.exec(statement).all()

    if not results:
        raise HTTPException(status_code=404, detail=f"No test history found for {nodeid}")

    # Get location from first report
    first_report = results[0][0]
    location = first_report.location

    # Group by session and aggregate phases
    session_runs = {}
    for report, session in results:
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
    all_durations = {"setup": [], "call": [], "teardown": [], "total": []}

    for session_id, run in session_runs.items():
        session = run["session"]
        setup_report = run["setup"]
        call_report = run["call"]
        teardown_report = run["teardown"]

        # Calculate durations
        setup_duration = setup_report.duration if setup_report else 0.0
        call_duration = call_report.duration if call_report else 0.0
        teardown_duration = teardown_report.duration if teardown_report else 0.0
        total_duration = setup_duration + call_duration + teardown_duration

        # Determine outcome from call phase
        if call_report:
            outcome = call_report.outcome
            # Check for xfail marker
            has_xfail = "xfail" in call_report.keywords
            if has_xfail:
                if outcome == "skipped":
                    result_label = "XFAIL"
                elif outcome == "passed":
                    result_label = "XPASS"
                elif outcome == "failed":
                    result_label = "FAIL"  # Strict xfail that passed
                else:
                    result_label = outcome.upper()
            else:
                result_label = {
                    "passed": "PASS",
                    "failed": "FAIL",
                    "skipped": "SKIP",
                }.get(outcome, outcome.upper())
        else:
            outcome = "unknown"
            result_label = "UNKNOWN"

        # Check for setup/teardown errors
        has_error = (setup_report and setup_report.outcome == "failed") or \
                   (teardown_report and teardown_report.outcome == "failed")

        history_entries.append({
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
        })

        # Track all durations for max calculation
        all_durations["setup"].append(setup_duration)
        all_durations["call"].append(call_duration)
        all_durations["teardown"].append(teardown_duration)
        all_durations["total"].append(total_duration)

    # Calculate statistics
    total_runs = len(history_entries)
    passed_runs = sum(1 for e in history_entries if e["outcome"] == "passed")
    pass_rate = (passed_runs / total_runs * 100) if total_runs > 0 else 0

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

    return templates.TemplateResponse(
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
        }
    )


@app.post("/upload")
async def upload_jsonl(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session)
):
    """Upload and parse a JSONL report file."""
    if not file.filename.endswith(".jsonl"):
        raise HTTPException(status_code=400, detail="File must be a .jsonl file")

    # Read file content
    content = await file.read()
    lines = content.decode("utf-8").strip().split("\n")

    # Parse and store
    session = parse_jsonl_report(lines, db)

    return {
        "status": "success",
        "session_id": session.id,
        "total_tests": session.total_tests,
        "passed": session.passed,
        "failed": session.failed,
        "skipped": session.skipped,
        "xfailed": session.xfailed,
        "xpassed": session.xpassed,
        "errors": session.errors,
    }


@app.get("/api/sessions")
async def list_sessions(db: Session = Depends(get_db_session)):
    """API endpoint to list all sessions."""
    statement = select(TestSession).order_by(TestSession.created_at.desc())
    sessions = db.exec(statement).all()
    return sessions


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: int, db: Session = Depends(get_db_session)):
    """API endpoint to get a specific session with all test reports."""
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int, db: Session = Depends(get_db_session)):
    """API endpoint to delete a session and all its related test reports."""
    # Get session
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete all related test reports first
    statement = select(TestReport).where(TestReport.session_id == session_id)
    test_reports = db.exec(statement).all()
    for report in test_reports:
        db.delete(report)

    # Delete the session
    db.delete(session)
    db.commit()

    return {"status": "success", "message": f"Session {session_id} deleted successfully"}


def build_test_entries(test_reports: list[TestReport]) -> list[dict]:
    """Build test entries from test reports.

    This helper function converts raw TestReport objects into structured
    test entries suitable for rendering, grouping by nodeid and phase.
    """
    # Group reports by nodeid
    grouped_reports = {}
    for report in test_reports:
        if report.nodeid not in grouped_reports:
            grouped_reports[report.nodeid] = {"setup": None, "call": None, "teardown": None}
        grouped_reports[report.nodeid][report.when] = report

    # Build test entries (similar to pytest-html)
    test_entries = []

    for nodeid, phases in grouped_reports.items():
        setup_report = phases.get("setup")
        call_report = phases.get("call")
        teardown_report = phases.get("teardown")

        # Add setup error entry if setup failed
        if setup_report and setup_report.outcome == "failed":
            test_entries.append({
                "nodeid": f"{nodeid}::setup",
                "display_name": nodeid,
                "location": setup_report.location,
                "outcome": "error",  # Setup failures are errors
                "result_label": "ERROR",
                "duration": setup_report.duration,
                "report": setup_report,
                "is_phase_error": True,
                "phase": "setup",
            })

        # Add main test entry (based on call phase)
        if call_report:
            # Check if test has xfail marker
            has_xfail = "xfail" in call_report.keywords

            # Determine outcome label based on xfail marker and outcome
            if has_xfail:
                if call_report.outcome == "skipped":
                    result_label = "XFAIL"  # Expected to fail and did
                    outcome = "xfailed"
                elif call_report.outcome == "passed":
                    result_label = "XPASS"  # Expected to fail but passed
                    outcome = "xpassed"
                elif call_report.outcome == "failed":
                    result_label = "FAIL"  # Strict xfail that passed (reported as failed)
                    outcome = "failed"
                else:
                    result_label = call_report.outcome.upper()
                    outcome = call_report.outcome
            else:
                # Regular tests without xfail marker
                if call_report.outcome == "failed":
                    result_label = "FAIL"
                elif call_report.outcome == "passed":
                    result_label = "PASS"
                elif call_report.outcome == "skipped":
                    result_label = "SKIP"
                else:
                    result_label = call_report.outcome.upper()
                outcome = call_report.outcome

            # Calculate total duration across all phases
            total_duration = 0
            if setup_report:
                total_duration += setup_report.duration
            if call_report:
                total_duration += call_report.duration
            if teardown_report:
                total_duration += teardown_report.duration

            test_entries.append({
                "nodeid": nodeid,
                "display_name": nodeid,
                "location": call_report.location,
                "outcome": outcome,
                "result_label": result_label,
                "duration": total_duration,
                "report": call_report,  # Main report for backward compatibility
                "setup_report": setup_report,
                "call_report": call_report,
                "teardown_report": teardown_report,
                "is_phase_error": False,
                "phase": "call",
            })
        elif setup_report and not call_report and setup_report.outcome != "failed":
            # Tests without call phase (e.g., xfail(run=False) or skipped in setup)
            # Exclude setup failures - they're already handled as ERROR entries above
            # Check if test has xfail marker from setup report
            has_xfail = "xfail" in setup_report.keywords

            # Check for wasxfail field which indicates xfail(run=False)
            has_wasxfail = hasattr(setup_report, "wasxfail") and setup_report.wasxfail

            if has_wasxfail:
                # xfail(run=False) - test was not run
                result_label = "XFAIL"
                outcome = "xfailed"
            elif setup_report.outcome == "skipped":
                # Test was skipped (not due to xfail)
                result_label = "SKIP"
                outcome = "skipped"
            else:
                # Fallback to setup outcome
                result_label = setup_report.outcome.upper()
                outcome = setup_report.outcome

            # Calculate total duration across all phases
            total_duration = 0
            if setup_report:
                total_duration += setup_report.duration
            if teardown_report:
                total_duration += teardown_report.duration

            test_entries.append({
                "nodeid": nodeid,
                "display_name": nodeid,
                "location": setup_report.location,
                "outcome": outcome,
                "result_label": result_label,
                "duration": total_duration,
                "report": setup_report,  # Use setup report as main report
                "setup_report": setup_report,
                "call_report": None,
                "teardown_report": teardown_report,
                "is_phase_error": False,
                "phase": "setup",
            })

        # Add teardown error entry if teardown failed
        if teardown_report and teardown_report.outcome == "failed":
            test_entries.append({
                "nodeid": f"{nodeid}::teardown",
                "display_name": nodeid,
                "location": teardown_report.location,
                "outcome": "error",  # Teardown failures are errors
                "result_label": "ERROR",
                "duration": teardown_report.duration,
                "report": teardown_report,
                "is_phase_error": True,
                "phase": "teardown",
            })

    return test_entries


@app.get("/api/sessions/{session_id}/test-entries", response_class=HTMLResponse)
async def get_test_entries_html(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db_session)
):
    """API endpoint to get rendered HTML for test entries.

    Returns HTML fragments for test result rows that can be inserted into the DOM.
    """
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get all test reports for this session
    statement = select(TestReport).where(
        TestReport.session_id == session_id
    ).order_by(TestReport.nodeid, TestReport.when)

    test_reports = db.exec(statement).all()

    # Build test entries
    test_entries = build_test_entries(test_reports)

    return templates.TemplateResponse(
        "_test_entry.html",
        {"request": request, "test_entries": test_entries}
    )


# Streaming infrastructure
class EventBroadcaster:
    """Simple SSE broadcaster for session updates."""

    def __init__(self):
        self.channels: dict[int, set[asyncio.Queue]] = {}

    def subscribe(self, session_id: int) -> asyncio.Queue:
        """Subscribe to updates for a session."""
        queue = asyncio.Queue()
        if session_id not in self.channels:
            self.channels[session_id] = set()
        self.channels[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: int, queue: asyncio.Queue):
        """Unsubscribe from session updates."""
        if session_id in self.channels:
            self.channels[session_id].discard(queue)
            if not self.channels[session_id]:
                del self.channels[session_id]

    async def broadcast(self, session_id: int, message: dict):
        """Broadcast update to all subscribers of a session."""
        if session_id in self.channels:
            dead_queues = set()
            for queue in self.channels[session_id]:
                try:
                    await queue.put(message)
                except:
                    dead_queues.add(queue)

            # Clean up dead queues
            for queue in dead_queues:
                self.channels[session_id].discard(queue)


broadcaster = EventBroadcaster()


class StreamEventRequest(BaseModel):
    """Request model for streaming events."""
    session_id: Optional[int] = None
    event: str  # JSONL line


# Map external session UUIDs to internal database session IDs
session_uuid_map: dict[str, int] = {}

@app.post("/api/stream/event")
async def stream_event(request: Request):
    """Receive a single test event and process it.

    This endpoint allows remote test runners to send events as they happen.
    Accepts JSONL line directly as request body (text/plain) or as JSON object.
    Expects X-Session-ID header to identify which session events belong to.
    """
    session_id = None
    db = None
    try:
        # Get database session
        db_gen = get_db_session()
        db = next(db_gen)

        # Get session UUID from header
        session_uuid = request.headers.get("x-session-id")

        # Try to parse as JSON first (for API clients sending structured data)
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict) and "event" in body:
                # Structured format: {"session_id": ..., "event": "..."}
                event_line = body["event"]
                session_id = body.get("session_id", session_id)
            else:
                # Assume the JSON itself is the event
                event_line = json.dumps(body)
        else:
            # Plain text format - JSONL line directly in body
            body_bytes = await request.body()
            event_line = body_bytes.decode("utf-8").strip()

        # Look up session ID from UUID if we've seen this session before
        if session_uuid and session_uuid in session_uuid_map:
            session_id = session_uuid_map[session_uuid]

        session, event_type = process_event(event_line, session_id, db)

        # Store the mapping for new sessions
        if session_uuid and event_type == "session_start":
            session_uuid_map[session_uuid] = session.id

        # Clean up mapping when session finishes
        if session_uuid and event_type == "session_finish":
            if session_uuid in session_uuid_map:
                del session_uuid_map[session_uuid]

        # Broadcast update to SSE subscribers
        await broadcaster.broadcast(session.id, {
            "type": event_type,
            "session_id": session.id,
            "session": {
                "id": session.id,
                "status": session.status,
                "total_tests": session.total_tests,
                "passed": session.passed,
                "failed": session.failed,
                "skipped": session.skipped,
                "xfailed": session.xfailed,
                "xpassed": session.xpassed,
                "errors": session.errors,
                "exitstatus": session.exitstatus,
            }
        })

        return {
            "status": "success",
            "session_id": session.id,
            "event_type": event_type,
            "session": {
                "total_tests": session.total_tests,
                "passed": session.passed,
                "failed": session.failed,
                "skipped": session.skipped,
                "xfailed": session.xfailed,
                "xpassed": session.xpassed,
                "errors": session.errors,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if db:
            try:
                next(db_gen, None)  # Close the generator
            except:
                pass


@app.get("/api/stream/{session_id}")
async def stream_session_updates(session_id: int, db: Session = Depends(get_db_session)):
    """Server-Sent Events endpoint for real-time session updates.

    Clients can subscribe to this endpoint to receive live updates as tests run.
    Clients can subscribe before the session is created for real-time monitoring.
    """
    async def event_generator():
        queue = broadcaster.subscribe(session_id)
        try:
            # Send initial session state
            yield f"data: {json.dumps({'type': 'initial', 'session_id': session_id})}\n\n"

            # Stream updates
            while True:
                message = await queue.get()
                yield f"data: {json.dumps(message)}\n\n"

                # Stop streaming when session completes
                if message.get("type") == "session_finish":
                    break
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
