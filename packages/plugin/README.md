# pytest-webreportlog

A pytest plugin that streams live test results to a [webreportlog-server](https://github.com/sbryskyi/pytest-webreportlog) web viewer over HTTP, phase by phase, as your suite runs.

It depends only on `pytest` — events are serialized with pytest's built-in `pytest_report_to_serializable` hook and sent with the standard library. No report files, no extra dependencies.

## Install

```bash
pip install pytest-webreportlog
```

## Use

Point your test run at a running viewer:

```bash
pytest --webreportlog-url=http://127.0.0.1:8000
```

Each run opens a new session in the viewer and streams `SessionStart`, collection reports, per-phase `TestReport`s, and `SessionFinish`. Captured output is **phase-isolated** — each setup/call/teardown report carries only its own sections.

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--webreportlog-url` | — | Viewer base URL. When unset, the plugin is inert. |
| `--webreportlog-timeout` | `5.0` | Per-request HTTP timeout (seconds). |
| `--webreportlog-exclude-logs-on-passed` | off | Drop captured logs for passing tests. |

Streaming is **fail-soft**: if the viewer is unreachable the run is never interrupted — a single warning is emitted and a summary line reports how many events failed.

Under `pytest-xdist`, only the controller streams (workers are skipped), so events are not duplicated.

## Tagging runs (environment metadata)

The plugin sends a metadata dict with each session's `SessionStart`. By default it
collects Python version, platform, and installed plugin versions. To attach your own
attributes — a trigger type, branch, build id, anything — install
[`pytest-metadata`](https://github.com/pytest-dev/pytest-metadata) and pass values on
the command line:

```bash
pytest --webreportlog-url=$URL --metadata trigger nightly --metadata branch main
```

or set them programmatically in a `conftest.py`:

```python
def pytest_configure(config):
    config._metadata["trigger"] = "nightly"  # any logic: CI vars, git, etc.
```

Every **scalar** metadata value becomes a one-click filter chip in the viewer's
session list and per-test history, so you can answer "under which circumstances did
this test fail?" (e.g. only `trigger=nightly` runs on `Python=3.12`).

## Wire format

The plugin POSTs newline-free JSON objects to `{url}/api/stream/event` with an `X-Session-ID` header (a per-run UUID). Each event carries a `$report_type` of `SessionStart`, `CollectReport`, `TestReport`, or `SessionFinish` — the same serialized shape pytest produces internally. The `SessionStart` event also carries a `metadata` object (see [Tagging runs](#tagging-runs-environment-metadata)).

## License

MIT
