"""Tests for parser module."""
import pytest
import json
from sqlmodel import Session, create_engine, SQLModel
from src.app.parser import parse_jsonl_report
from src.app.models import Session as TestSession, TestReport


@pytest.fixture
def test_db():
    """Create an in-memory test database."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_parse_simple_passing_test(test_db):
    """Test parsing simple passing test."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 0, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.pytest_version == "8.4.2"
    assert session.exitstatus == 0
    assert session.total_tests == 1
    assert session.passed == 1
    assert session.failed == 0


def test_parse_failed_test(test_db):
    """Test parsing failed test."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_fail", "location": ["test.py", 1, "test_fail"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_fail", "location": ["test.py", 1, "test_fail"], "keywords": {}, "outcome": "failed", "longrepr": "assert False", "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_fail", "location": ["test.py", 1, "test_fail"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 1, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.total_tests == 1
    assert session.failed == 1
    assert session.passed == 0


def test_parse_with_empty_lines(test_db):
    """Test parsing with empty lines."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}',
        '',
        '{"exitstatus": 0, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.pytest_version == "8.4.2"
    assert session.exitstatus == 0


def test_parse_xfail_test(test_db):
    """Test parsing xfail test."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_xfail", "location": ["test.py", 1, "test_xfail"], "keywords": {"xfail": 1}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_xfail", "location": ["test.py", 1, "test_xfail"], "keywords": {"xfail": 1}, "outcome": "skipped", "longrepr": null, "when": "call", "duration": 0.0, "start": 1000.001, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_xfail", "location": ["test.py", 1, "test_xfail"], "keywords": {"xfail": 1}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.001, "stop": 1000.002, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 0, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.total_tests == 1
    assert session.xfailed == 1
    assert session.passed == 0


def test_parse_xpass_test(test_db):
    """Test parsing xpass test."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_xpass", "location": ["test.py", 1, "test_xpass"], "keywords": {"xfail": 1}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_xpass", "location": ["test.py", 1, "test_xpass"], "keywords": {"xfail": 1}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_xpass", "location": ["test.py", 1, "test_xpass"], "keywords": {"xfail": 1}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 0, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.total_tests == 1
    assert session.xpassed == 1
    assert session.passed == 0


def test_parse_xfail_no_run(test_db):
    """Test parsing xfail(run=False) test - no call phase, only setup and teardown."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_xfail_no_run", "location": ["test.py", 1, "test_xfail_no_run"], "keywords": {"xfail": 1}, "outcome": "skipped", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "wasxfail": "[NOTRUN] reason", "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_xfail_no_run", "location": ["test.py", 1, "test_xfail_no_run"], "keywords": {"xfail": 1}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.001, "stop": 1000.002, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 0, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.total_tests == 1
    assert session.xfailed == 1
    assert session.passed == 0
    assert session.failed == 0


def test_parse_setup_error(test_db):
    """Test parsing setup error."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_setup_error", "location": ["test.py", 1, "test_setup_error"], "keywords": {}, "outcome": "failed", "longrepr": "Setup failed", "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 1, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.total_tests == 1
    assert session.errors == 1


def test_parse_teardown_error(test_db):
    """Test parsing teardown error."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_teardown_error", "location": ["test.py", 1, "test_teardown_error"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_teardown_error", "location": ["test.py", 1, "test_teardown_error"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_teardown_error", "location": ["test.py", 1, "test_teardown_error"], "keywords": {}, "outcome": "failed", "longrepr": "Teardown failed", "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 1, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.total_tests == 1
    assert session.errors == 1
    assert session.passed == 1  # Call phase passed


def test_parse_multiple_tests(test_db):
    """Test parsing multiple tests."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        # Test 1: pass
        '{"nodeid": "test.py::test1", "location": ["test.py", 1, "test1"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        # Test 2: fail
        '{"nodeid": "test.py::test2", "location": ["test.py", 2, "test2"], "keywords": {}, "outcome": "failed", "longrepr": "failed", "when": "call", "duration": 0.001, "start": 1000.001, "stop": 1000.002, "sections": [], "$report_type": "TestReport"}',
        # Test 3: skip
        '{"nodeid": "test.py::test3", "location": ["test.py", 3, "test3"], "keywords": {}, "outcome": "skipped", "longrepr": null, "when": "call", "duration": 0.0, "start": 1000.002, "stop": 1000.002, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 1, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.total_tests == 3
    assert session.passed == 1
    assert session.failed == 1
    assert session.skipped == 1


def test_parse_duration_calculation(test_db):
    """Test that duration is calculated from timestamps."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 100.0, "stop": 100.002, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 0, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    # Session duration should be calculated
    assert session.duration is not None
    assert session.duration > 0


def test_parse_without_session_finish(test_db):
    """Test parsing without SessionFinish (interrupted session)."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.0, "stop": 1000.002, "sections": [], "$report_type": "TestReport"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    assert session.pytest_version == "8.4.2"
    assert session.exitstatus is None  # No SessionFinish means no exitstatus


def test_parse_creates_test_reports(test_db):
    """Test that TestReport records are created."""
    lines = [
        '{"pytest_version": "8.4.2", "$report_type": "SessionStart"}',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}',
        '{"nodeid": "test.py::test_pass", "location": ["test.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}',
        '{"exitstatus": 0, "$report_type": "SessionFinish"}',
    ]

    session = parse_jsonl_report(lines, test_db)

    # Check that test reports were created
    reports = test_db.query(TestReport).filter(TestReport.session_id == session.id).all()
    assert len(reports) == 3  # setup, call, teardown
    assert all(r.nodeid == "test.py::test_pass" for r in reports)
