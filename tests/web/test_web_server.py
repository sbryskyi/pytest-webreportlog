"""Tests for web server API and JSONL parsing."""
import requests


def test_server_is_running(api_client):
    """Test that server starts and responds."""
    html = api_client.get_index_html()
    assert "pytest-webreportlog" in html


def test_upload_simple_passing(api_client, simple_passing_jsonl):
    """Test uploading a simple passing test."""
    result = api_client.upload_jsonl(simple_passing_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 0


def test_upload_mixed_outcomes(api_client, mixed_outcomes_jsonl):
    """Test uploading tests with mixed outcomes."""
    result = api_client.upload_jsonl(mixed_outcomes_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 3
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert result["skipped"] == 1
    assert result["errors"] == 0


def test_upload_setup_teardown_errors(api_client, setup_teardown_errors_jsonl):
    """Test uploading tests with setup/teardown errors."""
    result = api_client.upload_jsonl(setup_teardown_errors_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 2
    assert result["passed"] == 1  # test_teardown_error call phase passed
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 2  # 1 setup error + 1 teardown error


def test_session_api_data(api_client, mixed_outcomes_jsonl):
    """Test session API returns correct data."""
    upload_result = api_client.upload_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    session = api_client.get_session(session_id)

    assert session["id"] == session_id
    assert session["pytest_version"] == "8.4.2"
    assert session["exitstatus"] == 1
    assert session["total_tests"] == 3
    assert session["passed"] == 1
    assert session["failed"] == 1
    assert session["skipped"] == 1


def test_sessions_list_api(api_client, simple_passing_jsonl, mixed_outcomes_jsonl):
    """Test sessions list API."""
    # Upload two sessions
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    sessions = api_client.get_sessions()

    assert len(sessions) >= 2
    # Most recent first
    assert sessions[0]["id"] > sessions[1]["id"]


def test_session_html_contains_test_names(api_client, mixed_outcomes_jsonl):
    """Test session HTML contains test names."""
    upload_result = api_client.upload_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    assert "test_sample.py::test_pass" in html
    assert "test_sample.py::test_fail" in html
    assert "test_sample.py::test_skip" in html


def test_session_html_result_labels(api_client, mixed_outcomes_jsonl):
    """Test session HTML shows correct result labels."""
    upload_result = api_client.upload_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Check for result badges
    assert "PASS" in html
    assert "FAIL" in html
    assert "SKIP" in html


def test_session_html_traceback_formatted(api_client, mixed_outcomes_jsonl):
    """Test that tracebacks are properly formatted."""
    upload_result = api_client.upload_jsonl(mixed_outcomes_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Check traceback is present and formatted
    assert "Traceback" in html
    assert "def test_fail():" in html
    assert "&gt;   assert False" in html  # HTML escaped
    assert "AssertionError: test failed" in html


def test_session_html_separate_setup_error(api_client, setup_teardown_errors_jsonl):
    """Test that setup errors appear as separate entries."""
    upload_result = api_client.upload_jsonl(setup_teardown_errors_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should have separate entry for setup error
    assert "test_sample.py::test_setup_error::setup" in html
    assert "ERROR" in html
    assert "Setup failed" in html


def test_session_html_separate_teardown_error(api_client, setup_teardown_errors_jsonl):
    """Test that teardown errors appear as separate entries."""
    upload_result = api_client.upload_jsonl(setup_teardown_errors_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should have TWO entries for test_teardown_error
    # 1. Main test (PASS)
    # 2. Teardown error (ERROR)
    assert "test_sample.py::test_teardown_error::teardown" in html
    assert html.count("test_teardown_error") >= 2  # Appears in both entries


def test_session_html_statistics_summary(api_client, mixed_outcomes_jsonl):
    """Test session summary statistics display."""
    upload_result = api_client.upload_jsonl(mixed_outcomes_jsonl)
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


def test_index_shows_sessions(api_client, simple_passing_jsonl, mixed_outcomes_jsonl):
    """Test index page shows uploaded sessions."""
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    html = api_client.get_index_html()

    assert "Test Sessions" in html
    assert "8.4.2" in html  # pytest version
    assert "passed" in html.lower()


def test_upload_invalid_file(api_client):
    """Test uploading non-JSONL file returns error."""
    files = {"file": ("test.txt", "not jsonl", "text/plain")}
    response = requests.post(f"{api_client.base_url}/upload", files=files)

    assert response.status_code == 400


def test_upload_xfail(api_client, xfail_jsonl):
    """Test uploading xfail test."""
    result = api_client.upload_jsonl(xfail_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
    # xfail tests have separate xfailed category (like pytest-html)
    assert result["xfailed"] == 1
    assert result["passed"] == 0
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["xpassed"] == 0
    assert result["errors"] == 0


def test_upload_xpass(api_client, xpass_jsonl):
    """Test uploading xpass test."""
    result = api_client.upload_jsonl(xpass_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
    # xpass tests have separate xpassed category (like pytest-html)
    assert result["xpassed"] == 1
    assert result["passed"] == 0
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["xfailed"] == 0
    assert result["errors"] == 0


def test_upload_xfail_xpass_mixed(api_client, xfail_xpass_mixed_jsonl):
    """Test uploading mix of xfail, xpass, and normal tests."""
    result = api_client.upload_jsonl(xfail_xpass_mixed_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 3
    # Separate categories like pytest-html: 1 xfailed, 1 xpassed, 1 normal pass
    assert result["passed"] == 1  # normal pass only
    assert result["xfailed"] == 1  # expected failure
    assert result["xpassed"] == 1  # unexpected pass
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 0


def test_session_html_xfail_indicator(api_client, xfail_jsonl):
    """Test that xfail tests are displayed with appropriate indicator."""
    upload_result = api_client.upload_jsonl(xfail_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should contain test name
    assert "test_sample.py::test_xfail" in html
    # Should show XFAIL label
    assert "XFAIL" in html


def test_session_html_xpass_indicator(api_client, xpass_jsonl):
    """Test that xpass tests are displayed with appropriate indicator."""
    upload_result = api_client.upload_jsonl(xpass_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should contain test name
    assert "test_sample.py::test_xpass" in html
    # Should show XPASS label
    assert "XPASS" in html


def test_session_html_xfail_xpass_mixed_display(api_client, xfail_xpass_mixed_jsonl):
    """Test HTML display of mixed xfail/xpass session."""
    upload_result = api_client.upload_jsonl(xfail_xpass_mixed_jsonl)
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


def test_session_html_shows_phase_subsections(api_client, simple_passing_jsonl):
    """Test that HTML shows individual subsections for setup/call/teardown."""
    upload_result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should show phase names (phases without content are plain divs, not details)
    assert ">setup<" in html
    assert ">call<" in html
    assert ">teardown<" in html


def test_session_html_shows_phase_durations(api_client, simple_passing_jsonl):
    """Test that HTML shows duration for each phase."""
    upload_result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = upload_result["session_id"]

    html = api_client.get_session_html(session_id)

    # Each phase section should have a duration displayed
    # The JSONL fixture has durations: setup=0.001s, call=0.002s, teardown=0.001s
    assert "0.001" in html  # setup duration
    assert "0.002" in html  # call duration


def test_session_html_phase_output_isolation(api_client):
    """Test that each phase subsection shows only its own output."""
    # Create JSONL with output in all phases
    jsonl_with_phase_output = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_with_output", "location": ["test_sample.py", 1, "test_with_output"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [["Captured stdout setup", "Setup output"]], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_with_output", "location": ["test_sample.py", 1, "test_with_output"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [["Captured stdout call", "Call output"]], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_with_output", "location": ["test_sample.py", 1, "test_with_output"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [["Captured stdout teardown", "Teardown output"]], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""

    upload_result = api_client.upload_jsonl(jsonl_with_phase_output)
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
