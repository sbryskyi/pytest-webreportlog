"""Tests for formatter module."""

from webreportlog_server.formatter import format_longrepr


def test_format_longrepr_none() -> None:
    """Test formatting None longrepr."""
    result = format_longrepr(None)
    assert result is None


def test_format_longrepr_empty_string() -> None:
    """Test formatting empty string."""
    result = format_longrepr("")
    assert result is None


def test_format_longrepr_simple_string() -> None:
    """Test formatting simple string longrepr."""
    longrepr = "AssertionError: test failed"
    result = format_longrepr(longrepr)
    assert result == "AssertionError: test failed"


def test_format_longrepr_multiline_string() -> None:
    """Test formatting multiline string longrepr."""
    longrepr = "def test_fail():\n>   assert False\nE   AssertionError"
    result = format_longrepr(longrepr)
    assert result == longrepr


def test_format_longrepr_dict_with_reprtraceback() -> None:
    """Test formatting dict with full reprtraceback structure."""
    longrepr = {
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": [
                            "def test_fail():",
                            ">   assert False",
                            "E   AssertionError: test failed"
                        ],
                        "reprfileloc": {
                            "path": "test_sample.py",
                            "lineno": 6,
                            "message": "AssertionError"
                        }
                    }
                }
            ]
        }
    }
    result = format_longrepr(longrepr)
    assert "def test_fail():" in result
    assert ">   assert False" in result
    assert "E   AssertionError: test failed" in result
    assert "test_sample.py:6: AssertionError" in result


def test_format_longrepr_dict_multiple_entries() -> None:
    """Test formatting dict with multiple traceback entries."""
    longrepr = {
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": ["def helper():", ">   raise ValueError('error')"],
                        "reprfileloc": {
                            "path": "helpers.py",
                            "lineno": 10,
                            "message": "ValueError"
                        }
                    }
                },
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": ["def test_fail():", ">   helper()"],
                        "reprfileloc": {
                            "path": "test_sample.py",
                            "lineno": 20,
                            "message": "ValueError"
                        }
                    }
                }
            ]
        }
    }
    result = format_longrepr(longrepr)
    assert "def helper():" in result
    assert "def test_fail():" in result
    assert "helpers.py:10: ValueError" in result
    assert "test_sample.py:20: ValueError" in result


def test_format_longrepr_dict_reprcrash_fallback() -> None:
    """Test formatting dict with reprcrash only (no reprtraceback)."""
    longrepr = {
        "reprcrash": {
            "path": "test_sample.py",
            "lineno": 15,
            "message": "RuntimeError: Setup failed"
        }
    }
    result = format_longrepr(longrepr)
    assert result == "test_sample.py:15\nRuntimeError: Setup failed"


def test_format_longrepr_dict_reprcrash_message_only() -> None:
    """Test formatting dict with reprcrash message but no path/lineno."""
    longrepr = {
        "reprcrash": {
            "message": "RuntimeError: Something went wrong"
        }
    }
    result = format_longrepr(longrepr)
    assert result == "RuntimeError: Something went wrong"


def test_format_longrepr_dict_no_lines() -> None:
    """Test formatting dict with reprtraceback but no lines."""
    longrepr = {
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": [],
                        "reprfileloc": {
                            "path": "test_sample.py",
                            "lineno": 5,
                            "message": "Error"
                        }
                    }
                }
            ]
        },
        "reprcrash": {
            "message": "Fallback error message"
        }
    }
    result = format_longrepr(longrepr)
    # Even with no lines, reprfileloc is still added
    assert "test_sample.py:5: Error" in result


def test_format_longrepr_dict_incomplete_reprfileloc() -> None:
    """Test formatting dict with incomplete reprfileloc."""
    longrepr = {
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": ["test line"],
                        "reprfileloc": {
                            "path": "test.py"
                            # Missing lineno
                        }
                    }
                }
            ]
        }
    }
    result = format_longrepr(longrepr)
    assert result == "test line"


