"""Tests for HTML report generation - format-specific tests only.

Common cross-format tests (exceptions, logs, xfail) are in test_all_formats.py.
"""
from pytest import Pytester

from .report_utils import (
    html_contains_text,
    parse_html_report,
)


def test_html_generates_file(
    html_config: Pytester, simple_test_content: Pytester
) -> None:
    """Test that pytest-html generates an HTML report file."""
    result = html_config.runpytest()
    result.assert_outcomes(passed=1)

    html_file = html_config.path / "report.html"
    assert html_file.exists(), "HTML report file should be created"


def test_html_is_self_contained(
    html_config: Pytester, simple_test_content: Pytester
) -> None:
    """Test that HTML report is self-contained (no external dependencies)."""
    result = html_config.runpytest()
    result.assert_outcomes(passed=1)

    html_content = parse_html_report(html_config.path / "report.html")

    # Self-contained HTML should have CSS and JS embedded (not external references)
    # Modern pytest-html uses inline styles and scripts
    assert "<style>" in html_content or "style=" in html_content or "<script>" in html_content
    # File should be reasonably large if self-contained (has inline assets)
    assert len(html_content) > 1000, "Self-contained HTML should be substantial in size"


def test_html_contains_test_names(
    html_config: Pytester, multiple_test_content: Pytester
) -> None:
    """Test that HTML report contains test names."""
    result = html_config.runpytest()
    result.assert_outcomes(passed=2)

    html_content = parse_html_report(html_config.path / "report.html")

    assert html_contains_text(html_content, "test_one")
    assert html_contains_text(html_content, "test_two")


def test_html_shows_passed_tests(
    html_config: Pytester, simple_test_content: Pytester
) -> None:
    """Test that HTML report shows passed test status."""
    result = html_config.runpytest()
    result.assert_outcomes(passed=1)

    html_content = parse_html_report(html_config.path / "report.html")

    # Should contain indication of passed tests
    assert html_contains_text(html_content, "test_pass")
    # Common indicators for passed tests
    assert ("passed" in html_content.lower() or
            "success" in html_content.lower() or
            "✓" in html_content or
            "✔" in html_content)


def test_html_summary_section(
    html_config: Pytester, multiple_test_content: Pytester
) -> None:
    """Test that HTML report contains a summary section."""
    result = html_config.runpytest()
    result.assert_outcomes(passed=2)

    html_content = parse_html_report(html_config.path / "report.html")

    # Should contain some form of summary
    assert "2" in html_content  # Number of tests
    # Common summary indicators
    assert any(word in html_content.lower() for word in ["summary", "results", "report"])
