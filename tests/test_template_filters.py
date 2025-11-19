"""Tests for template filters."""
import pytest
from markupsafe import Markup
from src.app.main import strip_ansi


def test_strip_ansi_none_input():
    """Test strip_ansi with None input."""
    result = strip_ansi(None)
    assert result == ""


def test_strip_ansi_empty_string():
    """Test strip_ansi with empty string."""
    result = strip_ansi("")
    assert result == ""


def test_strip_ansi_plain_text():
    """Test strip_ansi with plain text (no ANSI codes)."""
    result = strip_ansi("Hello World")
    assert isinstance(result, Markup)
    assert "Hello World" in str(result)


def test_strip_ansi_with_color_codes():
    """Test strip_ansi converts ANSI color codes to HTML."""
    # ANSI red color: \033[31m
    text_with_ansi = "\033[31mError message\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    # Should contain the text
    assert "Error message" in str(result)
    # Should contain HTML color styling (ansi2html adds span tags with styles)
    assert "span" in str(result).lower() or "color" in str(result).lower()


def test_strip_ansi_with_multiple_colors():
    """Test strip_ansi with multiple ANSI codes."""
    # Red, then green
    text_with_ansi = "\033[31mRed\033[0m \033[32mGreen\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Red" in str(result)
    assert "Green" in str(result)


def test_strip_ansi_with_bold():
    """Test strip_ansi with ANSI bold code."""
    text_with_ansi = "\033[1mBold text\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Bold text" in str(result)


def test_strip_ansi_with_underline():
    """Test strip_ansi with ANSI underline code."""
    text_with_ansi = "\033[4mUnderlined text\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Underlined text" in str(result)


def test_strip_ansi_complex_ansi_sequence():
    """Test strip_ansi with complex ANSI sequences."""
    # Pytest-like output with multiple colors and styles
    text_with_ansi = "\033[1m\033[31mFAILED\033[0m test.py::test_example - \033[32mAssertionError\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "FAILED" in str(result)
    assert "test.py::test_example" in str(result)
    assert "AssertionError" in str(result)


def test_strip_ansi_preserves_newlines():
    """Test that strip_ansi preserves newlines."""
    text_with_ansi = "\033[31mLine 1\033[0m\nLine 2"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Line 1" in str(result)
    assert "Line 2" in str(result)
    # Newlines should be preserved
    assert "\n" in str(result) or "<br" in str(result).lower()


def test_strip_ansi_integer_input():
    """Test strip_ansi with integer input."""
    result = strip_ansi(42)
    assert isinstance(result, Markup)
    assert "42" in str(result)


def test_strip_ansi_list_input():
    """Test strip_ansi with list input."""
    result = strip_ansi(["item1", "item2"])
    assert isinstance(result, Markup)
    # Should convert list to string
    assert "item1" in str(result)
    assert "item2" in str(result)


def test_strip_ansi_dict_input():
    """Test strip_ansi with dict input."""
    result = strip_ansi({"key": "value"})
    assert isinstance(result, Markup)
    # Should convert dict to string
    assert "key" in str(result)
    assert "value" in str(result)


def test_strip_ansi_returns_markup():
    """Test that strip_ansi returns Markup type for safe HTML rendering."""
    result = strip_ansi("test")
    assert isinstance(result, Markup)


def test_strip_ansi_pytest_failure_output():
    """Test strip_ansi with realistic pytest failure output."""
    pytest_output = """\033[1m\033[31mE       AssertionError: assert 1 == 2\033[0m
\033[1m\033[31mE        +  where 1 = func()\033[0m"""

    result = strip_ansi(pytest_output)

    assert isinstance(result, Markup)
    assert "AssertionError" in str(result)
    assert "assert 1 == 2" in str(result)
    assert "where 1 = func()" in str(result)


def test_strip_ansi_pytest_captured_output():
    """Test strip_ansi with pytest captured output."""
    captured_output = """\033[1mCaptured stdout\033[0m
\033[32mTest output line 1\033[0m
\033[33mWarning line\033[0m"""

    result = strip_ansi(captured_output)

    assert isinstance(result, Markup)
    assert "Captured stdout" in str(result)
    assert "Test output line 1" in str(result)
    assert "Warning line" in str(result)


def test_strip_ansi_background_colors():
    """Test strip_ansi with ANSI background colors."""
    text_with_ansi = "\033[41mRed background\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Red background" in str(result)


def test_strip_ansi_256_colors():
    """Test strip_ansi with 256-color ANSI codes."""
    text_with_ansi = "\033[38;5;208mOrange text\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Orange text" in str(result)


def test_strip_ansi_rgb_colors():
    """Test strip_ansi with RGB ANSI codes."""
    text_with_ansi = "\033[38;2;255;0;0mRGB Red\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "RGB Red" in str(result)


def test_strip_ansi_mixed_text_and_codes():
    """Test strip_ansi with mixed plain text and ANSI codes."""
    text = "Plain text \033[31mcolored\033[0m more plain \033[1mbold\033[0m end"
    result = strip_ansi(text)

    assert isinstance(result, Markup)
    assert "Plain text" in str(result)
    assert "colored" in str(result)
    assert "more plain" in str(result)
    assert "bold" in str(result)
    assert "end" in str(result)


def test_strip_ansi_empty_ansi_codes():
    """Test strip_ansi with text containing only reset codes."""
    text_with_ansi = "\033[0m\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)


def test_strip_ansi_unicode_with_ansi():
    """Test strip_ansi with unicode characters and ANSI codes."""
    text_with_ansi = "\033[32m✓ Test passed\033[0m"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "✓" in str(result)
    assert "Test passed" in str(result)


def test_strip_ansi_long_text():
    """Test strip_ansi with long text containing multiple ANSI sequences."""
    long_text = "\n".join([
        f"\033[3{i % 8}mLine {i}\033[0m"
        for i in range(100)
    ])
    result = strip_ansi(long_text)

    assert isinstance(result, Markup)
    assert "Line 0" in str(result)
    assert "Line 99" in str(result)


def test_strip_ansi_malformed_ansi_codes():
    """Test strip_ansi handles malformed ANSI codes gracefully."""
    # Incomplete ANSI code - ansi2html may consume the first character as part of the code
    text_with_ansi = "\033[Text with incomplete code"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    # Should still return something (ansi2html may strip the 'T')
    assert "ext with incomplete code" in str(result)


def test_strip_ansi_consecutive_resets():
    """Test strip_ansi with consecutive reset codes."""
    text_with_ansi = "\033[31mRed\033[0m\033[0m\033[0m Normal"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Red" in str(result)
    assert "Normal" in str(result)


def test_strip_ansi_no_reset_code():
    """Test strip_ansi when ANSI code is not reset."""
    text_with_ansi = "\033[31mRed text without reset"
    result = strip_ansi(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Red text without reset" in str(result)