def test_format_longrepr_dict_non_reprentry_type() -> None:
    """Test formatting dict with non-ReprEntry type."""
    longrepr = {
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "SomethingElse",
                    "data": {
                        "lines": ["should be skipped"]
                    }
                }
            ]
        },
        "reprcrash": {
            "message": "Error occurred"
        }
    }
    result = format_longrepr(longrepr)
    assert result == "Error occurred"


def test_format_longrepr_dict_missing_data() -> None:
    """Test formatting dict with missing data field."""
    longrepr = {
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry"
                    # Missing data field
                }
            ]
        },
        "reprcrash": {
            "message": "Fallback message"
        }
    }
    result = format_longrepr(longrepr)
    assert result == "Fallback message"


def test_format_longrepr_dict_empty() -> None:
    """Test formatting empty dict."""
    longrepr = {}
    result = format_longrepr(longrepr)
    # Empty dict has no reprtraceback or reprcrash, returns None
    assert result is None


def test_format_longrepr_dict_empty_reprentries() -> None:
    """Test formatting dict with empty reprentries list."""
    longrepr = {
        "reprtraceback": {
            "reprentries": []
        }
    }
    result = format_longrepr(longrepr)
    assert result == str(longrepr)


def test_format_longrepr_unicode_characters() -> None:
    """Test formatting longrepr with unicode characters."""
    longrepr = "AssertionError: Expected '✓' but got '✗'"
    result = format_longrepr(longrepr)
    assert result == "AssertionError: Expected '✓' but got '✗'"


def test_format_longrepr_dict_with_unicode() -> None:
    """Test formatting dict with unicode in lines."""
    longrepr = {
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": [
                            "def test_unicode():",
                            ">   assert '✓' == '✗'",
                            "E   AssertionError"
                        ]
                    }
                }
            ]
        }
    }
    result = format_longrepr(longrepr)
    assert "✓" in result
    assert "✗" in result


def test_format_longrepr_real_pytest_structure() -> None:
    """Test formatting with real pytest-reportlog structure."""
    longrepr = {
        "reprcrash": {
            "path": "test_sample.py",
            "lineno": 6,
            "message": "AssertionError: test failed"
        },
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": [
                            "def test_fail():",
                            ">   assert False",
                            "E   AssertionError: test failed"
                        ],
                        "reprfuncargs": {"args": []},
                        "reprlocals": None,
                        "reprfileloc": {
                            "path": "test_sample.py",
                            "lineno": 6,
                            "message": "AssertionError"
                        }
                    }
                }
            ]
        }
    }
    result = format_longrepr(longrepr)
    assert "def test_fail():" in result
    assert ">   assert False" in result
    assert "E   AssertionError: test failed" in result
    assert "test_sample.py:6" in result


def test_format_longrepr_setup_error_structure() -> None:
    """Test formatting setup error with fixture traceback."""
    longrepr = {
        "reprcrash": {
            "path": "test_sample.py",
            "lineno": 3,
            "message": "RuntimeError: Setup failed"
        },
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": [
                            "@pytest.fixture",
                            "def failing():",
                            ">   raise RuntimeError('Setup failed')",
                            "E   RuntimeError: Setup failed"
                        ],
                        "reprfuncargs": {"args": []},
                        "reprlocals": None,
                        "reprfileloc": {
                            "path": "test_sample.py",
                            "lineno": 3,
                            "message": "RuntimeError"
                        }
                    }
                }
            ]
        }
    }
    result = format_longrepr(longrepr)
    assert "@pytest.fixture" in result
    assert "raise RuntimeError('Setup failed')" in result
    assert "test_sample.py:3: RuntimeError" in result


def test_format_longrepr_preserves_formatting() -> None:
    """Test that formatting preserves code indentation and structure."""
    longrepr = {
        "reprtraceback": {
            "reprentries": [
                {
                    "type": "ReprEntry",
                    "data": {
                        "lines": [
                            "    def nested_function():",
                            "        value = calculate()",
                            ">       assert value > 0",
                            "E       AssertionError"
                        ]
                    }
                }
            ]
        }
    }
    result = format_longrepr(longrepr)
    # Check that indentation is preserved
    assert "    def nested_function():" in result
    assert "        value = calculate()" in result
