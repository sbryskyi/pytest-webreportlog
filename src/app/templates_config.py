"""Jinja2 templates configuration and custom filters."""
import logging
from pathlib import Path

from ansi2html import Ansi2HTMLConverter
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

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
        logger.error(f"Error in ansi_to_html: {e}, type: {type(text)}, value: {repr(text)[:100]}")
        return str(text) if text is not None else ""


templates.env.filters["ansi_to_html"] = ansi_to_html
