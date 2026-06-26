"""CLI for the webreportlog web viewer service."""

import os
import signal
import sys
import time
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="webreportlog-server",
    help="Web viewer for live pytest results streamed by the pytest-webreportlog plugin",
    no_args_is_help=True,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_PID_FILE = Path("server.pid")
DEFAULT_LOG_FILE = Path("server.log")

_STOP_TIMEOUT = 10  # seconds to wait for graceful shutdown


def _get_pid_from_file(pid_file: Path) -> int | None:
    """Read PID from file if it exists."""
    if not pid_file.exists():
        return None
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _cleanup_stale_pid_file(pid_file: Path) -> None:
    """Remove PID file if the process is no longer running."""
    pid = _get_pid_from_file(pid_file)
    if pid is not None and not _is_process_running(pid):
        pid_file.unlink(missing_ok=True)


def _wait_for_stop(pid: int) -> bool:
    """Poll until the process stops or the timeout is reached. Returns True if stopped."""
    deadline = time.monotonic() + _STOP_TIMEOUT
    while time.monotonic() < deadline:
        if not _is_process_running(pid):
            return True
        time.sleep(0.25)
    return False


@app.command()
def serve(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = DEFAULT_PORT,
    reload: Annotated[
        bool,
        typer.Option("--reload", "-r", help="Enable auto-reload for development"),
    ] = False,
    workers: Annotated[
        int,
        typer.Option("--workers", "-w", help="Number of worker processes"),
    ] = 1,
) -> None:
    """Start the web server (foreground mode)."""
    import uvicorn

    effective_workers = workers if not reload else 1
    if effective_workers > 1:
        typer.echo(
            "Warning: streaming (SSE) requires workers=1. "
            "With multiple workers, in-memory session state is not shared between processes.",
            err=True,
        )

    typer.echo(f"Starting server at http://{host}:{port}")
    if reload:
        typer.echo("Auto-reload enabled (development mode)")

    uvicorn.run(
        "webreportlog_server.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=effective_workers,
    )


@app.command()
def start(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = DEFAULT_PORT,
    pid_file: Annotated[
        Path,
        typer.Option("--pid-file", help="Path to PID file"),
    ] = DEFAULT_PID_FILE,
    log_file: Annotated[
        Path,
        typer.Option("--log-file", help="Path to log file"),
    ] = DEFAULT_LOG_FILE,
) -> None:
    """Start the web server in background (daemon mode)."""
    import subprocess

    _cleanup_stale_pid_file(pid_file)

    if pid_file.exists():
        pid = _get_pid_from_file(pid_file)
        typer.echo(f"Server already running (PID: {pid})", err=True)
        raise typer.Exit(1)

    typer.echo(f"Starting server at http://{host}:{port} (background)")

    with open(log_file, "w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "webreportlog_server.main:app",
                "--host",
                host,
                "--port",
                str(port),
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    pid_file.write_text(str(process.pid))
    typer.echo(f"Server started (PID: {process.pid})")
    typer.echo(f"Logs: tail -f {log_file}")


@app.command()
def stop(
    pid_file: Annotated[
        Path,
        typer.Option("--pid-file", help="Path to PID file"),
    ] = DEFAULT_PID_FILE,
) -> None:
    """Stop the background server."""
    _cleanup_stale_pid_file(pid_file)

    pid = _get_pid_from_file(pid_file)
    if pid is None:
        typer.echo("Server not running", err=True)
        raise typer.Exit(1)

    typer.echo(f"Stopping server (PID: {pid})...")

    try:
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink(missing_ok=True)
        typer.echo("Server stopped")
    except OSError as e:
        typer.echo(f"Failed to stop server: {e}", err=True)
        pid_file.unlink(missing_ok=True)
        raise typer.Exit(1) from e


@app.command()
def restart(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = DEFAULT_PORT,
    pid_file: Annotated[
        Path,
        typer.Option("--pid-file", help="Path to PID file"),
    ] = DEFAULT_PID_FILE,
    log_file: Annotated[
        Path,
        typer.Option("--log-file", help="Path to log file"),
    ] = DEFAULT_LOG_FILE,
) -> None:
    """Restart the background server."""
    _cleanup_stale_pid_file(pid_file)
    pid = _get_pid_from_file(pid_file)
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
            pid_file.unlink(missing_ok=True)
            typer.echo(f"Stopped server (PID: {pid})")
            if not _wait_for_stop(pid):
                typer.echo(
                    f"Warning: server (PID {pid}) did not stop within {_STOP_TIMEOUT}s",
                    err=True,
                )
        except OSError:
            pass

    start(host=host, port=port, pid_file=pid_file, log_file=log_file)


@app.command()
def status(
    pid_file: Annotated[
        Path,
        typer.Option("--pid-file", help="Path to PID file"),
    ] = DEFAULT_PID_FILE,
) -> None:
    """Check if the server is running."""
    pid = _get_pid_from_file(pid_file)

    if pid is None:
        typer.echo("Server is not running")
        raise typer.Exit(1)

    if _is_process_running(pid):
        typer.echo(f"Server is running (PID: {pid})")
    else:
        typer.echo("PID file exists but process is not running")
        pid_file.unlink(missing_ok=True)
        raise typer.Exit(1)


@app.command()
def dev(
    host: Annotated[
        str,
        typer.Option("--host", "-h", help="Host to bind to"),
    ] = DEFAULT_HOST,
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port to bind to"),
    ] = DEFAULT_PORT,
) -> None:
    """Start development server with auto-reload."""
    serve(host=host, port=port, reload=True, workers=1)


