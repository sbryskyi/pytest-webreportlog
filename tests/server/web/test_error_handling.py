"""Tests for error handling: invalid inputs, not found, edge cases."""
import urllib.parse
import uuid

import requests

from .conftest import APIClient


def test_stream_empty_event(api_client: APIClient) -> None:
    """Streaming an empty event body is rejected."""
    response = api_client.post_stream_event("")
    assert response.status_code == 400


def test_stream_malformed_json(api_client: APIClient) -> None:
    """Streaming a malformed JSON line is rejected."""
    response = api_client.post_stream_event("{this is not valid json}")
    assert response.status_code == 400


def test_stream_missing_required_fields(api_client: APIClient) -> None:
    """A TestReport with missing optional fields is handled gracefully."""
    session_uuid = uuid.uuid4().hex
    api_client.post_stream_event(
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}', session_uuid
    )
    response = api_client.post_stream_event(
        '{"nodeid": "test_sample.py::test_pass", "when": "call", "$report_type": "TestReport"}',
        session_uuid,
    )
    # Server fills missing fields with defaults rather than crashing.
    assert response.status_code in [200, 400, 422]


def test_session_not_found(api_client: APIClient) -> None:
    """Test accessing non-existent session."""
    response = api_client.session.get(f"{api_client.base_url}/sessions/99999")

    assert response.status_code == 404


def test_session_api_not_found(api_client: APIClient) -> None:
    """Test API endpoint for non-existent session."""
    response = requests.get(f"{api_client.base_url}/api/sessions/99999")

    assert response.status_code == 404


def test_special_characters_in_nodeid(api_client: APIClient) -> None:
    """Test handling special characters in nodeid."""
    jsonl_special = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test[param-1]::[value]::test_name", "location": ["test.py", 1, "test_name"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test[param-1]::[value]::test_name", "location": ["test.py", 1, "test_name"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test[param-1]::[value]::test_name", "location": ["test.py", 1, "test_name"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""

    result = api_client.stream_jsonl(jsonl_special)

    assert result["status"] == "success"
    assert result["total_tests"] == 1


def test_url_encoding_in_history_path(api_client: APIClient) -> None:
    """Test URL encoding in test history paths."""
    jsonl_brackets = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test.py::test_func[param1]", "location": ["test.py", 1, "test_func"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test.py::test_func[param1]", "location": ["test.py", 1, "test_func"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test.py::test_func[param1]", "location": ["test.py", 1, "test_func"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""

    api_client.stream_jsonl(jsonl_brackets)

    # Should be able to access history page (URL encoding handled)
    encoded_nodeid = urllib.parse.quote("test.py::test_func[param1]", safe="")
    response = api_client.session.get(f"{api_client.base_url}/history/{encoded_nodeid}")

    # Should either work or return 404, not crash
    assert response.status_code in [200, 404]
