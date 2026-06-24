# pytest-webreportlog

A web dashboard for [pytest-reportlog](https://github.com/pytest-dev/pytest-reportlog) output. Upload JSONL reports or stream test events in real time.

## Features

- Upload `.jsonl` reports via web UI or API
- Session list with pass/fail/skip/xfail/error counts
- Per-test drill-down by phase (setup / call / teardown) with ANSI color rendering
- Test history and pass-rate analytics across sessions
- Real-time streaming via Server-Sent Events (SSE)
- Dark mode

## Stack

FastAPI · SQLModel · SQLite · Jinja2 · Tailwind CSS · HTMX · Uvicorn · Typer

## Quick start

```bash
uv sync
pytest-webreportlog dev        # http://localhost:8000
```

Run your tests, then upload the report:

```bash
pytest --report-log=report.jsonl
# drag-and-drop report.jsonl onto the web UI, or:
curl -F "file=@report.jsonl" http://localhost:8000/upload
```

## CLI

```
pytest-webreportlog dev                          # dev server with auto-reload
pytest-webreportlog serve [--host] [--port] [--reload] [--workers N]
pytest-webreportlog start [--host] [--port] [--pid-file] [--log-file]
pytest-webreportlog stop / restart / status
```

> **Note:** SSE streaming requires `--workers 1` (the default). Multiple workers use separate in-memory state.

## Database

SQLite, stored in `data/sessions.db` by default. Override with `DATABASE_URL`:

```bash
DATABASE_URL=sqlite:///data/myproject.db pytest-webreportlog serve
```

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Session list |
| GET | `/sessions/{id}` | Session detail |
| GET | `/history` | Test history overview |
| GET | `/history/{nodeid}` | Per-test history |
| GET | `/api/sessions` | Sessions (JSON) |
| GET | `/api/sessions/{id}` | Session detail (JSON) |
| DELETE | `/api/sessions/{id}` | Delete session |
| POST | `/upload` | Upload JSONL file |
| POST | `/api/stream/event` | Post a test event |
| GET | `/api/stream/{session_id}` | SSE stream |

### Streaming example

```bash
SESSION=$(uuidgen)
BASE=http://localhost:8000

curl -s -X POST $BASE/api/stream/event -H "X-Session-ID: $SESSION" \
  -H "Content-Type: text/plain" \
  -d '{"pytest_version":"8.4.2","$report_type":"SessionStart"}'

curl -s -X POST $BASE/api/stream/event -H "X-Session-ID: $SESSION" \
  -H "Content-Type: text/plain" \
  -d '{"nodeid":"test_foo.py::test_bar","outcome":"passed","when":"call","duration":0.01,"$report_type":"TestReport"}'

curl -s -X POST $BASE/api/stream/event -H "X-Session-ID: $SESSION" \
  -H "Content-Type: text/plain" \
  -d '{"exitstatus":0,"$report_type":"SessionFinish"}'
```

## Tests

```bash
uv run pytest tests/
```

## License

MIT
