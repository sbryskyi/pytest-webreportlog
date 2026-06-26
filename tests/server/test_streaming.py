"""Tests for streaming event processing."""

import json
from collections.abc import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine
from webreportlog_server.models import Session as TestSession
from webreportlog_server.models import SessionStatus, TestReport
from webreportlog_server.streaming import (
    _update_session_stats,
    active_sessions,
    process_event,
)


@pytest.fixture
def test_db() -> Generator[Session, None, None]:
    """Create an in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def clear_active_sessions() -> Generator[None, None, None]:
    """Clear active sessions cache before each test."""
    active_sessions.clear()
    yield
    active_sessions.clear()


# SessionStart event tests


def test_process_session_start_creates_new_session(test_db: Session) -> None:
    """Test that SessionStart creates a new session."""
    event = '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}'

    session, event_type = process_event(event, None, test_db)

    assert session is not None
    assert session.id is not None
    assert session.pytest_version == "8.4.2"
    assert session.status == SessionStatus.IN_PROGRESS.value
    assert event_type == "session_start"
    assert session.id in active_sessions


def test_process_session_start_with_existing_session_id(test_db: Session) -> None:
    """Test SessionStart with existing session ID."""
    # Create session first
    existing_session = TestSession(
        pytest_version="8.0.0", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(existing_session)
    test_db.commit()
    test_db.refresh(existing_session)

    event = '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}'

    session, event_type = process_event(event, existing_session.id, test_db)

    assert session.id == existing_session.id
    assert event_type == "session_start"


def test_process_session_start_with_nonexistent_session_id(test_db: Session) -> None:
    """Test SessionStart with non-existent session ID raises error."""
    event = '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}'

    with pytest.raises(ValueError, match="Session 9999 not found"):
        process_event(event, 9999, test_db)


# SessionFinish event tests


def test_process_session_finish(test_db: Session) -> None:
    """Test SessionFinish event updates session."""
    # Create session first
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    # Add to active sessions
    active_sessions[session.id] = {
        "test_outcomes": {},
        "min_start": None,
        "max_stop": None,
    }

    event = '{"exitstatus": 0, "$report_type": "SessionFinish"}'

    result_session, event_type = process_event(event, session.id, test_db)

    assert result_session.exitstatus == 0
    assert result_session.status == SessionStatus.COMPLETED.value
    assert event_type == "session_finish"
    assert session.id not in active_sessions  # Should be cleaned up


def test_process_session_finish_without_session_id(test_db: Session) -> None:
    """Test SessionFinish without session_id raises error."""
    event = '{"exitstatus": 0, "$report_type": "SessionFinish"}'

    with pytest.raises(ValueError, match="SessionFinish without session_id"):
        process_event(event, None, test_db)


def test_process_session_finish_with_nonexistent_session(test_db: Session) -> None:
    """Test SessionFinish with non-existent session raises error."""
    event = '{"exitstatus": 0, "$report_type": "SessionFinish"}'

    with pytest.raises(ValueError, match="Session 9999 not found"):
        process_event(event, 9999, test_db)


# TestReport event tests


def test_process_test_report_creates_report(test_db: Session) -> None:
    """Test TestReport event creates test report."""
    # Create session first
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    event = json.dumps(
        {
            "nodeid": "test.py::test_pass",
            "location": ["test.py", 1, "test_pass"],
            "keywords": {},
            "outcome": "passed",
            "longrepr": None,
            "when": "call",
            "duration": 0.002,
            "start": 1000.0,
            "stop": 1000.002,
            "sections": [],
            "$report_type": "TestReport",
        }
    )

    result_session, event_type = process_event(event, session.id, test_db)

    assert event_type == "test_report_call"
    assert result_session.total_tests == 1
    assert result_session.passed == 1

    # Check that test report was created
    from sqlmodel import select

    statement = select(TestReport).where(TestReport.session_id == session.id)
    reports = test_db.exec(statement).all()
    assert len(reports) == 1
    assert reports[0].nodeid == "test.py::test_pass"
    assert reports[0].outcome == "passed"


def test_process_test_report_without_session_id(test_db: Session) -> None:
    """Test TestReport without session_id raises error."""
    event = json.dumps(
        {
            "nodeid": "test.py::test_pass",
            "when": "call",
            "outcome": "passed",
            "$report_type": "TestReport",
        }
    )

    with pytest.raises(ValueError, match="TestReport without session_id"):
        process_event(event, None, test_db)


def test_process_test_report_with_nonexistent_session(test_db: Session) -> None:
    """Test TestReport with non-existent session raises error."""
    event = json.dumps(
        {
            "nodeid": "test.py::test_pass",
            "when": "call",
            "outcome": "passed",
            "$report_type": "TestReport",
        }
    )

    with pytest.raises(ValueError, match="Session 9999 not found"):
        process_event(event, 9999, test_db)


def test_process_test_report_tracks_setup_error(test_db: Session) -> None:
    """Test TestReport tracks setup errors."""
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    event = json.dumps(
        {
            "nodeid": "test.py::test_fail",
            "location": ["test.py", 1, "test_fail"],
            "keywords": {},
            "outcome": "failed",
            "longrepr": "Setup failed",
            "when": "setup",
            "duration": 0.001,
            "start": 1000.0,
            "stop": 1000.001,
            "sections": [],
            "$report_type": "TestReport",
        }
    )

    result_session, event_type = process_event(event, session.id, test_db)

    assert result_session.errors == 1
    assert result_session.total_tests == 1


def test_process_test_report_tracks_teardown_error(test_db: Session) -> None:
    """Test TestReport tracks teardown errors."""
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    # First add passing call phase
    call_event = json.dumps(
        {
            "nodeid": "test.py::test_pass",
            "location": ["test.py", 1, "test_pass"],
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
    process_event(call_event, session.id, test_db)

    # Then add failing teardown
    teardown_event = json.dumps(
        {
            "nodeid": "test.py::test_pass",
            "location": ["test.py", 1, "test_pass"],
            "keywords": {},
            "outcome": "failed",
            "longrepr": "Teardown failed",
            "when": "teardown",
            "duration": 0.001,
            "start": 1000.001,
            "stop": 1000.002,
            "sections": [],
            "$report_type": "TestReport",
        }
    )

    result_session, event_type = process_event(teardown_event, session.id, test_db)

    assert result_session.errors == 1
    assert result_session.passed == 1  # Call phase still passed


def test_process_test_report_tracks_xfail(test_db: Session) -> None:
    """Test TestReport tracks xfail correctly."""
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    event = json.dumps(
        {
            "nodeid": "test.py::test_xfail",
            "location": ["test.py", 1, "test_xfail"],
            "keywords": {"xfail": 1},
            "outcome": "skipped",
            "longrepr": None,
            "when": "call",
            "duration": 0.0,
            "start": 1000.0,
            "stop": 1000.0,
            "sections": [],
            "$report_type": "TestReport",
        }
    )

    result_session, event_type = process_event(event, session.id, test_db)

    assert result_session.xfailed == 1
    assert result_session.passed == 0
    assert result_session.skipped == 0


def test_process_test_report_tracks_xpass(test_db: Session) -> None:
    """Test TestReport tracks xpass correctly."""
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    event = json.dumps(
        {
            "nodeid": "test.py::test_xpass",
            "location": ["test.py", 1, "test_xpass"],
            "keywords": {"xfail": 1},
            "outcome": "passed",
            "longrepr": None,
            "when": "call",
            "duration": 0.002,
            "start": 1000.0,
            "stop": 1000.002,
            "sections": [],
            "$report_type": "TestReport",
        }
    )

    result_session, event_type = process_event(event, session.id, test_db)

    assert result_session.xpassed == 1
    assert result_session.passed == 0


def test_process_test_report_calculates_duration(test_db: Session) -> None:
    """Test TestReport calculates session duration from timestamps."""
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    # Add first test
    event1 = json.dumps(
        {
            "nodeid": "test.py::test1",
            "location": ["test.py", 1, "test1"],
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
    process_event(event1, session.id, test_db)

    # Add second test with later timestamp
    event2 = json.dumps(
        {
            "nodeid": "test.py::test2",
            "location": ["test.py", 2, "test2"],
            "keywords": {},
            "outcome": "passed",
            "longrepr": None,
            "when": "call",
            "duration": 0.001,
            "start": 1000.005,
            "stop": 1000.010,
            "sections": [],
            "$report_type": "TestReport",
        }
    )
    result_session, _ = process_event(event2, session.id, test_db)

    assert result_session.duration is not None
    assert result_session.duration == pytest.approx(0.010)  # 1000.010 - 1000.0


def test_process_test_report_handles_multiple_phases(test_db: Session) -> None:
    """Test TestReport handles setup, call, teardown phases."""
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    # Setup phase
    setup_event = json.dumps(
        {
            "nodeid": "test.py::test_pass",
            "location": ["test.py", 1, "test_pass"],
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
    )
    session, event_type = process_event(setup_event, session.id, test_db)
    assert event_type == "test_report_setup"

    # Call phase
    call_event = json.dumps(
        {
            "nodeid": "test.py::test_pass",
            "location": ["test.py", 1, "test_pass"],
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
    )
    session, event_type = process_event(call_event, session.id, test_db)
    assert event_type == "test_report_call"
    assert session.passed == 1

    # Teardown phase
    teardown_event = json.dumps(
        {
            "nodeid": "test.py::test_pass",
            "location": ["test.py", 1, "test_pass"],
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
    )
    session, event_type = process_event(teardown_event, session.id, test_db)
    assert event_type == "test_report_teardown"

    # Check we still have 1 test
    assert session.total_tests == 1
    assert session.passed == 1


# CollectReport event tests


def test_process_collect_report(test_db: Session) -> None:
    """Test CollectReport event is handled."""
    session = TestSession(
        pytest_version="8.4.2", status=SessionStatus.IN_PROGRESS.value
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)

    event = '{"nodeid": "test.py", "$report_type": "CollectReport"}'

    result_session, event_type = process_event(event, session.id, test_db)

    assert result_session.id == session.id
    assert event_type == "collect_report"


def test_process_collect_report_without_session_id(test_db: Session) -> None:
    """CollectReport before SessionStart is silently ignored (returns None session)."""
    event = '{"nodeid": "test.py", "$report_type": "CollectReport"}'

    session, event_type = process_event(event, None, test_db)
    assert session is None
    assert event_type == "collect_report"


# Edge cases and error handling


def test_process_empty_event_line(test_db: Session) -> None:
    """Test processing empty event line raises error."""
    with pytest.raises(ValueError, match="Empty event line"):
        process_event("", None, test_db)


def test_process_whitespace_event_line(test_db: Session) -> None:
    """Test processing whitespace-only event line raises error."""
    with pytest.raises(ValueError, match="Empty event line"):
        process_event("   \n  ", None, test_db)


def test_process_unknown_report_type(test_db: Session) -> None:
    """Test unknown report type raises error."""
    event = '{"$report_type": "UnknownType"}'

    with pytest.raises(ValueError, match="Unknown report type: UnknownType"):
        process_event(event, None, test_db)


def test_process_invalid_json(test_db: Session) -> None:
    """Test invalid JSON raises error."""
    event = "{invalid json}"

    with pytest.raises(json.JSONDecodeError):
        process_event(event, None, test_db)


# _update_session_stats tests


def test_update_session_stats_all_passed(test_db: Session) -> None:
    """Test stats calculation with all passing tests."""
    session = TestSession(pytest_version="8.4.2")
    test_db.add(session)
    test_db.commit()

    test_outcomes = {
        "test1": {
            "call_outcome": "passed",
            "has_setup_error": False,
            "has_teardown_error": False,
            "has_xfail_marker": False,
        },
        "test2": {
            "call_outcome": "passed",
            "has_setup_error": False,
            "has_teardown_error": False,
            "has_xfail_marker": False,
        },
    }

    _update_session_stats(session, test_outcomes)

    assert session.total_tests == 2
    assert session.passed == 2
    assert session.failed == 0
    assert session.skipped == 0
    assert session.errors == 0


def test_update_session_stats_mixed_outcomes(test_db: Session) -> None:
    """Test stats calculation with mixed outcomes."""
    session = TestSession(pytest_version="8.4.2")
    test_db.add(session)
    test_db.commit()

    test_outcomes = {
        "test1": {
            "call_outcome": "passed",
            "has_setup_error": False,
            "has_teardown_error": False,
            "has_xfail_marker": False,
        },
        "test2": {
            "call_outcome": "failed",
            "has_setup_error": False,
            "has_teardown_error": False,
            "has_xfail_marker": False,
        },
        "test3": {
            "call_outcome": "skipped",
            "has_setup_error": False,
            "has_teardown_error": False,
            "has_xfail_marker": False,
        },
    }

    _update_session_stats(session, test_outcomes)

    assert session.total_tests == 3
    assert session.passed == 1
    assert session.failed == 1
    assert session.skipped == 1
    assert session.errors == 0


def test_update_session_stats_with_errors(test_db: Session) -> None:
    """Test stats calculation with setup/teardown errors."""
    session = TestSession(pytest_version="8.4.2")
    test_db.add(session)
    test_db.commit()

    test_outcomes = {
        "test1": {
            "call_outcome": None,
            "has_setup_error": True,
            "has_teardown_error": False,
            "has_xfail_marker": False,
        },
        "test2": {
            "call_outcome": "passed",
            "has_setup_error": False,
            "has_teardown_error": True,
            "has_xfail_marker": False,
        },
    }

    _update_session_stats(session, test_outcomes)

    assert session.total_tests == 2
    assert session.errors == 2
    assert session.passed == 1  # test2 call phase passed


def test_update_session_stats_xfail_xpass(test_db: Session) -> None:
    """Test stats calculation with xfail and xpass."""
    session = TestSession(pytest_version="8.4.2")
    test_db.add(session)
    test_db.commit()

    test_outcomes = {
        "test1": {
            "call_outcome": "skipped",
            "has_setup_error": False,
            "has_teardown_error": False,
            "has_xfail_marker": True,
        },
        "test2": {
            "call_outcome": "passed",
            "has_setup_error": False,
            "has_teardown_error": False,
            "has_xfail_marker": True,
        },
    }

    _update_session_stats(session, test_outcomes)

    assert session.total_tests == 2
    assert session.xfailed == 1
    assert session.xpassed == 1
    assert session.passed == 0
    assert session.skipped == 0


def test_update_session_stats_duration_calculation(test_db: Session) -> None:
    """Test duration calculation from timestamps."""
    session = TestSession(pytest_version="8.4.2")
    test_db.add(session)
    test_db.commit()

    test_outcomes = {}

    _update_session_stats(session, test_outcomes, min_start=1000.0, max_stop=1005.5)

    assert session.duration == pytest.approx(5.5)


def test_update_session_stats_no_duration_without_timestamps(test_db: Session) -> None:
    """Test that duration is not set without timestamps."""
    session = TestSession(pytest_version="8.4.2")
    test_db.add(session)
    test_db.commit()

    test_outcomes = {}

    _update_session_stats(session, test_outcomes, min_start=None, max_stop=None)

    assert session.duration is None


def test_update_session_stats_partial_timestamps(test_db: Session) -> None:
    """Test duration calculation with partial timestamps."""
    session = TestSession(pytest_version="8.4.2")
    test_db.add(session)
    test_db.commit()

    test_outcomes = {}

    # Only min_start, no max_stop
    _update_session_stats(session, test_outcomes, min_start=1000.0, max_stop=None)
    assert session.duration is None

    # Only max_stop, no min_start
    _update_session_stats(session, test_outcomes, min_start=None, max_stop=1005.0)
    assert session.duration is None
