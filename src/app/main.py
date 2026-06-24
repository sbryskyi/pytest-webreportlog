"""FastAPI application for pytest-webreportlog web service."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import create_db_and_tables
from .routes import sessions_router, history_router, streaming_router
from .templates_config import templates, ansi_to_html  # noqa: F401 — re-exported for tests

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    create_db_and_tables()
    _mark_stale_sessions_interrupted()
    yield


def _mark_stale_sessions_interrupted() -> None:
    """Mark any IN_PROGRESS sessions as INTERRUPTED on startup and clear in-memory state."""
    from sqlmodel import Session, select
    from .database import engine
    from .models import Session as TestSession, SessionStatus
    from .streaming import active_sessions

    with Session(engine) as db:
        stale = db.exec(
            select(TestSession).where(TestSession.status == SessionStatus.IN_PROGRESS.value)
        ).all()
        for session in stale:
            session.status = SessionStatus.INTERRUPTED.value
        if stale:
            db.commit()
            logger.info("Marked %d stale session(s) as INTERRUPTED", len(stale))

    active_sessions.clear()


app = FastAPI(title="pytest-webreportlog Web Viewer", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

app.include_router(sessions_router)
app.include_router(history_router)
app.include_router(streaming_router)
