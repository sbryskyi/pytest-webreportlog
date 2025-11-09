"""Test file with xfail and xpass outcomes for comparison testing."""
import pytest


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
