"""Verify the two distributions keep their dependency sets isolated."""
import importlib.metadata as metadata
import re


def _dist_names(distribution: str) -> list[str]:
    """Return the lowercased distribution names required by ``distribution``."""
    requires = metadata.requires(distribution) or []
    names = []
    for spec in requires:
        match = re.match(r"[A-Za-z0-9._-]+", spec)
        if match:
            names.append(match.group(0).lower())
    return names


def test_plugin_requires_only_pytest() -> None:
    assert _dist_names("pytest-webreportlog") == ["pytest"]


def test_server_does_not_require_pytest() -> None:
    server_deps = _dist_names("webreportlog-server")
    assert "pytest" not in server_deps
    assert "pytest-reportlog" not in server_deps
    # Sanity: it does still require its web stack.
    assert "fastapi" in server_deps
