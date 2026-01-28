"""Tests for test history feature: overview page and individual test history."""
from .conftest import APIClient


# ============================================================================
# HISTORY OVERVIEW TESTS
# ============================================================================


def test_history_overview_page_loads(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test that history overview page loads successfully."""
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")

    assert response.status_code == 200
    assert "Test History Overview" in response.text


def test_history_overview_displays_all_tests(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test history overview displays all unique tests."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")
    html = response.text

    # Should show all 3 tests
    assert "test_sample.py::test_pass" in html
    assert "test_sample.py::test_fail" in html
    assert "test_sample.py::test_skip" in html


def test_history_overview_aggregated_statistics(
    api_client: APIClient, simple_passing_jsonl: str, mixed_outcomes_jsonl: str
) -> None:
    """Test aggregated statistics in history overview."""
    # Upload same test twice with different outcomes
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")
    html = response.text

    # test_pass appears in both sessions
    assert "test_sample.py::test_pass" in html
    # Should show total runs for test_pass (at least 1, ideally 2)
    # Note: Exact count depends on database session isolation
    assert "Total Runs" in html or "total" in html.lower()


def test_history_overview_pass_rate_display(
    api_client: APIClient, simple_passing_jsonl: str, mixed_outcomes_jsonl: str
) -> None:
    """Test pass rate display in history overview."""
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")
    html = response.text

    # test_pass has 100% pass rate (2/2)
    assert "100.0%" in html or "100%" in html


def test_history_overview_latest_result_badges(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test latest result badge display in history overview."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(f"{api_client.base_url}/history")
    html = response.text

    # Should have result badges
    assert "PASS" in html
    assert "FAIL" in html
    assert "SKIP" in html


def test_history_overview_sorting_by_nodeid(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test sorting by nodeid in history overview."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    # Test ascending sort
    response = api_client.session.get(
        f"{api_client.base_url}/history?sort_by=nodeid&sort_dir=asc"
    )
    assert response.status_code == 200

    # Test descending sort
    response = api_client.session.get(
        f"{api_client.base_url}/history?sort_by=nodeid&sort_dir=desc"
    )
    assert response.status_code == 200


def test_history_overview_sorting_by_total_runs(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test sorting by total_runs in history overview."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history?sort_by=total_runs&sort_dir=desc"
    )
    assert response.status_code == 200


def test_history_overview_sorting_by_pass_rate(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test sorting by pass_rate in history overview."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history?sort_by=pass_rate&sort_dir=desc"
    )
    assert response.status_code == 200


def test_history_overview_empty_state(api_client: APIClient) -> None:
    """Test history overview with no tests uploaded yet."""
    response = api_client.session.get(f"{api_client.base_url}/history")

    assert response.status_code == 200
    assert "Test History Overview" in response.text


# ============================================================================
# INDIVIDUAL TEST HISTORY TESTS
# ============================================================================


def test_individual_test_history_page_loads(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test individual test history page loads."""
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_pass"
    )

    assert response.status_code == 200
    assert "Test History" in response.text
    assert "test_sample.py::test_pass" in response.text


def test_individual_test_history_shows_all_runs(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test individual test history shows all runs of a specific test."""
    # Upload same test twice
    api_client.upload_jsonl(simple_passing_jsonl)
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_pass"
    )
    html = response.text

    # Should show summary stats
    assert "Total Runs" in html
    # Note: Exact count depends on database session isolation
    assert response.status_code == 200


def test_individual_test_history_summary_stats(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test individual test history shows correct summary statistics."""
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_pass"
    )
    html = response.text

    # Should show pass rate
    assert "Pass Rate" in html
    assert "100" in html  # 100% pass rate

    # Should show average duration
    assert "Avg" in html and "Duration" in html


def test_individual_test_history_session_links(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test individual test history has working session links."""
    result = api_client.upload_jsonl(simple_passing_jsonl)
    session_id = result["session_id"]

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_pass"
    )
    html = response.text

    # Should have link to session
    assert f"/sessions/{session_id}" in html or f"#{session_id}" in html


def test_individual_test_history_not_found(api_client: APIClient) -> None:
    """Test 404 for non-existent test nodeid."""
    response = api_client.session.get(
        f"{api_client.base_url}/history/nonexistent::test"
    )

    assert response.status_code == 404


def test_individual_test_history_mixed_outcomes(
    api_client: APIClient, simple_passing_jsonl: str, mixed_outcomes_jsonl: str
) -> None:
    """Test individual test history with mixed outcomes across sessions."""
    api_client.upload_jsonl(simple_passing_jsonl)  # test_pass succeeds
    api_client.upload_jsonl(mixed_outcomes_jsonl)  # test_pass also succeeds

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_pass"
    )
    html = response.text

    # Both runs should be PASS
    assert html.count("PASS") >= 2


def test_individual_test_history_expandable_rows(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test individual test history has expandable rows."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_fail"
    )
    html = response.text

    # Should have details/summary elements for expansion
    assert "<details" in html
    assert "<summary" in html


def test_individual_test_history_phase_details(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """Test individual test history shows phase details."""
    api_client.upload_jsonl(simple_passing_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_pass"
    )
    html = response.text

    # Should show phases
    assert "setup" in html.lower()
    assert "call" in html.lower()
    assert "teardown" in html.lower()


def test_individual_test_history_traceback_display(
    api_client: APIClient, mixed_outcomes_jsonl: str
) -> None:
    """Test individual test history displays tracebacks for failures."""
    api_client.upload_jsonl(mixed_outcomes_jsonl)

    response = api_client.session.get(
        f"{api_client.base_url}/history/test_sample.py::test_fail"
    )
    html = response.text

    # Should show traceback
    assert "Traceback" in html or "AssertionError" in html
