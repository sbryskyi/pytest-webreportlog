# Web server test suite

Integration tests for `webreportlog-server`. A session-scoped `web_server`
fixture (`conftest.py`) launches the FastAPI app as a subprocess against a
temporary SQLite database and tears it down afterward — no manual server
control.

Tests exercise the server the way the plugin does: the `APIClient.stream_jsonl`
helper streams newline-delimited report events to `POST /api/stream/event`
(correlated by an `X-Session-ID`) and returns a session-summary dict. Other
tests assert on the rendered HTML, the JSON API, history aggregation, and
streaming error handling.

`test_e2e_plugin.py` is the end-to-end check: it drives a real inner pytest run
through the installed `pytest-webreportlog` plugin (via `pytester`) against the
live `web_server`, then asserts the viewer reflects the run.

Run just this suite:

```bash
uv run pytest tests/server/web
```
