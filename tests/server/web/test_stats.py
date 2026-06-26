"""Tests for the /api/stats endpoint and the database-size footer display."""

from .conftest import APIClient


def test_stats_endpoint_reports_size_and_counts(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    api_client.stream_jsonl(simple_passing_jsonl)

    resp = api_client.session.get(f"{api_client.base_url}/api/stats")
    assert resp.status_code == 200

    data = resp.json()
    assert data["database"]["path"]
    assert data["database"]["size_bytes"] > 0
    assert data["database"]["size_human"] != "n/a"
    assert data["sessions"] >= 1
    assert data["test_reports"] >= 1


def test_footer_shows_database_size(api_client: APIClient) -> None:
    html = api_client.get_index_html()
    assert "Database:" in html
    # The human-readable size from the API should appear in the footer.
    size_human = api_client.session.get(f"{api_client.base_url}/api/stats").json()[
        "database"
    ]["size_human"]
    assert size_human in html


def test_stats_includes_cap_fields(api_client: APIClient) -> None:
    """With no cap configured, the cap fields are present but null/false."""
    db = api_client.session.get(f"{api_client.base_url}/api/stats").json()["database"]
    assert "max_size_bytes" in db
    assert db["max_size_bytes"] is None
    assert db["max_size_human"] is None
    assert db["over_cap"] is False


def test_prune_requires_a_cap(api_client: APIClient) -> None:
    """No body cap and no env cap -> 400 (and nothing is mutated)."""
    resp = api_client.session.post(f"{api_client.base_url}/api/prune", json={})
    assert resp.status_code == 400


def test_prune_noop_under_huge_cap(
    api_client: APIClient, simple_passing_jsonl: str
) -> None:
    """A cap far above the current size is a safe no-op with a clear report."""
    api_client.stream_jsonl(simple_passing_jsonl)
    resp = api_client.session.post(
        f"{api_client.base_url}/api/prune", json={"max_size": "1TB"}
    )
    assert resp.status_code == 200
    report = resp.json()
    assert report["under_cap"] is True
    assert report["stripped"] == [] and report["deleted"] == []
    assert report["before_bytes"] == report["after_bytes"]
