"""Test file with various skip scenarios for comparison testing."""
import pytest
import sys


# Decorator skip with reason
@pytest.mark.skip(reason="Unconditionally skipped test")
def test_skip_decorator():
    """Test skipped via decorator."""
    assert False, "This should never run"


# Conditional skip based on platform
@pytest.mark.skipif(sys.platform == "win32", reason="Not supported on Windows")
def test_skip_conditional_platform():
    """Test conditionally skipped based on platform."""
    assert True


# Conditional skip based on Python version
@pytest.mark.skipif(sys.version_info < (3, 6), reason="Requires Python 3.6+")
def test_skip_conditional_version():
    """Test conditionally skipped based on Python version."""
    assert True


# Imperative skip in test body
def test_skip_imperative():
    """Test that skips during execution."""
    if True:  # Condition to trigger skip
        pytest.skip("Skipped during test execution")
    assert False, "This should never execute"


# Skip with condition
def test_skip_with_condition():
    """Test that conditionally skips during execution."""
    some_condition = True
    if some_condition:
        pytest.skip("Condition not met, skipping test")
    assert True


# Normal passing test for comparison
def test_normal_pass_in_skip_module():
    """Regular passing test in skip module."""
    assert True


# Skip in setup phase
@pytest.fixture
def skipping_fixture():
    """Fixture that skips during setup."""
    pytest.skip("Skipped in fixture setup")
    yield


def test_skip_in_fixture(skipping_fixture):
    """Test that gets skipped via fixture."""
    assert False, "This should never run"
