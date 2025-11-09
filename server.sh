#!/bin/bash

PID_FILE="server.pid"

start() {
    if [ -f "$PID_FILE" ]; then
        echo "Server already running (PID: $(cat $PID_FILE))"
        exit 1
    fi

    echo "Starting server..."
    uv run uvicorn src.app.main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
    echo $! > "$PID_FILE"
    echo "Server started (PID: $(cat $PID_FILE))"
    echo "Logs: tail -f server.log"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Server not running"
        exit 1
    fi

    PID=$(cat "$PID_FILE")
    echo "Stopping server (PID: $PID)..."
    kill $PID
    rm "$PID_FILE"
    echo "Server stopped"
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null; then
            echo "Server is running (PID: $PID)"
        else
            echo "PID file exists but process is not running"
            rm "$PID_FILE"
        fi
    else
        echo "Server is not running"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
