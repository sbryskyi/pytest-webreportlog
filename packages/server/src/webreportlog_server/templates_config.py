"""Jinja2 templates configuration and custom filters."""

import logging
from pathlib import Path

from ansi2html import Ansi2HTMLConverter
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from .database import get_configured_max_bytes, get_database_size_bytes
from .utils import format_size, scalar_env_facets

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_ANSI_COLOR_SCHEME = "xterm"

templates = Jinja2Templates(directory=_TEMPLATES_DIR)
_ansi_converter = Ansi2HTMLConverter(inline=True, scheme=_ANSI_COLOR_SCHEME)


def ansi_to_html(text: str | None) -> str | Markup:
    """Convert ANSI color codes to inline-styled HTML."""
    try:
        if text is None:
            return ""
        if not isinstance(text, str):
            text = str(text)
        html = _ansi_converter.convert(text, full=False)
        return Markup(html)
    except Exception as e:
        logger.error(
            f"Error in ansi_to_html: {e}, type: {type(text)}, value: {repr(text)[:100]}"
        )
        return str(text) if text is not None else ""


templates.env.filters["ansi_to_html"] = ansi_to_html


def database_size() -> str:
    """Human-readable current database size, recomputed on each render."""
    return format_size(get_database_size_bytes())


def _configured_cap() -> int | None:
    try:
        return get_configured_max_bytes()
    except ValueError:
        return None  # misconfigured cap shouldn't break rendering


def database_cap() -> str | None:
    """Human-readable size cap, or None when no cap is configured."""
    cap = _configured_cap()
    return format_size(cap) if cap is not None else None


def database_over_cap() -> bool:
    """True when the current database size exceeds the configured cap."""
    cap = _configured_cap()
    size = get_database_size_bytes()
    return size is not None and cap is not None and size > cap


# Palette for facet/attribute filter chips. Deliberately avoids the outcome
# colours (green/red/yellow/blue/orange/amber/rose) so a filter chip never reads
# as a pass/fail status. A stable hash maps each string to a fixed colour.
_FACET_PALETTE = (
    "purple",
    "teal",
    "cyan",
    "indigo",
    "violet",
    "fuchsia",
    "pink",
    "lime",
)


def facet_color(value: str) -> str:
    """Return Tailwind badge classes for a string (stable across processes)."""
    if not value:
        return "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300"
    # sum(ord) is stable, unlike the builtin hash().
    color = _FACET_PALETTE[sum(ord(c) for c in value) % len(_FACET_PALETTE)]
    return (
        f"bg-{color}-100 dark:bg-{color}-900/50 text-{color}-800 dark:text-{color}-300"
    )


templates.env.globals["database_size"] = database_size
templates.env.globals["database_cap"] = database_cap
templates.env.globals["database_over_cap"] = database_over_cap
templates.env.globals["facet_color"] = facet_color
templates.env.globals["scalar_env_facets"] = scalar_env_facets
