"""CLI for pytest-webreportlog web service."""
import os
import signal
import sys
import time
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="pytest-webreportlog",
    help="Web service for viewing pytest-reportlog JSONL reports",
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
        "app.main:app",
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
                "app.main:app",
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
        raise typer.Exit(1)


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


if __name__ == "__main__":
    app()
