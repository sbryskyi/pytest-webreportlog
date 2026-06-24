"""Tests for template filters."""
from markupsafe import Markup

from app.templates_config import ansi_to_html


def test_ansi_to_html_none_input() -> None:
    result = ansi_to_html(None)
    assert result == ""


def test_ansi_to_html_empty_string() -> None:
    result = ansi_to_html("")
    assert result == ""


def test_ansi_to_html_plain_text() -> None:
    result = ansi_to_html("Hello World")
    assert isinstance(result, Markup)
    assert "Hello World" in str(result)


def test_ansi_to_html_with_color_codes() -> None:
    text_with_ansi = "\033[31mError message\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Error message" in str(result)
    assert "span" in str(result).lower() or "color" in str(result).lower()


def test_ansi_to_html_with_multiple_colors() -> None:
    text_with_ansi = "\033[31mRed\033[0m \033[32mGreen\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Red" in str(result)
    assert "Green" in str(result)


def test_ansi_to_html_with_bold() -> None:
    text_with_ansi = "\033[1mBold text\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Bold text" in str(result)


def test_ansi_to_html_with_underline() -> None:
    text_with_ansi = "\033[4mUnderlined text\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Underlined text" in str(result)


def test_ansi_to_html_complex_ansi_sequence() -> None:
    text_with_ansi = "\033[1m\033[31mFAILED\033[0m test.py::test_example - \033[32mAssertionError\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "FAILED" in str(result)
    assert "test.py::test_example" in str(result)
    assert "AssertionError" in str(result)


def test_ansi_to_html_preserves_newlines() -> None:
    text_with_ansi = "\033[31mLine 1\033[0m\nLine 2"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Line 1" in str(result)
    assert "Line 2" in str(result)
    assert "\n" in str(result) or "<br" in str(result).lower()


def test_ansi_to_html_integer_input() -> None:
    result = ansi_to_html(42)
    assert isinstance(result, Markup)
    assert "42" in str(result)


def test_ansi_to_html_list_input() -> None:
    result = ansi_to_html(["item1", "item2"])
    assert isinstance(result, Markup)
    assert "item1" in str(result)
    assert "item2" in str(result)


def test_ansi_to_html_dict_input() -> None:
    result = ansi_to_html({"key": "value"})
    assert isinstance(result, Markup)
    assert "key" in str(result)
    assert "value" in str(result)


def test_ansi_to_html_returns_markup() -> None:
    result = ansi_to_html("test")
    assert isinstance(result, Markup)


def test_ansi_to_html_pytest_failure_output() -> None:
    pytest_output = """\033[1m\033[31mE       AssertionError: assert 1 == 2\033[0m
\033[1m\033[31mE        +  where 1 = func()\033[0m"""

    result = ansi_to_html(pytest_output)

    assert isinstance(result, Markup)
    assert "AssertionError" in str(result)
    assert "assert 1 == 2" in str(result)
    assert "where 1 = func()" in str(result)


def test_ansi_to_html_pytest_captured_output() -> None:
    captured_output = """\033[1mCaptured stdout\033[0m
\033[32mTest output line 1\033[0m
\033[33mWarning line\033[0m"""

    result = ansi_to_html(captured_output)

    assert isinstance(result, Markup)
    assert "Captured stdout" in str(result)
    assert "Test output line 1" in str(result)
    assert "Warning line" in str(result)


def test_ansi_to_html_background_colors() -> None:
    text_with_ansi = "\033[41mRed background\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Red background" in str(result)


def test_ansi_to_html_256_colors() -> None:
    text_with_ansi = "\033[38;5;208mOrange text\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Orange text" in str(result)


def test_ansi_to_html_rgb_colors() -> None:
    text_with_ansi = "\033[38;2;255;0;0mRGB Red\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "RGB Red" in str(result)


def test_ansi_to_html_mixed_text_and_codes() -> None:
    text = "Plain text \033[31mcolored\033[0m more plain \033[1mbold\033[0m end"
    result = ansi_to_html(text)

    assert isinstance(result, Markup)
    assert "Plain text" in str(result)
    assert "colored" in str(result)
    assert "more plain" in str(result)
    assert "bold" in str(result)
    assert "end" in str(result)


def test_ansi_to_html_empty_ansi_codes() -> None:
    text_with_ansi = "\033[0m\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)


def test_ansi_to_html_unicode_with_ansi() -> None:
    text_with_ansi = "\033[32m✓ Test passed\033[0m"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "✓" in str(result)
    assert "Test passed" in str(result)


def test_ansi_to_html_long_text() -> None:
    long_text = "\n".join([
        f"\033[3{i % 8}mLine {i}\033[0m"
        for i in range(100)
    ])
    result = ansi_to_html(long_text)

    assert isinstance(result, Markup)
    assert "Line 0" in str(result)
    assert "Line 99" in str(result)


def test_ansi_to_html_malformed_ansi_codes() -> None:
    text_with_ansi = "\033[Text with incomplete code"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "ext with incomplete code" in str(result)


def test_ansi_to_html_consecutive_resets() -> None:
    text_with_ansi = "\033[31mRed\033[0m\033[0m\033[0m Normal"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Red" in str(result)
    assert "Normal" in str(result)


def test_ansi_to_html_no_reset_code() -> None:
    text_with_ansi = "\033[31mRed text without reset"
    result = ansi_to_html(text_with_ansi)

    assert isinstance(result, Markup)
    assert "Red text without reset" in str(result)
