"""JSONL builder utility for creating test data programmatically.

This module provides a fluent API for building reportlog-format JSONL content
for tests. It eliminates the need for hardcoded JSON strings and makes test
data creation more maintainable.

Example usage:
    builder = JSONLBuilder()
    jsonl = (
        builder
        .session_start("8.4.2")
        .test("test_sample.py::test_one")
            .setup(outcome="passed", duration=0.001)
            .call(outcome="passed", duration=0.002)
            .teardown(outcome="passed", duration=0.001)
        .test("test_sample.py::test_two")
            .setup(outcome="passed", duration=0.001)
            .call(outcome="failed", duration=0.003, longrepr="AssertionError")
            .teardown(outcome="passed", duration=0.001)
        .session_finish(exitstatus=1)
        .build()
    )
"""

import json
from typing import Any


class TestBuilder:
    """Builder for a single test with setup/call/teardown phases."""

    def __init__(self, parent: "JSONLBuilder", nodeid: str):
        self.parent = parent
        self.nodeid = nodeid
        self.file = nodeid.split("::")[0] if "::" in nodeid else "test.py"
        self.func = nodeid.split("::")[-1] if "::" in nodeid else nodeid
        self._keywords: dict = {}
        self._timestamp = parent._current_timestamp

    def keywords(self, **kwargs) -> "TestBuilder":
        """Set keywords for this test (e.g., xfail=1)."""
        self._keywords.update(kwargs)
        return self

    def setup(
        self,
        outcome: str = "passed",
        duration: float = 0.001,
        longrepr: Any = None,
        sections: list | None = None,
    ) -> "TestBuilder":
        """Add setup phase report."""
        return self._add_phase("setup", outcome, duration, longrepr, sections)

    def call(
        self,
        outcome: str = "passed",
        duration: float = 0.002,
        longrepr: Any = None,
        sections: list | None = None,
    ) -> "TestBuilder":
        """Add call phase report."""
        return self._add_phase("call", outcome, duration, longrepr, sections)

    def teardown(
        self,
        outcome: str = "passed",
        duration: float = 0.001,
        longrepr: Any = None,
        sections: list | None = None,
    ) -> "TestBuilder":
        """Add teardown phase report."""
        return self._add_phase("teardown", outcome, duration, longrepr, sections)

    def _add_phase(
        self,
        when: str,
        outcome: str,
        duration: float,
        longrepr: Any,
        sections: list | None,
    ) -> "TestBuilder":
        """Add a phase report."""
        start = self._timestamp
        stop = start + duration
        self._timestamp = stop
        self.parent._current_timestamp = stop

        report = {
            "nodeid": self.nodeid,
            "location": [self.file, 1, self.func],
            "keywords": self._keywords,
            "outcome": outcome,
            "longrepr": longrepr,
            "when": when,
            "duration": duration,
            "start": start,
            "stop": stop,
            "sections": sections or [],
            "$report_type": "TestReport",
        }
        self.parent._records.append(report)
        return self

    def test(self, nodeid: str) -> "TestBuilder":
        """Start a new test (delegate to parent)."""
        return self.parent.test(nodeid)

    def session_finish(self, exitstatus: int = 0) -> "JSONLBuilder":
        """Finish the session (delegate to parent)."""
        return self.parent.session_finish(exitstatus)


class JSONLBuilder:
    """Fluent builder for reportlog-format JSONL content."""

    def __init__(self):
        self._records: list[dict] = []
        self._current_timestamp: float = 1000.0

    def session_start(
        self, pytest_version: str = "8.4.2", metadata: dict | None = None
    ) -> "JSONLBuilder":
        """Add SessionStart record (optionally with environment metadata)."""
        record: dict = {
            "pytest_version": pytest_version,
            "$report_type": "SessionStart",
        }
        if metadata is not None:
            record["metadata"] = metadata
        self._records.append(record)
        return self

    def test(self, nodeid: str) -> TestBuilder:
        """Start a new test."""
        return TestBuilder(self, nodeid)

    def session_finish(self, exitstatus: int = 0) -> "JSONLBuilder":
        """Add SessionFinish record."""
        self._records.append(
            {
                "exitstatus": exitstatus,
                "$report_type": "SessionFinish",
            }
        )
        return self

    def build(self) -> str:
        """Build the JSONL content."""
        return "\n".join(json.dumps(r) for r in self._records) + "\n"


def simple_test(
    nodeid: str = "test_sample.py::test_pass", outcome: str = "passed"
) -> str:
    """Create JSONL for a simple test with given outcome."""
    builder = JSONLBuilder()
    test = builder.session_start().test(nodeid).setup()

    if outcome == "passed":
        test.call(outcome="passed")
    elif outcome == "failed":
        test.call(
            outcome="failed",
            longrepr={
                "reprcrash": {
                    "path": "test.py",
                    "lineno": 1,
                    "message": "AssertionError",
                },
                "reprtraceback": {"reprentries": []},
            },
        )
    elif outcome == "skipped":
        test.call(outcome="skipped")

    return (
        test.teardown()
        .session_finish(exitstatus=0 if outcome == "passed" else 1)
        .build()
    )


def xfail_test(nodeid: str = "test_sample.py::test_xfail", passes: bool = False) -> str:
    """Create JSONL for an xfail test.

    Args:
        nodeid: Test node ID
        passes: If True, creates xpass (expected to fail but passes).
                If False, creates xfail (expected to fail and does fail).
    """
    builder = JSONLBuilder()
    test = builder.session_start().test(nodeid).keywords(xfail=1).setup()

    if passes:
        # xpass: expected to fail but passes
        test.call(outcome="passed")
    else:
        # xfail: expected to fail and does fail
        test.call(outcome="skipped")

    return test.teardown().session_finish(exitstatus=0).build()
