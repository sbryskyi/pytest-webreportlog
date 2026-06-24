# pytest-webreportlog

A live pytest results dashboard, split into two independently-installable pieces:

| Package | Role | Dependencies |
|---------|------|--------------|
| [`pytest-webreportlog`](packages/plugin) | pytest plugin — streams results over HTTP as tests run | `pytest` only |
| [`webreportlog-server`](packages/server) | web viewer — receives, stores, and renders results | fastapi / uvicorn / sqlmodel / jinja2 / ansi2html / typer |

The two never need to be installed together: the test runner installs only the plugin; the viewer host installs only the server. They speak a small HTTP event protocol — no report files, no shared pytest dependency.

## How it works

```
pytest --webreportlog-url=URL ──HTTP events──▶ webreportlog-server ──▶ dashboard
```

The plugin serializes each pytest report with the built-in `pytest_report_to_serializable` hook and POSTs it (phase by phase) to the viewer's `/api/stream/event` endpoint, correlated by a per-run `X-Session-ID`. Captured output is phase-isolated — each setup/call/teardown report carries only its own sections.

## Quick start (development, single repo)

This repo is a uv workspace containing both packages.

```bash
uv sync                                   # installs both packages + dev tools

# terminal 1: the viewer
uv run webreportlog-server serve          # http://127.0.0.1:8000

# terminal 2: your tests, streaming live
uv run pytest --webreportlog-url=http://127.0.0.1:8000
```

Open http://127.0.0.1:8000 to watch sessions appear in real time.

## Installing the pieces separately

```bash
# on the machine that runs tests
pip install pytest-webreportlog

# on the machine that hosts the dashboard
pip install webreportlog-server
```

See each package's README for full options:
- [packages/plugin/README.md](packages/plugin/README.md) — plugin options, wire format
- [packages/server/README.md](packages/server/README.md) — CLI, database, API

## Features

- Session list with pass/fail/skip/xfail/xpass/error counts
- Per-test drill-down by phase (setup / call / teardown) with ANSI color rendering
- Test history and pass-rate analytics across sessions
- Real-time updates via Server-Sent Events
- Dark mode

## Tests

```bash
uv run pytest          # plugin, server, and end-to-end suites
```

## License

MIT
