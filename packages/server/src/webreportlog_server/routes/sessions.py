"""Session-related routes."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import delete, func
from sqlmodel import Session, select

from ..database import (
    get_configured_keep_recent,
    get_configured_max_bytes,
    get_database_path,
    get_database_size_bytes,
)
from ..database import (
    get_session as get_db_session,
)
from ..models import Session as TestSession
from ..models import TestReport
from ..services.entry_builder import build_test_entries
from ..services.retention import prune_database
from ..templates_config import templates
from ..utils import format_size, parse_size


class PruneRequest(BaseModel):
    """Optional overrides for a manual prune; falls back to env configuration."""
    max_size: str | None = None
    max_size_bytes: int | None = None
    keep_recent: int | None = None

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db_session)):
    """Show list of all test sessions."""
    statement = select(TestSession).order_by(TestSession.created_at.desc())
    sessions = db.exec(statement).all()

    return templates.TemplateResponse(
        request,
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
    session = db.get(TestSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    statement = select(TestReport).where(
        TestReport.session_id == session_id
    ).order_by(TestReport.nodeid, TestReport.when)

    test_reports = db.exec(statement).all()

    test_entries = build_test_entries(test_reports)

    return templates.TemplateResponse(
        request,
        "session.html",
        {
            "request": request,
            "session": session,
            "test_entries": test_entries
        }
    )


@router.get("/api/sessions")
async def list_sessions(db: Session = Depends(get_db_session)):
    """API endpoint to list all sessions."""
    statement = select(TestSession).order_by(TestSession.created_at.desc())
    sessions = db.exec(statement).all()
    return sessions


@router.get("/api/stats")
async def get_stats(db: Session = Depends(get_db_session)):
    """API endpoint reporting database size, configured cap, and record counts."""
    size_bytes = get_database_size_bytes()
    try:
        cap_bytes = get_configured_max_bytes()
    except ValueError:
        cap_bytes = None  # misconfigured cap shouldn't break the stats/footer
    over_cap = (
        size_bytes is not None and cap_bytes is not None and size_bytes > cap_bytes
    )
    session_count = db.exec(select(func.count()).select_from(TestSession)).one()
    report_count = db.exec(select(func.count()).select_from(TestReport)).one()
    return {
        "database": {
            "path": get_database_path(),
            "size_bytes": size_bytes,
            "size_human": format_size(size_bytes),
            "max_size_bytes": cap_bytes,
            "max_size_human": format_size(cap_bytes) if cap_bytes is not None else None,
            "over_cap": over_cap,
        },
        "sessions": session_count,
        "test_reports": report_count,
    }


@router.post("/api/prune")
def prune(
    body: PruneRequest | None = None,
    db: Session = Depends(get_db_session),
):
    """Prune the database to fit under a size cap (sync → runs in a threadpool).

    The cap comes from the request body (``max_size_bytes`` or ``max_size``) or, if
    omitted, from the ``WEBREPORTLOG_MAX_DB_SIZE`` environment variable.
    """
    body = body or PruneRequest()

    if body.max_size_bytes is not None:
        max_bytes: int | None = body.max_size_bytes
    elif body.max_size:
        try:
            max_bytes = parse_size(body.max_size)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        try:
            max_bytes = get_configured_max_bytes()
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid WEBREPORTLOG_MAX_DB_SIZE: {e}"
            ) from e

    if max_bytes is None:
        raise HTTPException(
            status_code=400,
            detail="No size cap configured. Set WEBREPORTLOG_MAX_DB_SIZE or pass max_size.",
        )

    keep_recent = (
        body.keep_recent if body.keep_recent is not None else get_configured_keep_recent()
    )
    return prune_database(db, max_bytes, keep_recent)


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
        request,
        "_test_entry.html",
        {"request": request, "test_entries": test_entries}
    )
