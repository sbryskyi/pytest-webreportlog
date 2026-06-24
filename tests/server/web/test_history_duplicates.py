"""Test for duplicate test rows bug in history overview.

This test verifies that the same test (nodeid) with different locations
(due to line number changes) appears only once in the history overview.
"""
import re


def test_history_overview_no_duplicates_for_same_nodeid(api_client):
    """Test that history overview doesn't show duplicates for same test with different locations.

    This test simulates the scenario where a test moves to a different line number
    (e.g., due to code refactoring). The same test (nodeid) should appear only once
    in the history overview, not as separate rows for each location.
    """
    # Upload first session with test at line 10
    jsonl1 = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_example", "location": ["test_sample.py", 10, "test_example"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 1000.0, "stop": 1000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_example", "location": ["test_sample.py", 10, "test_example"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 1000.001, "stop": 1000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_example", "location": ["test_sample.py", 10, "test_example"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 1000.003, "stop": 1000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""
    api_client.stream_jsonl(jsonl1)

    # Upload second session with same test at line 20 (simulating code moved)
    jsonl2 = """{"pytest_version": "8.4.2", "$report_type": "SessionStart"}
{"nodeid": "test_sample.py::test_example", "location": ["test_sample.py", 20, "test_example"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "setup", "duration": 0.001, "start": 2000.0, "stop": 2000.001, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_example", "location": ["test_sample.py", 20, "test_example"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "call", "duration": 0.002, "start": 2000.001, "stop": 2000.003, "sections": [], "$report_type": "TestReport"}
{"nodeid": "test_sample.py::test_example", "location": ["test_sample.py", 20, "test_example"], "keywords": {}, "outcome": "passed", "longrepr": null, "when": "teardown", "duration": 0.001, "start": 2000.003, "stop": 2000.004, "sections": [], "$report_type": "TestReport"}
{"exitstatus": 0, "$report_type": "SessionFinish"}
"""
    api_client.stream_jsonl(jsonl2)

    # Get history overview HTML
    import requests
    response = requests.get(f"{api_client.base_url}/history")
    assert response.status_code == 200
    content = response.text

    nodeid = "test_sample.py::test_example"

    # Count how many times the nodeid appears as a link (each row has one link)
    # Look for the pattern: href="/history/test_sample.py::test_example"
    pattern = rf'href="/history/{re.escape(nodeid)}"'
    matches = re.findall(pattern, content)

    # Should appear exactly once, not twice
    assert len(matches) == 1, (
        f"Expected test '{nodeid}' to appear once in history overview, "
        f"but found {len(matches)} occurrences. This indicates duplicate rows "
        f"for the same test with different locations."
    )
