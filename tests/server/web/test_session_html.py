"""Tests for session HTML rendering: test names, labels, tracebacks, statistics."""
from .conftest import APIClient


def test_session_html_contains_test_names(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test session HTML contains test names."""
    upload_result = api_client.stream_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    assert "test_sample.py::test_pass" in html
    assert "test_sample.py::test_fail" in html
    assert "test_sample.py::test_skip" in html


def test_session_html_result_labels(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test session HTML shows correct result labels."""
    upload_result = api_client.stream_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Check for result badges
    assert "PASS" in html
    assert "FAIL" in html
    assert "SKIP" in html


def test_session_html_traceback_formatted(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test that tracebacks are properly formatted."""
    upload_result = api_client.stream_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Check traceback is present and formatted
    assert "Traceback" in html
    assert "def test_fail():" in html
    assert "&gt;   assert False" in html  # HTML escaped
    assert "AssertionError: test failed" in html


def test_session_html_separate_setup_error(
    api_client: APIClient, setup_teardown_errors_jsonl: str
) -> None:
    """Test that setup errors appear as separate entries."""
    upload_result = api_client.stream_jsonl(setup_teardown_errors_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should have separate entry for setup error
    assert "test_sample.py::test_setup_error::setup" in html
    assert "ERROR" in html
    assert "Setup failed" in html


def test_session_html_separate_teardown_error(
    api_client: APIClient, setup_teardown_errors_jsonl: str
) -> None:
    """Test that teardown errors appear as separate entries."""
    upload_result = api_client.stream_jsonl(setup_teardown_errors_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should have TWO entries for test_teardown_error
    # 1. Main test (PASS)
    # 2. Teardown error (ERROR)
    assert "test_sample.py::test_teardown_error::teardown" in html
    assert html.count("test_teardown_error") >= 2  # Appears in both entries


def test_session_html_statistics_summary(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test session summary statistics display."""
    upload_result = api_client.stream_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Check summary cards
    assert "Total" in html
    assert ">3<" in html  # 3 total tests
    assert "Passed" in html
    assert ">1<" in html  # 1 passed
    assert "Failed" in html
    # assert ">1<" already checked
    assert "Skipped" in html


def test_session_html_xfail_indicator(api_client: APIClient, xfail_jsonl: str) -> None:
    """Test that xfail tests are displayed with appropriate indicator."""
    upload_result = api_client.stream_jsonl(xfail_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should contain test name
    assert "test_sample.py::test_xfail" in html
    # Should show XFAIL label
    assert "XFAIL" in html


def test_session_html_xpass_indicator(api_client: APIClient, xpass_jsonl: str) -> None:
    """Test that xpass tests are displayed with appropriate indicator."""
    upload_result = api_client.stream_jsonl(xpass_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should contain test name
    assert "test_sample.py::test_xpass" in html
    # Should show XPASS label
    assert "XPASS" in html


def test_session_html_xfail_xpass_mixed_display(
    api_client: APIClient, xfail_xpass_mixed_jsonl: str
) -> None:
    """Test HTML display of mixed xfail/xpass session."""
    upload_result = api_client.stream_jsonl(xfail_xpass_mixed_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should contain all test names
    assert "test_sample.py::test_xfail_one" in html
    assert "test_sample.py::test_xpass_one" in html
    assert "test_sample.py::test_normal_pass" in html

    # Should have XFAIL, XPASS, and PASS labels
    assert "XFAIL" in html
    assert "XPASS" in html
    assert "PASS" in html


def test_session_html_shows_phase_subsections(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test that HTML shows individual subsections for setup/call/teardown."""
    upload_result = api_client.stream_jsonl(simple_passing_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should show phase names (phases without content are plain divs, not details)
    assert ">setup<" in html
    assert ">call<" in html
    assert ">teardown<" in html


def test_session_html_shows_phase_durations(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test that HTML shows duration for each phase."""
    upload_result = api_client.stream_jsonl(simple_passing_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Each phase section should have a duration displayed
    # The JSONL fixture has durations: setup=0.001s, call=0.002s, teardown=0.001s
    assert "0.001" in html  # setup duration
    assert "0.002" in html  # call duration


def test_session_html_phase_output_isolation(api_client: APIClient) -> None:
    """Test that each phase subsection shows only its own output."""
    # Create JSONL with output in all phases
    jsonl_with_phase_output = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_with_output", "location": ["test_sample.py", 1, "test_with_output"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [["Captured stdout setup", "Setup output"]], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_with_output", "location": ["test_sample.py", 1, "test_with_output"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [["Captured stdout call", "Call output"]], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_with_output", "location": ["test_sample.py", 1, "test_with_output"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [["Captured stdout teardown", "Teardown output"]], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""

    upload_result = api_client.stream_jsonl(jsonl_with_phase_output)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should contain output from all phases
    assert "Setup output" in html
    assert "Call output" in html
    assert "Teardown output" in html

    # Should have Captured Output sections
    assert "Captured stdout setup" in html
    assert "Captured stdout call" in html
    assert "Captured stdout teardown" in html
