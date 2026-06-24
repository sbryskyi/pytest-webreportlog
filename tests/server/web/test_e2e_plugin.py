"""End-to-end: the plugin streams a real run to the live viewer.

Uses the fixture-managed `web_server` (no manual server control) and drives an
inner pytest session through the installed plugin, then asserts the viewer
reflects the run — both the API counts and phase-isolated HTML.
"""
import pytest

from .conftest import APIClient

pytestmark = pytest.mark.web


def test_plugin_streams_run_to_viewer(
    api_client: APIClient, pytester: pytest.Pytester
) -> None:
    pytester.makepyfile(
        """
        import pytest

        def test_pass():
            print("hello from call phase")
            assert True

        def test_fail():
            assert 1 == 2

        @pytest.mark.skip(reason="not today")
        def test_skip():
            pass

        @pytest.fixture
        def boom():
            yield
            raise RuntimeError("teardown blew up")

        def test_teardown_error(boom):
            assert True
        """
    )

    before = {s["id"] for s in api_client.get_sessions()}
    result = pytester.runpytest_subprocess(f"--webreportlog-url={api_client.base_url}")
    # test_pass + test_teardown_error pass, test_fail fails, test_skip skips,
    # and the teardown fixture raises -> one error.
    result.assert_outcomes(passed=2, failed=1, skipped=1, errors=1)

    new_ids = [s["id"] for s in api_client.get_sessions() if s["id"] not in before]
    assert new_ids, "plugin did not create a session on the live server"
    session_id = max(new_ids)

    # API reflects the streamed counts, including the teardown error.
    session = api_client.get_session(session_id)
    assert session["status"] == "completed"
    assert session["passed"] == 2
    assert session["failed"] == 1
    assert session["skipped"] == 1
    assert session["errors"] == 1

    # Viewer HTML shows the teardown-error entry and phase-isolated call output.
    html = api_client.get_session_html(session_id)
    assert "test_teardown_error::teardown" in html
    assert "hello from call phase" in html
