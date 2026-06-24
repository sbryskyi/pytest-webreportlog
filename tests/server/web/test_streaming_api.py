"""Tests for streaming API endpoints: real-time event processing."""
import json
import uuid

from .conftest import APIClient


def test_stream_event_session_start_creates_session(api_client: APIClient) -> None:
    """Test POST /api/stream/event with SessionStart creates new session."""
    session_uuid = str(uuid.uuid4())
    event = json.dumps({"pytest_version": "8.4.2", "$report_type": "SessionStart"})

    response = api_client.post_stream_event(event, session_uuid)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "session_id" in data
    assert data["event_type"] == "session_start"


def test_stream_event_test_report_updates_stats(api_client: APIClient) -> None:
    """Test POST /api/stream/event with TestReport updates session stats."""
    session_uuid = str(uuid.uuid4())

    # First, create session
    session_start = json.dumps(
        {"pytest_version": "8.4.2", "$report_type": "SessionStart"}
    )
    api_client.post_stream_event(session_start, session_uuid)

    # Send test report
    test_report = json.dumps(
        {
            "nodeid": "test.py::test_one",
            "location": ["test.py", 1, "test_one"],
            "keywords": {},
            "outcome": "passed",
            "longrepr": None,
            "when": "call",
            "duration": 0.001,
            "start": 1000.0,
            "stop": 1000.001,
            "sections": [],
            "$report_type": "TestReport",
        }
    )

    response = api_client.post_stream_event(test_report, session_uuid)

    assert response.status_code == 200
    data = response.json()
    assert data["session"]["passed"] == 1


def test_stream_event_session_finish_completes(api_client: APIClient) -> None:
    """Test POST /api/stream/event with SessionFinish completes session."""
    session_uuid = str(uuid.uuid4())

    # Create session
    session_start = json.dumps(
        {"pytest_version": "8.4.2", "$report_type": "SessionStart"}
    )
    response = api_client.post_stream_event(session_start, session_uuid)
    session_id = response.json()["session_id"]

    # Finish session
    session_finish = json.dumps({"exitstatus": 0, "$report_type": "SessionFinish"})
    response = api_client.post_stream_event(session_finish, session_uuid)

    assert response.status_code == 200
    data = response.json()
    assert data["event_type"] == "session_finish"

    # Verify session is completed in database
    session = api_client.get_session(session_id)
    assert session["status"] == "completed"


def test_stream_event_invalid_json(api_client: APIClient) -> None:
    """Test POST /api/stream/event with invalid JSON returns error."""
    response = api_client.post_stream_event("{invalid json}")
    assert response.status_code == 400


def test_stream_event_unknown_report_type(api_client: APIClient) -> None:
    """Test POST /api/stream/event with unknown report type returns error."""
    session_uuid = str(uuid.uuid4())

    # Create session first
    session_start = json.dumps(
        {"pytest_version": "8.4.2", "$report_type": "SessionStart"}
    )
    api_client.post_stream_event(session_start, session_uuid)

    # Send unknown report type
    unknown_event = json.dumps({"$report_type": "UnknownType"})
    response = api_client.post_stream_event(unknown_event, session_uuid)

    # Should return error for unknown type
    assert response.status_code in [400, 500]


def test_stream_event_complete_test_flow(api_client: APIClient) -> None:
    """Test complete streaming flow: session start, test reports, session finish."""
    session_uuid = str(uuid.uuid4())

    # Session start
    response = api_client.post_stream_event(
        json.dumps({"pytest_version": "8.4.2", "$report_type": "SessionStart"}),
        session_uuid,
    )
    session_id = response.json()["session_id"]

    # Test setup
    api_client.post_stream_event(
        json.dumps(
            {
                "nodeid": "test.py::test_one",
                "location": ["test.py", 1, "test_one"],
                "keywords": {},
                "outcome": "passed",
                "longrepr": None,
                "when": "setup",
                "duration": 0.001,
                "start": 1000.0,
                "stop": 1000.001,
                "sections": [],
                "$report_type": "TestReport",
            }
        ),
        session_uuid,
    )

    # Test call
    api_client.post_stream_event(
        json.dumps(
            {
                "nodeid": "test.py::test_one",
                "location": ["test.py", 1, "test_one"],
                "keywords": {},
                "outcome": "passed",
                "longrepr": None,
                "when": "call",
                "duration": 0.002,
                "start": 1000.001,
                "stop": 1000.003,
                "sections": [],
                "$report_type": "TestReport",
            }
        ),
        session_uuid,
    )

    # Test teardown
    api_client.post_stream_event(
        json.dumps(
            {
                "nodeid": "test.py::test_one",
                "location": ["test.py", 1, "test_one"],
                "keywords": {},
                "outcome": "passed",
                "longrepr": None,
                "when": "teardown",
                "duration": 0.001,
                "start": 1000.003,
                "stop": 1000.004,
                "sections": [],
                "$report_type": "TestReport",
            }
        ),
        session_uuid,
    )

    # Session finish
    api_client.post_stream_event(
        json.dumps({"exitstatus": 0, "$report_type": "SessionFinish"}),
        session_uuid,
    )

    # Verify final state
    session = api_client.get_session(session_id)
    assert session["status"] == "completed"
    assert session["total_tests"] == 1
    assert session["passed"] == 1
    assert session["exitstatus"] == 0
