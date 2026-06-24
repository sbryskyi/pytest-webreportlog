"""FastAPI application for the webreportlog web viewer service."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import create_db_and_tables, ensure_columns
from .routes import history_router, sessions_router, streaming_router
from .templates_config import (  # noqa: F401 — re-exported for tests
    ansi_to_html,
    templates,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    create_db_and_tables()
    ensure_columns()
    _mark_stale_sessions_interrupted()
    yield


def _mark_stale_sessions_interrupted() -> None:
    """Mark any IN_PROGRESS sessions as INTERRUPTED on startup and clear in-memory state."""
    from sqlmodel import Session, select

    from .database import engine
    from .models import Session as TestSession
    from .models import SessionStatus
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


app = FastAPI(title="webreportlog Web Viewer", lifespan=lifespan)

app.include_router(sessions_router)
app.include_router(history_router)
app.include_router(streaming_router)
