"""Tests for JUnit XML report generation - format-specific tests only.

Common cross-format tests (exceptions, logs, xfail) are in test_all_formats.py.
"""
from pytest import Pytester

from .report_utils import (
    get_junit_summary,
    get_junit_testcases,
    parse_junit_xml,
)


def test_junit_generates_file(
    junit_config: Pytester, simple_test_content: Pytester
) -> None:
    """Test that pytest generates a JUnit XML file."""
    result = junit_config.runpytest()
    result.assert_outcomes(passed=1)

    junit_file = junit_config.path / "junit.xml"
    assert junit_file.exists(), "JUnit XML file should be created"


def test_junit_summary_passing(
    junit_config: Pytester, multiple_test_content: Pytester
) -> None:
    """Test that JUnit XML correctly summarizes passing tests."""
    result = junit_config.runpytest()
    result.assert_outcomes(passed=2)

    root = parse_junit_xml(junit_config.path / "junit.xml")
    summary = get_junit_summary(root)

    assert summary["tests"] == 2
    assert summary["failures"] == 0
    assert summary["errors"] == 0
    assert summary["skipped"] == 0


def test_junit_summary_mixed(
    junit_config: Pytester, mixed_test_content: Pytester
) -> None:
    """Test that JUnit XML correctly summarizes mixed test outcomes."""
    result = junit_config.runpytest()
    result.assert_outcomes(passed=1, failed=1, skipped=1)

    root = parse_junit_xml(junit_config.path / "junit.xml")
    summary = get_junit_summary(root)

    assert summary["tests"] == 3
    assert summary["failures"] == 1
    assert summary["skipped"] == 1


def test_junit_testcase_elements(
    junit_config: Pytester, multiple_test_content: Pytester
) -> None:
    """Test that JUnit XML contains testcase elements for each test."""
    result = junit_config.runpytest()
    result.assert_outcomes(passed=2)

    root = parse_junit_xml(junit_config.path / "junit.xml")
    testcases = get_junit_testcases(root)

    assert len(testcases) == 2
    for testcase in testcases:
        assert testcase.get("name") is not None
        assert testcase.get("classname") is not None
        assert testcase.get("time") is not None


def test_junit_failure_details(
    junit_config: Pytester, mixed_test_content: Pytester
) -> None:
    """Test that JUnit XML includes failure details for failed tests."""
    result = junit_config.runpytest()
    result.assert_outcomes(passed=1, failed=1, skipped=1)

    root = parse_junit_xml(junit_config.path / "junit.xml")
    testcases = get_junit_testcases(root)

    # Find the failed test
    failed_testcases = [tc for tc in testcases if tc.find("failure") is not None]
    assert len(failed_testcases) == 1

    failure = failed_testcases[0].find("failure")
    assert failure is not None
    assert "Intentional failure" in failure.get("message", "")


def test_junit_skipped_details(
    junit_config: Pytester, mixed_test_content: Pytester
) -> None:
    """Test that JUnit XML includes skip details for skipped tests."""
    result = junit_config.runpytest()
    result.assert_outcomes(passed=1, failed=1, skipped=1)

    root = parse_junit_xml(junit_config.path / "junit.xml")
    testcases = get_junit_testcases(root)

    # Find the skipped test
    skipped_testcases = [tc for tc in testcases if tc.find("skipped") is not None]
    assert len(skipped_testcases) == 1

    skipped = skipped_testcases[0].find("skipped")
    assert skipped is not None
    # Skip reason should be in the element
    skip_info = skipped.get("message", "") or skipped.text or ""
    assert "Testing skip" in skip_info