@app.command()
def prune(
    max_size: Annotated[
        str | None,
        typer.Option(
            "--max-size",
            help="Size cap, e.g. '2GB' (default: WEBREPORTLOG_MAX_DB_SIZE)",
        ),
    ] = None,
    keep_recent: Annotated[
        int | None,
        typer.Option(
            "--keep-recent",
            help="Newest sessions to never prune (default: WEBREPORTLOG_KEEP_RECENT or 10)",
        ),
    ] = None,
) -> None:
    """Shrink the database to fit under a size cap.

    Strips logs/tracebacks from the oldest sessions first, then deletes the oldest
    sessions if still over the cap, then VACUUMs. Operates on the database at
    DATABASE_URL; VACUUM briefly locks it, so prefer running this while the server
    is idle (or use POST /api/prune in-process).
    """
    from sqlmodel import Session

    from .database import engine, get_configured_keep_recent, get_configured_max_bytes
    from .services.retention import prune_database
    from .utils import parse_size

    max_bytes: int | None
    if max_size is not None:
        try:
            max_bytes = parse_size(max_size)
        except ValueError as e:
            typer.echo(f"Invalid --max-size: {e}", err=True)
            raise typer.Exit(2) from e
    else:
        try:
            max_bytes = get_configured_max_bytes()
        except ValueError as e:
            typer.echo(f"Invalid WEBREPORTLOG_MAX_DB_SIZE: {e}", err=True)
            raise typer.Exit(2) from e

    if max_bytes is None:
        typer.echo(
            "No size cap configured. Pass --max-size or set WEBREPORTLOG_MAX_DB_SIZE.",
            err=True,
        )
        raise typer.Exit(2)

    resolved_keep = (
        keep_recent if keep_recent is not None else get_configured_keep_recent()
    )

    with Session(engine) as db:
        report = prune_database(db, max_bytes, resolved_keep)

    typer.echo(
        f"Database: {report['before_human']} -> {report['after_human']} "
        f"(cap {report['cap_human']})"
    )
    typer.echo(
        f"Stripped logs from {report['stripped_count']} session(s); "
        f"deleted {report['deleted_count']} session(s)."
    )
    if report.get("message"):
        typer.echo(report["message"])


if __name__ == "__main__":
    app()
