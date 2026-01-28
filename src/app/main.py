"""FastAPI application for pytest-webreportlog web service."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from ansi2html import Ansi2HTMLConverter
from markupsafe import Markup

from .database import create_db_and_tables
from .routes import sessions_router, history_router, streaming_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    create_db_and_tables()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(title="pytest-webreportlog Web Viewer", lifespan=lifespan)

# Configuration constants
ANSI_COLOR_SCHEME = 'xterm'
TEMPLATES_DIR = "src/app/templates"
STATIC_DIR = "src/app/static"

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Create ANSI to HTML converter (reuse instance for performance)
ansi_converter = Ansi2HTMLConverter(inline=True, scheme=ANSI_COLOR_SCHEME)


def strip_ansi(text: str | None) -> str | Markup:
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
        logger.error(f"Error in strip_ansi: {e}, type: {type(text)}, value: {repr(text)[:100]}")
        return str(text) if text is not None else ""


templates.env.filters['strip_ansi'] = strip_ansi

# Static files (for future use)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include routers
app.include_router(sessions_router)
app.include_router(history_router)
app.include_router(streaming_router)
