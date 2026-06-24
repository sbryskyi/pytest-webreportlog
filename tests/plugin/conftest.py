"""Fixtures for testing the pytest-webreportlog plugin.

Provides a lightweight in-process HTTP server that captures the events the
plugin streams, so plugin behavior can be asserted without the real viewer.
"""
import contextlib
import json
import socket
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _CapturedServer:
    """Holds the stub server's URL and the events it received."""

    def __init__(self, url: str, events: list[dict]) -> None:
        self.url = url
        self.events = events

    def events_of_type(self, report_type: str) -> list[dict]:
        return [e for e in self.events if e.get("$report_type") == report_type]

    def test_reports(self, when: str | None = None) -> list[dict]:
        reports = self.events_of_type("TestReport")
        if when is not None:
            reports = [r for r in reports if r.get("when") == when]
        return reports


def _make_handler(events: list[dict]):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 (pytest/http naming)
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8")
            with contextlib.suppress(json.JSONDecodeError):
                events.append(json.loads(raw))
            body = json.dumps({"status": "success", "session_id": 1}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # silence stub server logging
            pass

    return Handler


@pytest.fixture
def event_server() -> Generator[_CapturedServer, None, None]:
    """Start a stub event-capturing HTTP server for the duration of a test."""
    events: list[dict] = []
    server = HTTPServer(("127.0.0.1", 0), _make_handler(events))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _CapturedServer(f"http://127.0.0.1:{port}", events)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def closed_port_url() -> str:
    """Return a URL on a port that is bound then released (nothing listening)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}"
