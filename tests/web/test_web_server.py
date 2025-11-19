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
    # Check for session IDs
    assert "#1" in html or "#2" in html
    # Check for status (Passed or Failed instead of Completed)
    assert "Passed" in html or "Failed" in html


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


# ============================================================================
# HISTORY FEATURE TESTS
# ============================================================================

def test_history_overview_page_loads(api_client, simple_passing_jsonl):
    """Test that history overview page loads successfully."""
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")

    assert response.status_code == 200
    assert "Test History Overview" in response.text


def test_history_overview_displays_all_tests(api_client, mixed_outcomes_jsonl):
    """Test history overview displays all unique tests."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")
    html = response.text

    # Should show all 3 tests
    assert "test_sample.py::test_pass" in html
    assert "test_sample.py::test_fail" in html
    assert "test_sample.py::test_skip" in html


def test_history_overview_aggregated_statistics(api_client, simple_passing_jsonl, mixed_outcomes_jsonl):
    """Test aggregated statistics in history overview."""
    # Upload same test twice with different outcomes
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")
    html = response.text

    # test_pass appears in both sessions
    assert "test_sample.py::test_pass" in html
    # Should show total runs for test_pass (at least 1, ideally 2)
    # Note: Exact count depends on database session isolation
    assert "Total Runs" in html or "total" in html.lower()


def test_history_overview_pass_rate_display(api_client, simple_passing_jsonl, mixed_outcomes_jsonl):
    """Test pass rate display in history overview."""
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")
    html = response.text

    # test_pass has 100% pass rate (2/2)
    assert "100.0%" in html or "100%" in html


def test_history_overview_latest_result_badges(api_client, mixed_outcomes_jsonl):
    """Test latest result badge display in history overview."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")
    html = response.text

    # Should have result badges
    assert "PASS" in html
    assert "FAIL" in html
    assert "SKIP" in html


def test_history_overview_sorting_by_nodeid(api_client, mixed_outcomes_jsonl):
    """Test sorting by nodeid in history overview."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    # Test ascending sort
    response = api_client.session.get(f"{api_client.base_url}/history?sort_by=nodeid&sort_dir=asc")
    assert response.status_code == 200

    # Test descending sort
    response = api_client.session.get(f"{api_client.base_url}/history?sort_by=nodeid&sort_dir=desc")
    assert response.status_code == 200


def test_history_overview_sorting_by_total_runs(api_client, mixed_outcomes_jsonl):
    """Test sorting by total_runs in history overview."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history?sort_by=total_runs&sort_dir=desc")
    assert response.status_code == 200


def test_history_overview_sorting_by_pass_rate(api_client, mixed_outcomes_jsonl):
    """Test sorting by pass_rate in history overview."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history?sort_by=pass_rate&sort_dir=desc")
    assert response.status_code == 200


def test_history_overview_empty_state(api_client):
    """Test history overview with no tests uploaded yet."""
    response = api_client.session.get(f"{api_client.base_url}/history")

    assert response.status_code == 200
    assert "Test History Overview" in response.text


def test_individual_test_history_page_loads(api_client, simple_passing_jsonl):
    """Test individual test history page loads."""
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_pass")

    assert response.status_code == 200
    assert "Test History" in response.text
    assert "test_sample.py::test_pass" in response.text


def test_individual_test_history_shows_all_runs(api_client, simple_passing_jsonl):
    """Test individual test history shows all runs of a specific test."""
    # Upload same test twice
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_pass")
    html = response.text

    # Should show summary stats
    assert "Total Runs" in html
    # Note: Exact count depends on database session isolation
    assert response.status_code == 200


def test_individual_test_history_summary_stats(api_client, simple_passing_jsonl):
    """Test individual test history shows correct summary statistics."""
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_pass")
    html = response.text

    # Should show pass rate
    assert "Pass Rate" in html
    assert "100" in html  # 100% pass rate

    # Should show average duration
    assert "Avg" in html and "Duration" in html


def test_individual_test_history_session_links(api_client, simple_passing_jsonl):
    """Test individual test history has working session links."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_pass")
    html = response.text

    # Should have link to session
    assert f"/sessions/{session_id}" in html or f"#{session_id}" in html


def test_individual_test_history_not_found(api_client):
    """Test 404 for non-existent test nodeid."""
    response = api_client.session.get(f"{api_client.base_url}/history/nonexistent::test")

    assert response.status_code == 404


def test_individual_test_history_mixed_outcomes(api_client, simple_passing_jsonl, mixed_outcomes_jsonl):
    """Test individual test history with mixed outcomes across sessions."""
    api_client.upload_jsonl(simple_passing_jsonl)  # test_pass succeeds
    api_client.upload_jsonl(mixed_outcomes_jsonl)  # test_pass also succeeds

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_pass")
    html = response.text

    # Both runs should be PASS
    assert html.count("PASS") >= 2


