"""Pytest plugin that streams test results to a webreportlog viewer over HTTP.

Each pytest session is serialized using pytest's built-in
``pytest_report_to_serializable`` hook and posted, event by event, to the
viewer's ``/api/stream/event`` endpoint. Events are correlated by a per-run
``X-Session-ID`` UUID header.

The transport uses only the standard library, so the published distribution
depends on nothing but pytest. All network activity is fail-soft: if the viewer
is unreachable the test run is never interrupted.
"""

import copy
import json
import platform
import sys
import urllib.error
import urllib.request
import uuid
import warnings
from typing import Any

import pytest


class WebReportLogWarning(UserWarning):
    """Emitted once when streaming events to the viewer fails."""


# Captured-log section labels (one per phase), used by the
# --webreportlog-exclude-logs-on-passed option.
_CAPTURED_LOG_SECTIONS = (
    "Captured log setup",
    "Captured log call",
    "Captured log teardown",
)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("webreportlog", "webreportlog streaming plugin")
    group.addoption(
        "--webreportlog-url",
        action="store",
        dest="webreportlog_url",
        metavar="url",
        default=None,
        help="Base URL of the webreportlog viewer to stream results to, "
        "e.g. http://127.0.0.1:8000",
    )
    group.addoption(
        "--webreportlog-timeout",
        action="store",
        dest="webreportlog_timeout",
        type=float,
        default=5.0,
        help="Per-request HTTP timeout in seconds (default: 5.0)",
    )
    group.addoption(
        "--webreportlog-exclude-logs-on-passed",
        action="store_true",
        dest="webreportlog_exclude_logs_on_passed",
        default=False,
        help="Don't stream captured logs for passing tests",
    )


def pytest_configure(config: pytest.Config) -> None:
    url = config.option.webreportlog_url
    # Only the xdist controller streams (workers have `workerinput`); this
    # mirrors upstream pytest-reportlog and avoids duplicate event streams.
    if url and not hasattr(config, "workerinput"):
        plugin = WebReportLogPlugin(
            config=config,
            base_url=url,
            timeout=config.option.webreportlog_timeout,
            exclude_logs_on_passed=config.option.webreportlog_exclude_logs_on_passed,
        )
        # Dynamic attribute stashed on pytest's Config (mirrors upstream pattern).
        config._webreportlog_plugin = plugin  # type: ignore[attr-defined]
        config.pluginmanager.register(plugin)


def pytest_unconfigure(config: pytest.Config) -> None:
    plugin = getattr(config, "_webreportlog_plugin", None)
    if plugin is not None:
        config.pluginmanager.unregister(plugin)
        del config._webreportlog_plugin  # type: ignore[attr-defined]


def _normalize_endpoint(base_url: str) -> str:
    """Turn a viewer base URL into the full event endpoint."""
    base = base_url.rstrip("/")
    if base.endswith("/api/stream/event"):
        return base
    return f"{base}/api/stream/event"


class WebReportLogPlugin:
    """Serializes pytest reports and streams them to the viewer."""

    def __init__(
        self,
        config: pytest.Config,
        base_url: str,
        timeout: float = 5.0,
        exclude_logs_on_passed: bool = False,
    ) -> None:
        self._config = config
        self._endpoint = _normalize_endpoint(base_url)
        self._timeout = timeout
        self._exclude_logs_on_passed = exclude_logs_on_passed
        self._session_uuid = uuid.uuid4().hex
        self._sent = 0
        self._failed = 0
        self._warned = False

    # -- transport ---------------------------------------------------------

    def _post(self, data: dict[str, Any]) -> None:
        """POST one event; never raise (fail-soft)."""
        try:
            body = json.dumps(data).encode("utf-8")
        except TypeError:
            body = json.dumps(_cleanup_unserializable(data)).encode("utf-8")

        request = urllib.request.Request(
            self._endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "text/plain",
                "X-Session-ID": self._session_uuid,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout):
                pass
            self._sent += 1
        except (urllib.error.URLError, OSError) as exc:
            self._failed += 1
            if not self._warned:
                self._warned = True
                warnings.warn(
                    f"webreportlog: failed to stream events to {self._endpoint} "
                    f"({exc}); results will not be recorded.",
                    WebReportLogWarning,
                    stacklevel=2,
                )

    def _serialize(self, report: Any) -> dict[str, Any]:
        """Serialize a report via the core pytest hook; normalize the type key."""
        data = self._config.hook.pytest_report_to_serializable(
            config=self._config, report=report
        )
        # Subtests emit `_report_type` instead of `$report_type` (pytest-reportlog #90).
        if "_report_type" in data:
            data["$report_type"] = data.pop("_report_type")
        return data

    # -- hooks -------------------------------------------------------------

    def pytest_sessionstart(self) -> None:
        self._post(
            {
                "pytest_version": pytest.__version__,
                "$report_type": "SessionStart",
                "metadata": _collect_metadata(self._config),
            }
        )

    def pytest_collectreport(self, report: pytest.CollectReport) -> None:
        self._post(self._serialize(report))

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # Phase-section isolation: keep only the captured sections belonging to
        # this report's phase, so each phase carries just its own output.
        if phase := report.when:
            report = copy.copy(report)
            report.sections = [
                (head, content) for head, content in report.sections if phase in head
            ]

        data = self._serialize(report)

        if self._exclude_logs_on_passed and data.get("outcome") == "passed":
            data["sections"] = [
                s
                for s in data.get("sections", [])
                if s[0] not in _CAPTURED_LOG_SECTIONS
            ]

        self._post(data)

    def pytest_sessionfinish(self, exitstatus: int) -> None:
        self._post({"exitstatus": int(exitstatus), "$report_type": "SessionFinish"})

    def pytest_terminal_summary(self, terminalreporter) -> None:
        summary = f"webreportlog: streamed {self._sent} event(s) to {self._endpoint}"
        if self._failed:
            summary += f", {self._failed} failed"
        terminalreporter.write_sep("-", summary)


def _pytest_metadata(config: pytest.Config) -> dict[str, Any] | None:
    """Return pytest-metadata's collected metadata, or None when unavailable.

    pytest-metadata >= 2.0 stores it in ``config.stash`` (keyed by a StashKey it
    exports); older versions used ``config._metadata``. Both are optional — the
    plugin itself depends only on pytest.
    """
    try:
        from pytest_metadata.plugin import metadata_key

        return config.stash.get(metadata_key, None)
    except Exception:
        return getattr(config, "_metadata", None)


def _collect_metadata(config: pytest.Config) -> dict[str, Any]:
    """Return a JSON-safe metadata dict describing the test environment.

    Prefers pytest-metadata's rich collection when present; falls back to a
    minimal set gathered from stdlib.
    """
    raw = _pytest_metadata(config)
    if raw:
        try:
            return json.loads(json.dumps(dict(raw), default=str))
        except Exception:
            pass

    meta: dict[str, Any] = {
        "Python": sys.version.split()[0],
        "Platform": platform.platform(),
    }
    try:
        packages = {
            dist.project_name: dist.version
            for _, dist in config.pluginmanager.list_plugin_distinfo()
        }
        if packages:
            meta["Packages"] = packages
    except Exception:
        pass
    return meta


def _cleanup_unserializable(d: dict[str, Any]) -> dict[str, Any]:
    """Return a copy where non-JSON-serializable values are stringified."""
    result: dict[str, Any] = {}
    for key, value in d.items():
        try:
            json.dumps({key: value})
        except TypeError:
            value = str(value)
        result[key] = value
    return result
