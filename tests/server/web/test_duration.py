"""Tests for duration calculation and display."""
from .conftest import APIClient


def test_session_duration_calculated(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test that session duration is calculated correctly."""
    result = api_client.stream_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    session = api_client.get_session(session_id)

    # Duration should be calculated from start/stop timestamps
    assert "duration" in session
    assert session["duration"] > 0


def test_session_html_displays_duration(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test that session detail page displays duration."""
    result = api_client.stream_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should display duration with units
    assert "Duration:" in html
    assert "s" in html  # seconds unit


def test_test_phase_durations_displayed(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test that individual phase durations are displayed."""
    result = api_client.stream_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should show duration for each phase
    # The fixture has: setup=0.001s, call=0.002s, teardown=0.001s
    assert "0.001" in html
    assert "0.002" in html


def test_duration_with_zero_values(api_client: APIClient) -> None:
    """Test duration handling with zero duration."""
    jsonl_zero_duration = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_instant", "location": ["test_sample.py", 1, "test_instant"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.0, "start": 1000.0, "stop": 1000.0, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_instant", "location": ["test_sample.py", 1, "test_instant"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.0, "start": 1000.0, "stop": 1000.0, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_instant", "location": ["test_sample.py", 1, "test_instant"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.0, "start": 1000.0, "stop": 1000.0, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""

    result = api_client.stream_jsonl(jsonl_zero_duration)

    assert result["status"] == "success"
    assert result["total_tests"] == 1


def test_duration_aggregation_in_history(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test duration aggregation in test history."""
    # Upload same test multiple times
    api_client.stream_jsonl(simple_passing_jsonl)
    api_client.stream_jsonl(simple_passing_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_pass"
    )
    html = response.text

    # Should show average durations
    assert "Avg" in html
    assert "Duration" in html
