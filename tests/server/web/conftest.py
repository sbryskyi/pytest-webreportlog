"""Fixtures for web server tests."""
import shutil
import subprocess
import tempfile
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
import requests

# Count keys returned in the streamed session-summary dict.
_COUNT_KEYS = (
    "total_tests",
    "passed",
    "failed",
    "skipped",
    "xfailed",
    "xpassed",
    "errors",
)


class APIClient:
    """HTTP client for API requests to the test web server."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.session = requests.Session()

    def stream_jsonl(self, content: str) -> dict:
        """Stream newline-delimited events to the live event endpoint.

        Each non-empty line is one serialized report event, posted under a
        single per-call session UUID (mirroring how the plugin streams a run).
        Returns a session-summary dict in the same shape the old /upload
        endpoint produced, derived from the last server response.
        """
        session_uuid = uuid.uuid4().hex
        session_id = None
        counts = {key: 0 for key in _COUNT_KEYS}
        for line in content.splitlines():
            if not line.strip():
                continue
            data = self.post_stream_event(line, session_uuid).json()
            if not isinstance(data, dict):
                continue
            if data.get("session_id") is not None:
                session_id = data["session_id"]
            if isinstance(data.get("session"), dict):
                counts = {key: data["session"].get(key, counts[key]) for key in _COUNT_KEYS}
        return {"status": "success", "session_id": session_id, **counts}

    def get_sessions(self) -> list[dict]:
        """Get all sessions."""
        response = self.session.get(f"{self.base_url}/api/sessions")
        return response.json()

    def get_session(self, session_id: int) -> dict:
        """Get specific session."""
        response = self.session.get(f"{self.base_url}/api/sessions/{session_id}")
        return response.json()

    def get_session_html(self, session_id: int) -> str:
        """Get session detail HTML."""
        response = self.session.get(f"{self.base_url}/sessions/{session_id}")
        return response.text

    def get_index_html(self) -> str:
        """Get index page HTML."""
        response = self.session.get(f"{self.base_url}/")
        return response.text

    def delete_session(self, session_id: int) -> requests.Response:
        """Delete a session."""
        response = self.session.delete(f"{self.base_url}/api/sessions/{session_id}")
        return response

    def get_test_entries_html(self, session_id: int) -> requests.Response:
        """Get test entries HTML fragment."""
        response = self.session.get(
            f"{self.base_url}/api/sessions/{session_id}/test-entries"
        )
        return response

    def post_stream_event(
        self, event: str, session_uuid: str | None = None
    ) -> requests.Response:
        """Post a streaming event."""
        headers: dict[str, str] = {}
        if session_uuid:
            headers["X-Session-ID"] = session_uuid
        response = self.session.post(
            f"{self.base_url}/api/stream/event",
            data=event,
            headers={**headers, "Content-Type": "text/plain"},
        )
        return response


@pytest.fixture(scope="session")
def test_db_path() -> Generator[Path, None, None]:
    """Create a temporary database path for testing."""
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    yield db_path
    shutil.rmtree(tmpdir)


@pytest.fixture(scope="session")
def web_server(test_db_path: Path) -> Generator[str, None, None]:
    """Start web server for testing."""
    env = {
        "DATABASE_URL": f"sqlite:///{test_db_path}",
    }

    process = subprocess.Popen(
        [
            "uv",
            "run",
            "uvicorn",
            "webreportlog_server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8001",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**subprocess.os.environ, **env},
    )

    base_url = "http://127.0.0.1:8001"
    for _ in range(30):  # Wait up to 3 seconds
        try:
            requests.get(f"{base_url}/")
            break
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
    else:
        process.kill()
        raise RuntimeError("Server failed to start")

    yield base_url

    process.terminate()
    process.wait(timeout=5)


@pytest.fixture
def api_client(web_server: str) -> APIClient:
    """HTTP client for API requests."""
    return APIClient(web_server)


# JSONL test fixtures


@pytest.fixture
def simple_passing_jsonl() -> str:
    """Simple passing test JSONL."""
    return """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_pass", "location": ["test_sample.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_pass", "location": ["test_sample.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_pass", "location": ["test_sample.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""


@pytest.fixture
def mixed_outcomes_jsonl() -> str:
    """JSONL with passed, failed, and skipped tests."""
    return """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_pass", "location": ["test_sample.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_pass", "location": ["test_sample.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_pass", "location": ["test_sample.py", 1, "test_pass"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_fail", "location": ["test_sample.py", 5, "test_fail"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.004, "stop": 1000.005, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_fail", "location": ["test_sample.py", 5, "test_fail"], "keywords": {}, "outcome": "failed", "longrepr": {"reprcrash": {"path": "test_sample.py", "lineno": 6, "message": "AssertionError: test failed"}, "reprtraceback": {"reprentries": [{"type": "ReprEntry", "data": {"lines": ["def test_fail():", ">   assert False", "E   AssertionError: test failed"], "reprfuncargs": {"args": []}, "reprlocals": null, "reprfileloc": {"path": "test_sample.py", "lineno": 6, "message": "AssertionError"}}}]}}, "when": "call", "duration": 0.002, "start": 1000.005, "stop": 1000.007, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_fail", "location": ["test_sample.py", 5, "test_fail"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.007, "stop": 1000.008, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_skip", "location": ["test_sample.py", 10, "test_skip"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.008, "stop": 1000.009, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_skip", "location": ["test_sample.py", 10, "test_skip"], "keywords": {}, "outcome": "skipped", "longrepr": null, "when": "call", "duration": 0.0, "start": 1000.009, "stop": 1000.009, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_skip", "location": ["test_sample.py", 10, "test_skip"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.009, "stop": 1000.010, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 1, "$report_type": "SessionFinish"}
"""


