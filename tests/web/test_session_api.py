"""Tests for session API endpoints: upload, list, delete, get."""
import requests

from .conftest import APIClient


def test_server_is_running(api_client: APIClient) -> None:
    """Test that server starts and responds."""
    html = api_client.get_index_html()
    assert "pytest-webreportlog" in html


def test_upload_simple_passing(api_client: APIClient, simple_passing_jsonl: str) -> None:
    """Test uploading a simple passing test."""
    result = api_client.upload_jsonl(simple_passing_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 1
    assert result["passed"] == 1
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 0


def test_upload_mixed_outcomes(api_client: APIClient, mixed_outcomes_jsonl: str) -> None:
    """Test uploading tests with mixed outcomes."""
    result = api_client.upload_jsonl(mixed_outcomes_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 3
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert result["skipped"] == 1
    assert result["errors"] == 0


def test_upload_setup_teardown_errors(
    api_client: APIClient, setup_teardown_errors_jsonl: str
) -> None:
    """Test uploading tests with setup/teardown errors."""
    result = api_client.upload_jsonl(setup_teardown_errors_jsonl)

    assert result["status"] == "success"
    assert result["total_tests"] == 2
    assert result["passed"] == 1  # test_teardown_error call phase passed
    assert result["failed"] == 0
    assert result["skipped"] == 0
    assert result["errors"] == 2  # 1 setup error + 1 teardown error


def test_session_api_data(api_client: APIClient, mixed_outcomes_jsonl: str) -> None:
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


def test_sessions_list_api(
    api_client: APIClient, simple_passing_jsonl: str, mixed_outcomes_jsonl: str
) -> None:
    """Test sessions list API."""
    # Upload two sessions
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    sessions = api_client.get_sessions()

    assert len(sessions) >= 2
    # Most recent first
    assert sessions[0]["id"] > sessions[1]["id"]


def test_index_shows_sessions(
    api_client: APIClient, simple_passing_jsonl: str, mixed_outcomes_jsonl: str
) -> None:
    """Test index page shows uploaded sessions."""
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    html = api_client.get_index_html()

    assert "Test Sessions" in html
    # Check for session IDs
    assert "#1" in html or "#2" in html
    # Check for status (Passed or Failed instead of Completed)
    assert "Passed" in html or "Failed" in html


def test_upload_invalid_file(api_client: APIClient) -> None:
    """Test uploading non-JSONL file returns error."""
    files = {"file": ("test.txt", "not jsonl", "text/plain")}
    response = requests.post(f"{api_client.base_url}/upload", files=files)

    assert response.status_code == 400


def test_upload_xfail(api_client: APIClient, xfail_jsonl: str) -> None:
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


def test_upload_xpass(api_client: APIClient, xpass_jsonl: str) -> None:
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


def test_upload_xfail_xpass_mixed(
    api_client: APIClient, xfail_xpass_mixed_jsonl: str
) -> None:
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


# ============================================================================
# SESSION DELETION TESTS
# ============================================================================


def test_delete_session_success(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test deleting a session returns success."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    # Verify session exists
    sessions_before = api_client.get_sessions()
    assert any(s["id"] == session_id for s in sessions_before)

    # Delete session
    response = api_client.delete_session(session_id)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"


def test_delete_session_removes_from_list(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test deleting a session removes it from session list."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    # Delete session
    api_client.delete_session(session_id)

    # Verify session is gone
    sessions_after = api_client.get_sessions()
    assert not any(s["id"] == session_id for s in sessions_after)


def test_delete_session_not_found(api_client: APIClient) -> None:
    """Test deleting non-existent session returns 404."""
    response = api_client.delete_session(99999)
    assert response.status_code == 404


def test_delete_session_api_returns_correct_message(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test delete response contains correct message."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    response = api_client.delete_session(session_id)
    data = response.json()

    assert "message" in data
    assert str(session_id) in data["message"]


# ============================================================================
# TEST ENTRIES ENDPOINT TESTS
# ============================================================================


def test_get_test_entries_html_success(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test getting test entries HTML returns valid HTML."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    response = api_client.get_test_entries_html(session_id)

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_get_test_entries_html_contains_test_info(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test test entries HTML contains test information."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    response = api_client.get_test_entries_html(session_id)
    html = response.text

    # Should contain test name
    assert "test_pass" in html
    # Should contain result
    assert "PASS" in html


def test_get_test_entries_not_found(api_client: APIClient) -> None:
    """Test 404 for non-existent session test entries."""
    response = api_client.get_test_entries_html(99999)
    assert response.status_code == 404


def test_get_test_entries_includes_all_tests(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test entries HTML includes all tests in session."""
    result = api_client.upload_jsonl(mixed_outcomes_jsonl)
    session_id = result["session_id"]

    response = api_client.get_test_entries_html(session_id)
    html = response.text

    # Should contain all test names
    assert "test_pass" in html
    assert "test_fail" in html
    assert "test_skip" in html
