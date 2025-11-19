"""Test file with parametrized tests for comparison testing."""
import pytest


# Simple parametrization
@pytest.mark.parametrize("value", [1, 2, 3])
def test_parametrize_simple(value):
    """Parametrized test with simple values."""
    assert value > 0


# Parametrization with tuples
@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 3),
    (3, 4),
])
def test_parametrize_tuples(input, expected):
    """Parametrized test with input/output pairs."""
    assert input + 1 == expected


# Parametrization with some failures
@pytest.mark.parametrize("value,should_pass", [
    (1, True),
    (2, True),
    (3, False),  # This one will fail
    (4, True),
])
def test_parametrize_mixed_outcomes(value, should_pass):
    """Parametrized test with mixed pass/fail outcomes."""
    if should_pass:
        assert value > 0
    else:
        assert value > 10  # This will fail for value=3


# Multiple parameters
@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", [3, 4])
def test_parametrize_multiple(x, y):
    """Parametrized test with multiple decorators (creates cartesian product)."""
    assert x * y > 0


# Parametrize with IDs
@pytest.mark.parametrize("test_input,expected", [
    ("3+5", 8),
    ("2+4", 6),
    ("6*9", 54),
], ids=["sum1", "sum2", "product"])
def test_parametrize_with_ids(test_input, expected):
    """Parametrized test with custom IDs."""
    assert eval(test_input) == expected
