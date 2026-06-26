"""Tests for the metadata attribute filter chips on the index and history views."""

from .conftest import APIClient
from .jsonl_builder import JSONLBuilder


def _run(api_client: APIClient, nodeid: str, outcome: str, metadata: dict) -> None:
    """Stream one session containing a single test for `nodeid` with metadata."""
    jsonl = (
        JSONLBuilder()
        .session_start(metadata=metadata)
        .test(nodeid)
        .setup()
        .call(outcome=outcome)
        .teardown()
        .session_finish(exitstatus=0 if outcome == "passed" else 1)
        .build()
    )
    api_client.stream_jsonl(jsonl)


def test_history_detail_renders_attribute_chips(api_client: APIClient) -> None:
    """The per-test history page exposes scalar metadata as filter chips."""
    nodeid = "test_sample.py::test_attr_history"
    _run(api_client, nodeid, "passed", {"Python": "3.11", "Platform": "linux"})
    _run(
        api_client,
        nodeid,
        "failed",
        {"Python": "3.12", "Platform": "linux", "Packages": {"pytest": "8"}},
    )

    html = api_client.session.get(f"{api_client.base_url}/history/{nodeid}").text

    assert 'id="history-facets"' in html
    assert 'data-facet-attr="Python"' in html
    assert 'data-facet-value="3.11"' in html
    assert 'data-facet-value="3.12"' in html
    assert 'data-facet-attr="Platform"' in html
    # Nested dicts (Packages) are NOT turned into chips.
    assert 'data-facet-attr="Packages"' not in html
    # Each run row carries the per-row facet data + its outcome for live counts.
    assert "data-facets=" in html
    assert 'data-outcome="passed"' in html
    assert 'data-outcome="failed"' in html


def test_index_renders_env_facets(api_client: APIClient) -> None:
    """The session list exposes scalar metadata as filter chips."""
    _run(api_client, "test_sample.py::test_idx_attr", "passed", {"Browser": "firefox"})

    html = api_client.get_index_html()

    assert 'id="env-facets"' in html
    assert 'data-facet-attr="Browser"' in html
    assert 'data-facet-value="firefox"' in html
    assert "data-facets=" in html


def test_facet_values_are_escaped(api_client: APIClient) -> None:
    """A metadata value containing markup cannot break out of the page."""
    nodeid = "test_sample.py::test_escape_attr"
    _run(api_client, nodeid, "passed", {"Note": "</script><b>x</b>"})

    html = api_client.session.get(f"{api_client.base_url}/history/{nodeid}").text

    # The raw payload must never appear unescaped (tojson + autoescape handle it).
    assert "</script><b>x</b>" not in html
