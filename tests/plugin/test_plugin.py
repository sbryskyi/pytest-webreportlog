"""Behavioral tests for the pytest-webreportlog streaming plugin.

Each test runs an inner pytest session (via pytester, in a subprocess so the
installed plugin loads through its entry point) pointed at a stub event server,
then asserts on the events the plugin streamed.
"""
import pytest

pytestmark = pytest.mark.plugin


def test_streams_full_event_sequence(pytester: pytest.Pytester, event_server) -> None:
    pytester.makepyfile(
        """
        def test_pass():
            assert True
        """
    )
    result = pytester.runpytest_subprocess(f"--webreportlog-url={event_server.url}")
    result.assert_outcomes(passed=1)

    types = [e.get("$report_type") for e in event_server.events]
    assert types[0] == "SessionStart"
    assert types[-1] == "SessionFinish"
    assert {"setup", "call", "teardown"} <= {
        r["when"] for r in event_server.test_reports()
    }


def test_phase_section_isolation(pytester: pytest.Pytester, event_server) -> None:
    """Each phase report carries only the captured output for that phase."""
    pytester.makepyfile(
        """
        import logging
        import pytest

        @pytest.fixture
        def noisy():
            print("STDOUT setup")
            logging.warning("LOG setup")
            yield
            print("STDOUT teardown")
            logging.warning("LOG teardown")

        def test_logs(noisy):
            print("STDOUT call")
            logging.warning("LOG call")
            assert True
        """
    )
    result = pytester.runpytest_subprocess(f"--webreportlog-url={event_server.url}")
    result.assert_outcomes(passed=1)

    for when in ("setup", "call", "teardown"):
        report = event_server.test_reports(when)[0]
        headers = [head for head, _ in report.get("sections", [])]
        # Every section attached to this phase must belong to this phase.
        assert headers, f"expected captured sections for {when} phase"
        assert all(when in head for head in headers), (
            f"{when} report leaked foreign sections: {headers}"
        )


def test_failure_is_streamed_with_longrepr(
    pytester: pytest.Pytester, event_server
) -> None:
    pytester.makepyfile(
        """
        def test_fail():
            assert 1 == 2
        """
    )
    result = pytester.runpytest_subprocess(f"--webreportlog-url={event_server.url}")
    result.assert_outcomes(failed=1)

    call = event_server.test_reports("call")[0]
    assert call["outcome"] == "failed"
    assert call.get("longrepr")


def test_xfail_is_streamed(pytester: pytest.Pytester, event_server) -> None:
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.xfail(reason="expected")
        def test_xfail():
            assert False
        """
    )
    result = pytester.runpytest_subprocess(f"--webreportlog-url={event_server.url}")
    result.assert_outcomes(xfailed=1)

    call = event_server.test_reports("call")[0]
    assert "xfail" in call.get("keywords", {})


def test_exclude_logs_on_passed(pytester: pytest.Pytester, event_server) -> None:
    pytester.makepyfile(
        """
        import logging

        def test_pass():
            logging.warning("LOG call")
            print("STDOUT call")
            assert True
        """
    )
    result = pytester.runpytest_subprocess(
        f"--webreportlog-url={event_server.url}",
        "--webreportlog-exclude-logs-on-passed",
    )
    result.assert_outcomes(passed=1)

    call = event_server.test_reports("call")[0]
    headers = [head for head, _ in call.get("sections", [])]
    assert "Captured log call" not in headers


def test_inert_without_url(pytester: pytest.Pytester, event_server) -> None:
    """With no --webreportlog-url, the plugin streams nothing."""
    pytester.makepyfile(
        """
        def test_pass():
            assert True
        """
    )
    result = pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1)
    assert event_server.events == []


def test_fail_soft_when_server_unreachable(
    pytester: pytest.Pytester, closed_port_url: str
) -> None:
    """A down viewer must not break the run; one warning is surfaced."""
    pytester.makepyfile(
        """
        def test_pass():
            assert True
        """
    )
    result = pytester.runpytest_subprocess(
        f"--webreportlog-url={closed_port_url}",
        "--webreportlog-timeout=1",
    )
    # The user's suite still passes.
    result.assert_outcomes(passed=1)
    assert result.ret == 0
    # The failure is surfaced (warning + terminal summary).
    result.stdout.fnmatch_lines(["*webreportlog*"])
