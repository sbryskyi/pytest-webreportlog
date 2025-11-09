"""FastAPI application for pytest-webreportlog web service."""
import json
import re
from pathlib import Path
from typing import Annotated
from fastapi import FastAPI, Depends, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from ansi2html import Ansi2HTMLConverter
from markupsafe import Markup

from .database import create_db_and_tables, get_session, engine
from .models import Session as TestSession, TestReport
from .parser import parse_jsonl_report


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
async def index(request: Request, db: Session = Depends(get_session)):
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
    db: Session = Depends(get_session)
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

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "session": session,
            "test_entries": test_entries
        }
    )


@app.post("/upload")
async def upload_jsonl(
    file: UploadFile = File(...),
    db: Session = Depends(get_session)
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
async def list_sessions(db: Session = Depends(get_session)):
    """API endpoint to list all sessions."""
    statement = select(TestSession).order_by(TestSession.created_at.desc())
    sessions = db.exec(statement).all()
    return sessions


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: int, db: Session = Depends(get_session)):
    """API endpoint to get a specific session with all test reports."""
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