@pytest.fixture
def setup_teardown_errors_jsonl() -> str:
    """JSONL with setup and teardown errors."""
    return """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_setup_error", "location": ["test_sample.py", 1, "test_setup_error"], "keywords": {}, "outcome": "failed", "longrepr": {"reprcrash": {"path": "test_sample.py", "lineno": 3, "message": "RuntimeError: Setup failed"}, "reprtraceback": {"reprentries": [{"type": "ReprEntry", "data": {"lines": ["@pytest.fixture", "def failing():", ">   raise RuntimeError('Setup failed')", "E   RuntimeError: Setup failed"], "reprfuncargs": {"args": []}, "reprlocals": null, "reprfileloc": {"path": "test_sample.py", "lineno": 3, "message": "RuntimeError"}}}]}}, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_teardown_error", "location": ["test_sample.py", 10, "test_teardown_error"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.001, "stop": 1000.002, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_teardown_error", "location": ["test_sample.py", 10, "test_teardown_error"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.002, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_teardown_error", "location": ["test_sample.py", 10, "test_teardown_error"], "keywords": {}, "outcome": "failed", "longrepr": {"reprcrash": {"path": "test_sample.py", "lineno": 13, "message": "RuntimeError: Teardown failed"}, "reprtraceback": {"reprentries": [{"type": "ReprEntry", "data": {"lines": ["@pytest.fixture", "def failing_teardown():", "    yield", ">   raise RuntimeError('Teardown failed')", "E   RuntimeError: Teardown failed"], "reprfuncargs": {"args": []}, "reprlocals": null, "reprfileloc": {"path": "test_sample.py", "lineno": 13, "message": "RuntimeError"}}}]}}, "when": "teardown", "duration": 0.001, "start": 1000.004, "stop": 1000.005, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 1, "$report_type": "SessionFinish"}
"""


@pytest.fixture
def xfail_jsonl() -> str:
    """JSONL with xfail test (expected to fail and does fail)."""
    return """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_xfail", "location": ["test_sample.py", 1, "test_xfail"], "keywords": {"xfail": 1, "test_xfail": 1}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xfail", "location": ["test_sample.py", 1, "test_xfail"], "keywords": {"xfail": 1, "test_xfail": 1}, "outcome": "skipped", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xfail", "location": ["test_sample.py", 1, "test_xfail"], "keywords": {"xfail": 1, "test_xfail": 1}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""


@pytest.fixture
def xpass_jsonl() -> str:
    """JSONL with xpass test (expected to fail but passes)."""
    return """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_xpass", "location": ["test_sample.py", 1, "test_xpass"], "keywords": {"xfail": 1, "test_xpass": 1}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xpass", "location": ["test_sample.py", 1, "test_xpass"], "keywords": {"xfail": 1, "test_xpass": 1}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xpass", "location": ["test_sample.py", 1, "test_xpass"], "keywords": {"xfail": 1, "test_xpass": 1}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""


@pytest.fixture
def xfail_xpass_mixed_jsonl() -> str:
    """JSONL with mix of xfail, xpass, and normal tests."""
    return """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_xfail_one", "location": ["test_sample.py", 1, "test_xfail_one"], "keywords": {"xfail": 1, "test_xfail_one": 1}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xfail_one", "location": ["test_sample.py", 1, "test_xfail_one"], "keywords": {"xfail": 1, "test_xfail_one": 1}, "outcome": "skipped", "longrepr": null, "when": "call", "duration": 0.001, "start": 1000.001, "stop": 1000.002, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xfail_one", "location": ["test_sample.py", 1, "test_xfail_one"], "keywords": {"xfail": 1, "test_xfail_one": 1}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.002, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xpass_one", "location": ["test_sample.py", 5, "test_xpass_one"], "keywords": {"xfail": 1, "test_xpass_one": 1}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xpass_one", "location": ["test_sample.py", 5, "test_xpass_one"], "keywords": {"xfail": 1, "test_xpass_one": 1}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.001, "start": 1000.004, "stop": 1000.005, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_xpass_one", "location": ["test_sample.py", 5, "test_xpass_one"], "keywords": {"xfail": 1, "test_xpass_one": 1}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.005, "stop": 1000.006, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_normal_pass", "location": ["test_sample.py", 9, "test_normal_pass"], "keywords": {"test_normal_pass": 1}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.006, "stop": 1000.007, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_normal_pass", "location": ["test_sample.py", 9, "test_normal_pass"], "keywords": {"test_normal_pass": 1}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.001, "start": 1000.007, "stop": 1000.008, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_normal_pass", "location": ["test_sample.py", 9, "test_normal_pass"], "keywords": {"test_normal_pass": 1}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.008, "stop": 1000.009, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""
