"""Utilities for parsing and validating pytest reports."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def parse_jsonl(file_path: Path) -> list[dict[str, Any]]:
    """
    Parse JSONL report file and return list of records.

    Args:
        file_path: Path to the .jsonl file

    Returns:
        List of dictionaries, one per line in the JSONL file
    """
    records = []
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_jsonl_report_types(records: list[dict]) -> set[str]:
    """Extract all report types from JSONL records."""
    return {
        record.get("$report_type") for record in records if "$report_type" in record
    }


def get_jsonl_test_reports(records: list[dict]) -> list[dict]:
    """Get only TestReport records from JSONL."""
    return [r for r in records if r.get("$report_type") == "TestReport"]


def get_jsonl_session_info(records: list[dict]) -> dict | None:
    """Get SessionStart record from JSONL."""
    for record in records:
        if record.get("$report_type") == "SessionStart":
            return record
    return None


def parse_junit_xml(file_path: Path) -> ET.Element:
    """
    Parse JUnit XML report file.

    Args:
        file_path: Path to the junit.xml file

    Returns:
        ElementTree root element
    """
    tree = ET.parse(file_path)
    return tree.getroot()


def get_junit_testcases(root: ET.Element) -> list[ET.Element]:
    """Get all testcase elements from JUnit XML."""
    return root.findall(".//testcase")


def get_junit_summary(root: ET.Element) -> dict[str, int]:
    """
    Extract test summary from JUnit XML root element.

    Returns:
        Dictionary with keys: tests, failures, errors, skipped
    """
    testsuite = root.find("testsuite")
    if testsuite is None:
        testsuite = root

    return {
        "tests": int(testsuite.get("tests", 0)),
        "failures": int(testsuite.get("failures", 0)),
        "errors": int(testsuite.get("errors", 0)),
        "skipped": int(testsuite.get("skipped", 0)),
    }


def get_junit_system_out(testcase: ET.Element) -> str:
    """Get system-out content from a JUnit testcase element."""
    system_out = testcase.find("system-out")
    if system_out is not None:
        return system_out.text or ""
    return ""


def get_junit_system_err(testcase: ET.Element) -> str:
    """Get system-err content from a JUnit testcase element."""
    system_err = testcase.find("system-err")
    if system_err is not None:
        return system_err.text or ""
    return ""


def parse_html_report(file_path: Path) -> str:
    """
    Read HTML report file.

    Args:
        file_path: Path to the .html file

    Returns:
        HTML content as string
    """
    return file_path.read_text()


def html_contains_text(html_content: str, text: str) -> bool:
    """Check if HTML contains specific text."""
    return text in html_content
