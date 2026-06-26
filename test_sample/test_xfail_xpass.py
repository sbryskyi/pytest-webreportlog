"""Test file with xfail and xpass outcomes for comparison testing."""

import pytest


@pytest.fixture
def failing_setup():
    assert False
    yield


@pytest.fixture
def failing_xfailed_setup():
    pytest.xfail(reason="Directive")
    yield


@pytest.mark.xfail(reason="Expected to fail")
def test_xfail():
    """Test expected to fail (and does)."""
    assert False, "This test is expected to fail"


@pytest.mark.xfail(reason="Expected to fail but passes")
def test_xpass():
    """Test expected to fail but passes unexpectedly."""
    assert True


def test_normal_pass():
    """Regular passing test."""
    assert True


@pytest.mark.xfail(reason="disabled", run=False)
def test_xfail_run_false():
    """Test expected to fail and disabled"""
    assert True


@pytest.mark.xfail(reason="Expected to fail")
def test_fail_with_setup_error(failing_setup):
    """Test expected to fail but passes unexpectedly."""
    assert True


def test_fail_with_xfail_in_setup(failing_xfailed_setup):
    """Test expected to fail but passes unexpectedly."""
    assert True


@pytest.mark.xfail(reason="Expected to fail")
def test_fail_with_xfail_in_setup_and_mark(failing_xfailed_setup):
    """Test expected to fail but passes unexpectedly."""
    assert True