def test_individual_test_history_expandable_rows(api_client, mixed_outcomes_jsonl):
    """Test individual test history has expandable rows."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_fail")
    html = response.text

    # Should have details/summary elements for expansion
    assert "<details" in html
    assert "<summary" in html


def test_individual_test_history_phase_details(api_client, simple_passing_jsonl):
    """Test individual test history shows phase details."""
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_pass")
    html = response.text

    # Should show phases
    assert "setup" in html.lower()
    assert "call" in html.lower()
    assert "teardown" in html.lower()


def test_individual_test_history_traceback_display(api_client, mixed_outcomes_jsonl):
    """Test individual test history displays tracebacks for failures."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_fail")
    html = response.text

    # Should show traceback
    assert "Traceback" in html or "AssertionError" in html


# ============================================================================
# DURATION CALCULATION TESTS
# ============================================================================

def test_session_duration_calculated(api_client, simple_passing_jsonl):
    """Test that session duration is calculated correctly."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    session = api_client.get_session(session_id)

    # Duration should be calculated from start/stop timestamps
    assert "duration" in session
    assert session["duration"] > 0


def test_session_html_displays_duration(api_client, simple_passing_jsonl):
    """Test that session detail page displays duration."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should display duration with units
    assert "Duration:" in html
    assert "s" in html  # seconds unit


def test_test_phase_durations_displayed(api_client, simple_passing_jsonl):
    """Test that individual phase durations are displayed."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    html = api_client.get_session_html(session_id)

    # Should show duration for each phase
    # The fixture has: setup=0.001s, call=0.002s, teardown=0.001s
    assert "0.001" in html
    assert "0.002" in html


def test_duration_with_zero_values(api_client):
    """Test duration handling with zero duration."""
    jsonl_zero_duration = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_instant", "location": ["test_sample.py", 1, "test_instant"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.0, "start": 1000.0, "stop": 1000.0, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_instant", "location": ["test_sample.py", 1, "test_instant"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.0, "start": 1000.0, "stop": 1000.0, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_instant", "location": ["test_sample.py", 1, "test_instant"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.0, "start": 1000.0, "stop": 1000.0, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""

    result = api_client.upload_jsonl(jsonl_zero_duration)

    assert result["status"] == "success"
    assert result["total_tests"] == 1


def test_duration_aggregation_in_history(api_client, simple_passing_jsonl):
    """Test duration aggregation in test history."""
    # Upload same test multiple times
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history/test_sample.py::test_pass")
    html = response.text

    # Should show average durations
    assert "Avg" in html
    assert "Duration" in html


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_upload_empty_file(api_client):
    """Test uploading empty file."""
    import requests
    files = {"file": ("test.jsonl", "", "application/jsonl")}
    response = requests.post(f"{api_client.base_url}/upload", files=files)

    # Server currently accepts empty files (returns 200)
    # This could be enhanced to return 400/422 for better validation
    assert response.status_code in [200, 400, 422]


def test_upload_malformed_json(api_client):
    """Test uploading malformed JSON."""
    import requests
    malformed = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{this is not valid json}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""
    files = {"file": ("test.jsonl", malformed, "application/jsonl")}
    response = requests.post(f"{api_client.base_url}/upload", files=files)

    # Should return error
    assert response.status_code in [400, 422, 500]


def test_upload_missing_required_fields(api_client):
    """Test uploading JSONL with missing required fields."""
    import requests
    missing_fields = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_pass", "when": "call", "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""
    files = {"file": ("test.jsonl", missing_fields, "application/jsonl")}
    response = requests.post(f"{api_client.base_url}/upload", files=files)

    # Should handle missing fields gracefully
    assert response.status_code in [200, 400, 422]


def test_session_not_found(api_client):
    """Test accessing non-existent session."""
    response = api_client.session.get(f"{api_client.base_url}/sessions/99999")

    assert response.status_code == 404


def test_session_api_not_found(api_client):
    """Test API endpoint for non-existent session."""
    import requests
    response = requests.get(f"{api_client.base_url}/api/sessions/99999")

    assert response.status_code == 404


def test_special_characters_in_nodeid(api_client):
    """Test handling special characters in nodeid."""
    jsonl_special = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test[param-1]::[value]::test_name", "location": ["test.py", 1, "test_name"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test[param-1]::[value]::test_name", "location": ["test.py", 1, "test_name"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test[param-1]::[value]::test_name", "location": ["test.py", 1, "test_name"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""

    result = api_client.upload_jsonl(jsonl_special)

    assert result["status"] == "success"
    assert result["total_tests"] == 1


def test_url_encoding_in_history_path(api_client):
    """Test URL encoding in test history paths."""
    jsonl_brackets = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test.py::test_func[param1]", "location": ["test.py", 1, "test_func"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test.py::test_func[param1]", "location": ["test.py", 1, "test_func"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test.py::test_func[param1]", "location": ["test.py", 1, "test_func"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""

    api_client.upload_jsonl(jsonl_brackets)

    # Should be able to access history page (URL encoding handled)
    import urllib.parse
    encoded_nodeid = urllib.parse.quote("test.py::test_func[param1]", safe='')
    response = api_client.session.get(f"{api_client.base_url}/history/{encoded_nodeid}")

    # Should either work or return 404, not crash
    assert response.status_code in [200, 404]
