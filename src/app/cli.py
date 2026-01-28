"""CLI for pytest-webreportlog web service."""
import os
import signal
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(
    name="pytest-webreportlog",
    help="Web service for viewing pytest-reportlog JSONL reports",
    no_args_is_help=True,
)

# Default configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_PID_FILE = Path("server.pid")
DEFAULT_LOG_FILE = Path("server.log")


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

    typer.echo(f"Starting server at http://{host}:{port}")
    if reload:
        typer.echo("Auto-reload enabled (development mode)")

    uvicorn.run(
        "src.app.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,  # reload doesn't work with multiple workers
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
                "src.app.main:app",
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
    import time

    # Stop if running
    _cleanup_stale_pid_file(pid_file)
    pid = _get_pid_from_file(pid_file)
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
            pid_file.unlink(missing_ok=True)
            typer.echo(f"Stopped server (PID: {pid})")
            time.sleep(1)  # Give it time to shut down
        except OSError:
            pass

    # Start fresh
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
