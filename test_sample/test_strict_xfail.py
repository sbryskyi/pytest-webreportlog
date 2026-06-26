"""Test file with strict xfail scenarios for comparison testing."""

import pytest


# Strict xfail that fails as expected
@pytest.mark.xfail(strict=True, reason="Strict xfail - should fail")
def test_strict_xfail_fails():
    """Strict xfail that fails as expected (good)."""
    assert False, "Expected to fail"


# Strict xfail that unexpectedly passes (becomes a failure!)
@pytest.mark.xfail(strict=True, reason="Strict xfail - unexpectedly passes")
def test_strict_xfail_passes():
    """Strict xfail that passes (becomes a failure due to strict=True)."""
    assert True


# Regular xfail for comparison
@pytest.mark.xfail(reason="Non-strict xfail")
def test_regular_xfail():
    """Regular (non-strict) xfail that fails."""
    assert False


# Normal passing test for comparison
def test_normal_pass_in_strict_module():
    """Regular passing test in strict xfail module."""
    assert True
