"""Configuration for testing pytest report generation."""

import pytest
from pytest import Pytester


# Configuration fixtures - create pytest.ini for different report types
@pytest.fixture
def junit_config(pytester: Pytester) -> Pytester:
    """Configure pytest with JUnit XML output."""
    pytester.makeini(
        """
        [pytest]
        addopts = --junit-xml=junit.xml
        """
    )
    return pytester


@pytest.fixture
def junit_config_with_capture(pytester: Pytester) -> Pytester:
    """Configure pytest with JUnit XML output and log capture enabled."""
    pytester.makeini(
        """
        [pytest]
        addopts = --junit-xml=junit.xml
        junit_logging = all
        junit_log_passing_tests = True
        log_cli_level = INFO
        """
    )
    return pytester


@pytest.fixture
def html_config(pytester: Pytester) -> Pytester:
    """Configure pytest with HTML report output."""
    pytester.makeini(
        """
        [pytest]
        addopts =
            --html=report.html
            --self-contained-html
        """
    )
    return pytester


# Test content fixtures - create test files with different scenarios
@pytest.fixture
def simple_test_content(pytester: Pytester) -> Pytester:
    """Create a simple passing test file."""
    pytester.makepyfile(
        """
        def test_pass():
            assert True
        """
    )
    return pytester


@pytest.fixture
def multiple_test_content(pytester: Pytester) -> Pytester:
    """Create multiple passing tests."""
    pytester.makepyfile(
        """
        def test_one():
            assert True

        def test_two():
            assert 1 + 1 == 2
        """
    )
    return pytester


@pytest.fixture
def mixed_test_content(pytester: Pytester) -> Pytester:
    """Create tests with mixed outcomes (pass, fail, skip)."""
    pytester.makepyfile(
        """
        import pytest

        def test_pass():
            assert True

        def test_fail():
            assert False, "Intentional failure"

        @pytest.mark.skip(reason="Testing skip")
        def test_skip():
            pass
        """
    )
    return pytester


@pytest.fixture
def timing_test_content(pytester: Pytester) -> Pytester:
    """Create a test that takes measurable time."""
    pytester.makepyfile(
        """
        def test_timing():
            import time
            time.sleep(0.01)
            assert True
        """
    )
    return pytester


@pytest.fixture
def exception_in_setup_content(pytester: Pytester) -> Pytester:
    """Create a test that raises exception during setup phase."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def failing_setup():
            raise RuntimeError("Exception in setup phase")

        def test_with_setup_exception(failing_setup):
            assert True
        """
    )
    return pytester


@pytest.fixture
def exception_in_call_content(pytester: Pytester) -> Pytester:
    """Create a test that raises exception during call phase."""
    pytester.makepyfile(
        """
        def helper_function():
            raise ValueError("Exception in call phase")

        def test_with_call_exception():
            helper_function()
        """
    )
    return pytester


@pytest.fixture
def exception_in_teardown_content(pytester: Pytester) -> Pytester:
    """Create a test that raises exception during teardown phase."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def failing_teardown():
            yield
            raise RuntimeError("Exception in teardown phase")

        def test_with_teardown_exception(failing_teardown):
            assert True
        """
    )
    return pytester


@pytest.fixture
def exception_in_call_and_teardown_content(pytester: Pytester) -> Pytester:
    """Create a test that raises exceptions in both call and teardown phases."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def failing_teardown():
            yield
            raise RuntimeError("Exception in teardown phase")

        def test_with_call_and_teardown_exception(failing_teardown):
            raise ValueError("Exception in call phase")
        """
    )
    return pytester


@pytest.fixture
def logs_in_setup_content(pytester: Pytester) -> Pytester:
    """Create a test that produces logs and stdout during setup phase."""
    pytester.makepyfile(
        """
        import pytest
        import logging

        @pytest.fixture
        def logging_setup():
            print("STDOUT in setup phase")
            logging.warning("WARNING in setup phase")
            logging.info("INFO in setup phase")

        def test_with_setup_logs(logging_setup):
            assert True
        """
    )
    return pytester


@pytest.fixture
def logs_in_call_content(pytester: Pytester) -> Pytester:
    """Create a test that produces logs and stdout during call phase."""
    pytester.makepyfile(
        """
        import logging

        def test_with_call_logs():
            print("STDOUT in call phase")
            logging.warning("WARNING in call phase")
            logging.info("INFO in call phase")
            assert True
        """
    )
    return pytester


@pytest.fixture
def logs_in_teardown_content(pytester: Pytester) -> Pytester:
    """Create a test that produces logs and stdout during teardown phase."""
    pytester.makepyfile(
        """
        import pytest
        import logging

        @pytest.fixture
        def logging_teardown():
            yield
            print("STDOUT in teardown phase")
            logging.warning("WARNING in teardown phase")
            logging.info("INFO in teardown phase")

        def test_with_teardown_logs(logging_teardown):
            assert True
        """
    )
    return pytester


@pytest.fixture
def logs_in_all_phases_content(pytester: Pytester) -> Pytester:
    """Create a test that produces logs and stdout in all phases."""
    pytester.makepyfile(
        """
        import pytest
        import logging

        @pytest.fixture
        def logging_all_phases():
            print("STDOUT in setup phase")
            logging.warning("WARNING in setup phase")
            yield
            print("STDOUT in teardown phase")
            logging.warning("WARNING in teardown phase")

        def test_with_all_phase_logs(logging_all_phases):
            print("STDOUT in call phase")
            logging.warning("WARNING in call phase")
            assert True
        """
    )
    return pytester


@pytest.fixture
def xfail_test_content(pytester: Pytester) -> Pytester:
    """Create a test expected to fail (and does fail)."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.xfail(reason="Expected to fail")
        def test_xfail():
            assert False, "This test is expected to fail"
        """
    )
    return pytester


@pytest.fixture
def xpass_test_content(pytester: Pytester) -> Pytester:
    """Create a test expected to fail (but passes unexpectedly)."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.xfail(reason="Expected to fail but will pass")
        def test_xpass():
            assert True
        """
    )
    return pytester


@pytest.fixture
def strict_xfail_test_content(pytester: Pytester) -> Pytester:
    """Create a strict xfail test (counts as failure if it passes)."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.xfail(strict=True, reason="Strict xfail")
        def test_strict_xfail():
            assert False
        """
    )
    return pytester


@pytest.fixture
def xfail_xpass_mixed_content(pytester: Pytester) -> Pytester:
    """Create tests with mix of xfail and xpass outcomes."""
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.xfail(reason="Expected to fail")
        def test_xfail_one():
            assert False, "Expected failure"

        @pytest.mark.xfail(reason="Expected to fail but passes")
        def test_xpass_one():
            assert True

        def test_normal_pass():
            assert True

        @pytest.mark.xfail(strict=True, reason="Strict xfail")
        def test_strict_xfail_one():
            assert False
        """
    )
    return pytester
