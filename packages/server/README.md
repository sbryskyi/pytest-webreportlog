# webreportlog-server

The web viewer for [pytest-webreportlog](https://github.com/sbryskyi/pytest-webreportlog). It receives live pytest events over HTTP, stores them in SQLite, and renders an interactive dashboard with per-phase drill-down, ANSI rendering, history, and real-time updates.

It does **not** depend on pytest — it only consumes the serialized report events the plugin sends.

## Install & run

```bash
pip install webreportlog-server
webreportlog-server serve            # http://127.0.0.1:8000
```

Then run your tests with the plugin pointed at the server:

```bash
pytest --webreportlog-url=http://127.0.0.1:8000
```

## CLI

```
webreportlog-server dev                          # dev server with auto-reload
webreportlog-server serve [--host] [--port] [--reload] [--workers N]
webreportlog-server start [--host] [--port] [--pid-file] [--log-file]
webreportlog-server stop / restart / status
```

> **Note:** live streaming uses in-memory session state, so it requires `--workers 1` (the default).

## Database

SQLite at `data/sessions.db` by default. Override with `DATABASE_URL`:

```bash
DATABASE_URL=sqlite:///data/myproject.db webreportlog-server serve
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
| DELETE | `/api/sessions/{id}` | Delete a session |
| POST | `/api/stream/event` | Ingest one streamed report event |
| GET | `/api/stream/{session_id}` | Subscribe to live updates (SSE) |

### Event ingestion

`POST /api/stream/event` accepts one serialized pytest report (a JSON object) per request, correlated by an `X-Session-ID` header. Accepted `$report_type` values: `SessionStart`, `CollectReport`, `TestReport`, `SessionFinish`. This is exactly what the `pytest-webreportlog` plugin emits. The `SessionStart` event may include a `metadata` object; its scalar entries become one-click filter chips on the session list and per-test history views.

## License

MIT
