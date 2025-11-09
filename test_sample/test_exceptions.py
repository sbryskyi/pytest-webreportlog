"""Tests that demonstrate exceptions in different test phases."""
import pytest


# Setup phase exception
@pytest.fixture
def failing_setup():
    """Fixture that fails during setup."""
    raise RuntimeError("Exception in setup phase")


def test_with_setup_exception(failing_setup):
    """This test should fail during setup."""
    assert True


# Call phase exception
def helper_function():
    """Helper function to create a deeper traceback."""
    raise ValueError("Exception in call phase")


def test_with_call_exception():
    """This test should fail during call phase."""
    helper_function()


# Teardown phase exception
@pytest.fixture
def failing_teardown():
    """Fixture that fails during teardown."""
    yield
    raise RuntimeError("Exception in teardown phase")


def test_with_teardown_exception(failing_teardown):
    """This test should pass but fail during teardown."""
    assert True


# Both call and teardown phase exceptions
@pytest.fixture
def failing_teardown_2():
    """Another fixture that fails during teardown."""
    yield
    raise RuntimeError("Exception in teardown phase")


def test_with_call_and_teardown_exception(failing_teardown_2):
    """This test should fail during both call and teardown."""
    raise ValueError("Exception in call phase")
