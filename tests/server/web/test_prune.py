"""End-to-end prune test on an isolated, fixture-managed server.

Uses its own server process + database (separate from the shared session-scoped
one) so that destructive pruning cannot affect other tests.
"""
import json
import subprocess
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
import requests

from .conftest import APIClient

PORT = 8002
BASE_URL = f"http://127.0.0.1:{PORT}"


@pytest.fixture
def isolated_client(tmp_path: Path) -> Generator[APIClient, None, None]:
    """A fresh server (own DB) for one test; torn down afterward."""
    db_path = tmp_path / "prune.db"
    env = {
        **subprocess.os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
    }
    process = subprocess.Popen(
        [
            "uv", "run", "uvicorn", "webreportlog_server.main:app",
            "--host", "127.0.0.1", "--port", str(PORT),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        for _ in range(50):  # up to ~5s
            try:
                requests.get(f"{BASE_URL}/")
                break
            except requests.exceptions.ConnectionError:
                time.sleep(0.1)
        else:
            process.kill()
            raise RuntimeError("Server failed to start")
        yield APIClient(BASE_URL)
    finally:
        process.terminate()
        process.wait(timeout=5)


def _stream_big_session(client: APIClient, payload_bytes: int = 300_000) -> int:
    """Stream a single completed session carrying a large captured-log section."""
    session_uuid = uuid.uuid4().hex
    big = "X" * payload_bytes
    events = [
        {"pytest_version": "8.4.2", "$report_type": "SessionStart"},
        {
            "nodeid": "t.py::test_big", "location": ["t.py", 1, "test_big"],
            "keywords": {}, "outcome": "passed", "when": "call",
            "duration": 0.1, "start": 1000.0, "stop": 1000.1,
            "sections": [["Captured stdout call", big]],
            "$report_type": "TestReport",
        },
        {"exitstatus": 0, "$report_type": "SessionFinish"},
    ]
    last = None
    for event in events:
        last = client.post_stream_event(json.dumps(event), session_uuid).json()
    return last["session_id"]


def test_prune_strips_logs_and_shows_notice(isolated_client: APIClient) -> None:
    session_id = _stream_big_session(isolated_client)
    before = isolated_client.session.get(
        f"{isolated_client.base_url}/api/stats"
    ).json()["database"]["size_bytes"]

    resp = isolated_client.session.post(
        f"{isolated_client.base_url}/api/prune",
        json={"max_size_bytes": 50_000, "keep_recent": 0},
    )
    assert resp.status_code == 200
    report = resp.json()
    assert session_id in report["stripped"]
    assert report["under_cap"] is True

    # Size dropped on disk.
    after = isolated_client.session.get(
        f"{isolated_client.base_url}/api/stats"
    ).json()["database"]["size_bytes"]
    assert after < before

    # Session still exists, big log gone, and the detail page shows the notice.
    session = isolated_client.get_session(session_id)
    assert session is not None
    html = isolated_client.get_session_html(session_id)
    assert "pruned to reclaim" in html
