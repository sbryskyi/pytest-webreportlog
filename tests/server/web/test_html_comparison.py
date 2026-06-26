"""Tests comparing web server output with pytest-html reports."""

import json
import re
import subprocess
from pathlib import Path

import pytest

from .conftest import APIClient


def _run_pytest_streaming(
    api_client: APIClient,
    test_path: str,
    html_path: Path | None = None,
) -> tuple[subprocess.CompletedProcess, int]:
    """Run pytest with the webreportlog plugin streaming to the test server.

    Returns the completed process and the id of the freshly-created session.
    """
    before = {s["id"] for s in api_client.get_sessions()}

    cmd = [
        "uv",
        "run",
        "pytest",
        test_path,
        f"--webreportlog-url={api_client.base_url}",
        # Ignore test_sample's own addopts; keep only importlib mode.
        "-o",
        "addopts=--import-mode=importlib",
        "-q",
    ]
    if html_path is not None:
        cmd += [f"--html={html_path}", "--self-contained-html"]

    result = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True, text=True)

    new_ids = [s["id"] for s in api_client.get_sessions() if s["id"] not in before]
    assert new_ids, (
        "Plugin did not create a session.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result, max(new_ids)


def run_pytest_and_stream(
    api_client: APIClient, tmp_path: Path, test_path: str
) -> tuple[int, str, Path]:
    """Run pytest (streaming to the server) plus a pytest-html report.

    Returns (session_id, our_html, pytest_html_path).
    """
    html_path = tmp_path / "pytest.html"
    _, session_id = _run_pytest_streaming(api_client, test_path, html_path=html_path)
    our_html = api_client.get_session_html(session_id)
    return session_id, our_html, html_path


def parse_pytest_html_data(html_content: str) -> dict:
    """Extract data from pytest-html report.

    pytest-html embeds test data in a JSON blob in the HTML.
    """
    # Find the data-jsonblob attribute
    match = re.search(r'data-jsonblob="([^"]+)"', html_content)
    if not match:
        return {}

    # Decode HTML entities and parse JSON
    json_str = match.group(1)
    json_str = json_str.replace("&#34;", '"')
    json_str = json_str.replace("&amp;quot;", '"')
    json_str = json_str.replace("&gt;", ">")
    json_str = json_str.replace("&lt;", "<")

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return {}


def extract_test_results_from_pytest_html(html_content: str) -> dict[str, str]:
    """Extract test results from pytest-html.

    Returns dict mapping test IDs to their outcomes.
    """
    data = parse_pytest_html_data(html_content)
    tests = data.get("tests", {})

    results: dict[str, str] = {}
    for test_id, test_entries in tests.items():
        for entry in test_entries:
            result = entry.get("result", "")
            entry_test_id = entry.get("testId", test_id)
            results[entry_test_id] = result

    return results


def extract_our_test_results(html_content: str) -> dict[str, str]:
    """Extract test results from our web server HTML.

    Returns dict mapping test names to their result labels.
    """
    results: dict[str, str] = {}

    # Find all test entries with their result badges
    # Pattern: badge with PASS/FAIL/ERROR/SKIP followed by test name
    pattern = r'(PASS|FAIL|SKIP|ERROR)</span>.*?<p class="text-sm font-medium text-gray-900">([^<]+)</p>'
    matches = re.findall(pattern, html_content, re.DOTALL)

    for result, test_name in matches:
        results[test_name] = result

    return results


def count_results(results: dict[str, str]) -> dict[str, int]:
    """Count result types from results dict."""
    counts = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

    for result in results.values():
        result_lower = result.lower()
        if result_lower == "passed" or result_lower == "pass":
            counts["passed"] += 1
        elif result_lower == "failed" or result_lower == "fail":
            counts["failed"] += 1
        elif result_lower == "skipped" or result_lower == "skip":
            counts["skipped"] += 1
        elif result_lower == "error":
            counts["errors"] += 1

    return counts


@pytest.mark.skipif(
    not (Path("test_sample") / "test_exceptions.py").exists(),
    reason="Requires test_sample directory",
)
def test_compare_with_pytest_html_exceptions(
    api_client: APIClient, tmp_path: Path
) -> None:
    """Compare our output with pytest-html for exception tests."""
    session_id, our_html, html_path = run_pytest_and_stream(
        api_client, tmp_path, "test_sample/test_exceptions.py"
    )

    # Get pytest-html
    with open(html_path) as f:
        pytest_html = f.read()

    # Extract and compare results
    pytest_results = extract_test_results_from_pytest_html(pytest_html)
    our_results = extract_our_test_results(our_html)

    pytest_counts = count_results(pytest_results)
    our_counts = count_results(our_results)

    # Our counts should match pytest-html
    assert our_counts["passed"] == pytest_counts["passed"]
    assert our_counts["failed"] == pytest_counts["failed"]
    assert our_counts["skipped"] == pytest_counts["skipped"]
    assert our_counts["errors"] == pytest_counts["errors"]


@pytest.mark.skipif(
    not (Path("test_sample") / "test_exceptions.py").exists(),
    reason="Requires test_sample directory",
)
def test_compare_teardown_error_handling(api_client: APIClient, tmp_path: Path) -> None:
    """Verify we handle teardown errors same as pytest-html.

    When test passes but teardown fails:
    - pytest-html shows: test (Passed) + test::teardown (Error)
    - We should show the same
    """
    session_id, our_html, _ = run_pytest_and_stream(
        api_client,
        tmp_path,
        "test_sample/test_exceptions.py::test_with_teardown_exception",
    )

    # Check we have both entries
    assert "test_with_teardown_exception::teardown" in our_html
    assert "ERROR" in our_html
    assert "PASS" in our_html

    # Verify statistics
    session = api_client.get_session(session_id)
    assert session["passed"] == 1  # Test itself passed
    assert session["errors"] == 1  # Teardown error


@pytest.mark.skipif(
    not (Path("test_sample") / "test_exceptions.py").exists(),
    reason="Requires test_sample directory",
)
def test_session_statistics_match_pytest(api_client: APIClient, tmp_path: Path) -> None:
    """Verify session statistics match pytest's output."""
    result, session_id = _run_pytest_streaming(
        api_client, "test_sample/test_exceptions.py"
    )

    # Parse pytest output for counts (Format: "2 failed, 1 passed, 3 errors")
    pytest_summary: dict[str, int] = {}
    for key, pattern in [
        ("passed", r"(\d+) passed"),
        ("failed", r"(\d+) failed"),
        ("errors", r"(\d+) error"),
    ]:
        match = re.search(pattern, result.stdout)
        if match:
            pytest_summary[key] = int(match.group(1))

    # Compare with the session the plugin streamed
    session = api_client.get_session(session_id)
    assert session["passed"] == pytest_summary.get("passed", 0)
    assert session["failed"] == pytest_summary.get("failed", 0)
    assert session["errors"] == pytest_summary.get("errors", 0)


def test_traceback_formatting_matches_structure(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Verify tracebacks have proper structure."""
    upload_result = api_client.stream_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should have formatted traceback
    assert "<pre" in html
    assert "font-mono" in html  # Monospace font for code
    assert "def test_fail():" in html
    assert "&gt;" in html  # HTML escaped >
    assert "AssertionError" in html


def test_result_badges_use_correct_colors(
    api_client: APIClient, setup_teardown_errors_jsonl: str
) -> None:
    """Verify result badges use correct color scheme."""
    upload_result = api_client.stream_jsonl(setup_teardown_errors_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Check color classes
    # PASS = green (bg-green-100)
    # FAIL = red (bg-red-100)
    # ERROR = orange (bg-orange-100)
    # SKIP = yellow (bg-yellow-100)

    # Should have orange badges for errors
    assert "bg-orange-100" in html
    # Should have green badges for passed
    assert "bg-green-100" in html


def test_collapsed_sections_expandable(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Verify test entries are collapsible/expandable."""
    upload_result = api_client.stream_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should use <details> for collapsible sections
    assert "<details" in html
    assert "<summary" in html
    # Rotation on expand
    assert "group-open:rotate-90" in html


@pytest.mark.skipif(
    not (Path("test_sample") / "test_xfail_xpass.py").exists(),
    reason="Requires test_sample directory",
)
def test_compare_xfail_xpass_with_pytest_html(
    api_client: APIClient, tmp_path: Path
) -> None:
    """Compare our handling of xfail/xpass with pytest-html."""
    session_id, our_html, html_path = run_pytest_and_stream(
        api_client, tmp_path, "test_sample/test_xfail_xpass.py"
    )

    # Get pytest-html
    with open(html_path) as f:
        pytest_html = f.read()

    # Extract and compare results
    pytest_results = extract_test_results_from_pytest_html(pytest_html)
    our_results = extract_our_test_results(our_html)

    pytest_counts = count_results(pytest_results)
    our_counts = count_results(our_results)

    # Our counts should match pytest-html
    # xfail shows as skipped, xpass shows as passed
    assert our_counts["passed"] >= pytest_counts["passed"]
    assert our_counts["skipped"] >= pytest_counts["skipped"]


@pytest.mark.skipif(
    not (Path("test_sample") / "test_xfail_xpass.py").exists(),
    reason="Requires test_sample directory",
)
def test_xfail_xpass_statistics_match_pytest(
    api_client: APIClient, tmp_path: Path
) -> None:
    """Verify xfail/xpass statistics match pytest output."""
    result, session_id = _run_pytest_streaming(
        api_client, "test_sample/test_xfail_xpass.py"
    )

    # Parse pytest output for counts
    pytest_summary: dict[str, int] = {}
    for key, pattern in [
        ("passed", r"(\d+) passed"),
        ("xfailed", r"(\d+) xfailed"),
        ("xpassed", r"(\d+) xpassed"),
    ]:
        match = re.search(pattern, result.stdout)
        if match:
            pytest_summary[key] = int(match.group(1))

    # Match pytest-html behavior: xfailed and xpassed are separate categories
    session = api_client.get_session(session_id)
    assert session["passed"] == pytest_summary.get("passed", 0)
    assert session["xfailed"] == pytest_summary.get("xfailed", 0)
    assert session["xpassed"] == pytest_summary.get("xpassed", 0)
