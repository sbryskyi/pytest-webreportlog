"""Formatters for pytest report data."""


def format_longrepr(longrepr) -> str | None:
    """Format longrepr from JSONL into readable traceback text.

    Args:
        longrepr: The longrepr field from pytest-reportlog JSONL

    Returns:
        Formatted traceback string or None if no error
    """
    if not longrepr:
        return None

    if isinstance(longrepr, str):
        return longrepr

    # longrepr is a dict with reprtraceback structure
    lines = []

    # Extract traceback entries
    reprtraceback = longrepr.get("reprtraceback")
    if reprtraceback and "reprentries" in reprtraceback:
        for entry in reprtraceback["reprentries"]:
            if entry.get("type") == "ReprEntry":
                data = entry.get("data", {})

                # Add the code lines from this traceback entry
                entry_lines = data.get("lines", [])
                if entry_lines:
                    lines.extend(entry_lines)

                # Add file location if available
                reprfileloc = data.get("reprfileloc")
                if reprfileloc:
                    path = reprfileloc.get("path", "")
                    lineno = reprfileloc.get("lineno", "")
                    message = reprfileloc.get("message", "")
                    if path and lineno:
                        lines.append(f"\n{path}:{lineno}: {message}")

    # If we got traceback lines, join them
    if lines:
        return "\n".join(lines)

    # Fallback: try to get crash message
    reprcrash = longrepr.get("reprcrash")
    if reprcrash:
        message = reprcrash.get("message", "")
        path = reprcrash.get("path", "")
        lineno = reprcrash.get("lineno", "")
        if message:
            if path and lineno:
                return f"{path}:{lineno}\n{message}"
            return message

    # Last resort: convert to string
    return str(longrepr)
