#!/usr/bin/env python3
"""Test SSE (Server-Sent Events) functionality."""
import json
import subprocess
import threading
import time

import requests


def subscribe_to_sse(session_id, events_received):
    """Subscribe to SSE endpoint and collect events."""
    url = f"http://127.0.0.1:8006/api/stream/{session_id}"
    print(f"[SSE] Subscribing to {url}")

    try:
        response = requests.get(url, stream=True, timeout=30)
        print(f"[SSE] Connection established, status={response.status_code}")

        for line in response.iter_lines(decode_unicode=True):
            if line:
                print(f"[SSE] Received: {line}")
                events_received.append(line)

                # Check if session finished
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])  # Remove 'data: ' prefix
                        if data.get('type') == 'session_finish':
                            print("[SSE] Session finished, closing connection")
                            break
                    except json.JSONDecodeError:
                        pass

    except requests.exceptions.RequestException as e:
        print(f"[SSE] Error: {e}")


def run_pytest():
    """Run pytest with streaming endpoint."""
    print("[PYTEST] Starting pytest...")
    time.sleep(2)  # Give SSE time to connect

    result = subprocess.run(
        [
            "uv", "run", "pytest",
            "test_sample/test_module_a.py::test_pass",
            "-v",
            "--webreportlog-url=http://127.0.0.1:8006"
        ],
        cwd="/home/sergii/p/pytest-webreportlog",
        capture_output=True,
        text=True
    )

    print(f"[PYTEST] Exit code: {result.returncode}")
    print(f"[PYTEST] Output:\n{result.stdout}")
    if result.stderr:
        print(f"[PYTEST] Errors:\n{result.stderr}")


def main():
    """Main test function."""
    print("=" * 60)
    print("Testing SSE (Server-Sent Events) functionality")
    print("=" * 60)

    # First, run pytest to get a session ID
    print("\n[STEP 1] Creating initial session to get session ID...")
    subprocess.run(
        [
            "uv", "run", "pytest",
            "test_sample/test_module_a.py::test_pass",
            "-v",
            "--webreportlog-url=http://127.0.0.1:8006"
        ],
        cwd="/home/sergii/p/pytest-webreportlog",
        capture_output=True,
        text=True
    )

    # Get the session ID from API
    response = requests.get("http://127.0.0.1:8006/api/sessions")
    sessions = response.json()

    if not sessions:
        print("[ERROR] No sessions found!")
        return

    next_session_id = max(s['id'] for s in sessions) + 1
    print(f"\n[STEP 2] Next session will be ID {next_session_id}")

    # Start SSE subscriber in background
    events_received = []
    sse_thread = threading.Thread(
        target=subscribe_to_sse,
        args=(next_session_id, events_received)
    )
    sse_thread.daemon = True
    sse_thread.start()

    # Give SSE time to connect
    time.sleep(1)

    # Run pytest with streaming
    print("\n[STEP 3] Running pytest with streaming...")
    run_pytest()

    # Wait for SSE thread to finish
    sse_thread.join(timeout=10)

    # Summary
    print("\n" + "=" * 60)
    print(f"Test complete! Received {len(events_received)} SSE events:")
    print("=" * 60)
    for i, event in enumerate(events_received, 1):
        print(f"{i}. {event}")

    # Verify we received events
    if len(events_received) > 0:
        print("\n✓ SSE functionality is working!")
        return 0
    else:
        print("\n✗ No SSE events received - SSE may not be working")
        return 1


if __name__ == "__main__":
    exit(main())
