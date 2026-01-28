"""Tests comparing web server output with pytest-html reports."""
import json
import re
import subprocess
from pathlib import Path

import pytest

from .conftest import APIClient


def run_pytest_and_upload(
    api_client: APIClient, tmp_path: Path, test_path: str
) -> tuple[int, str, Path]:
    """Helper to run pytest and upload results to server.

    Args:
        api_client: API client fixture
        tmp_path: Temporary directory path
        test_path: Path to test file to run

    Returns:
        Tuple of (session_id, our_html, pytest_html_path)
    """
    jsonl_path = tmp_path / "report.jsonl"
    html_path = tmp_path / "pytest.html"

    # Run pytest with both JSONL and HTML reports
    subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            test_path,
            f"--report-log={jsonl_path}",
            f"--html={html_path}",
            "--self-contained-html",
            "-q",
        ],
        cwd=Path.cwd(),
    )

    # Upload JSONL to our server
    with open(jsonl_path) as f:
        jsonl_content = f.read()
    upload_result = api_client.upload_jsonl(jsonl_content)
    session_id = upload_result["session_id"]

    # Get our HTML
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
    session_id, our_html, html_path = run_pytest_and_upload(
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
def test_compare_teardown_error_handling(
    api_client: APIClient, tmp_path: Path
) -> None:
    """Verify we handle teardown errors same as pytest-html.

    When test passes but teardown fails:
    - pytest-html shows: test (Passed) + test::teardown (Error)
    - We should show the same
    """
    session_id, our_html, _ = run_pytest_and_upload(
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
def test_session_statistics_match_pytest(
    api_client: APIClient, tmp_path: Path
) -> None:
    """Verify session statistics match pytest's output."""
    jsonl_path = tmp_path / "report.jsonl"

    # Run pytest and capture output
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "test_sample/test_exceptions.py",
            f"--report-log={jsonl_path}",
            "-v",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
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

    # Upload to our server
    with open(jsonl_path) as f:
        upload_result = api_client.upload_jsonl(f.read())

    # Compare statistics
    assert upload_result["passed"] == pytest_summary.get("passed", 0)
    assert upload_result["failed"] == pytest_summary.get("failed", 0)
    assert upload_result["errors"] == pytest_summary.get("errors", 0)


def test_traceback_formatting_matches_structure(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Verify tracebacks have proper structure."""
    upload_result = api_client.upload_jsonl(mixed_outcomes_jsonl)
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
    upload_result = api_client.upload_jsonl(setup_teardown_errors_jsonl)
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
    upload_result = api_client.upload_jsonl(mixed_outcomes_jsonl)
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
    session_id, our_html, html_path = run_pytest_and_upload(
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
    jsonl_path = tmp_path / "report.jsonl"

    # Run pytest and capture output
    result = subprocess.run(
        [
            "uv",
            "run",
            "pytest",
            "test_sample/test_xfail_xpass.py",
            f"--report-log={jsonl_path}",
            "-v",
        ],
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
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

    # Upload to our server
    with open(jsonl_path) as f:
        upload_result = api_client.upload_jsonl(f.read())

    # Match pytest-html behavior: xfailed and xpassed are separate categories
    assert upload_result["passed"] == pytest_summary.get("passed", 0)
    assert upload_result["xfailed"] == pytest_summary.get("xfailed", 0)
    assert upload_result["xpassed"] == pytest_summary.get("xpassed", 0)
