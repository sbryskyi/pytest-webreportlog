"""Session-related routes."""
import json
from fastapi import APIRouter, Depends, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import delete
from sqlmodel import Session, select

from ..database import get_session as get_db_session
from ..models import Session as TestSession, TestReport
from ..parser import parse_jsonl_report
from ..services.entry_builder import build_test_entries
from ..templates_config import templates

router = APIRouter()

# Configuration constants
MAX_UPLOAD_SIZE_MB = 100


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db_session)):
    """Show list of all test sessions."""
    statement = select(TestSession).order_by(TestSession.created_at.desc())
    sessions = db.exec(statement).all()

    return templates.TemplateResponse(
        "index.html",
        {"request": request, "sessions": sessions}
    )


@router.get("/sessions/{session_id}", response_class=HTMLResponse)
async def view_session(
    request: Request,
    session_id: int,
    db: Session = Depends(get_db_session)
):
    """Show detailed view of a specific test session."""
    from ..main import templates

    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    statement = select(TestReport).where(
        TestReport.session_id == session_id
    ).order_by(TestReport.nodeid, TestReport.when)

    test_reports = db.exec(statement).all()

    test_entries = build_test_entries(test_reports)

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "session": session,
            "test_entries": test_entries
        }
    )


@router.post("/upload")
async def upload_jsonl(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session)
):
    """Upload and parse a JSONL report file."""
    # Validate file extension
    if not file.filename or not file.filename.endswith(".jsonl"):
        raise HTTPException(status_code=400, detail="File must be a .jsonl file")

    # Read file content with size limit
    max_size = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # Convert to bytes
    content = b""
    bytes_read = 0

    chunk_size = 1024 * 1024  # Read 1MB at a time
    while chunk := await file.read(chunk_size):
        bytes_read += len(chunk)
        if bytes_read > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_MB}MB"
            )
        content += chunk

    # Decode content
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8")

    lines = text_content.strip().split("\n")

    # Validate non-empty
    if not lines or (len(lines) == 1 and not lines[0].strip()):
        raise HTTPException(status_code=400, detail="File is empty")

    # Parse and store with error handling
    try:
        session = parse_jsonl_report(lines, db)
    except json.JSONDecodeError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid JSONL format: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to parse report: {str(e)}")

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


@router.get("/api/sessions")
async def list_sessions(db: Session = Depends(get_db_session)):
    """API endpoint to list all sessions."""
    statement = select(TestSession).order_by(TestSession.created_at.desc())
    sessions = db.exec(statement).all()
    return sessions


@router.get("/api/sessions/{session_id}")
async def get_session(session_id: int, db: Session = Depends(get_db_session)):
    """API endpoint to get a specific session with all test reports."""
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int, db: Session = Depends(get_db_session)):
    """API endpoint to delete a session and all its related test reports."""
    # Get session
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    db.exec(delete(TestReport).where(TestReport.session_id == session_id))
    db.delete(session)
    db.commit()

    return {"status": "success", "message": f"Session {session_id} deleted successfully"}


@router.get("/api/sessions/{session_id}/test-entries", response_class=HTMLResponse)
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
