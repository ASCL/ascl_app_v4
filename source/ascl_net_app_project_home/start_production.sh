#!/bin/bash
#
# Production startup script for ASCL.net Flask application
#
# This script starts the Flask app using Uvicorn with production settings.
# The app will use the ascl_net.cfg configuration file and ascl_db_v4 database.
#
# Usage:
#   ./start_production.sh [start|stop|restart|status]
#
# Default action is 'start' if no argument provided.
#

# Change to script directory
cd "$(dirname "$0")"

# Configuration
export FLASK_CONFIG=ascl_net.cfg
HOST="127.0.0.1"
PORT=5050
WORKERS=2  # Adjust based on CPU cores (recommended: 2-4)
PID_FILE="/tmp/ascl_production.pid"

# Uvicorn command
UVICORN_CMD="uvicorn asgi:application --host $HOST --port $PORT --workers $WORKERS"

# Functions
start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Production app is already running (PID: $PID)"
            exit 1
        else
            echo "Removing stale PID file..."
            rm -f "$PID_FILE"
        fi
    fi

    echo "Starting ASCL.net production app..."
    echo "  Host: $HOST"
    echo "  Port: $PORT"
    echo "  Workers: $WORKERS"
    echo "  Config: $FLASK_CONFIG"
    echo "  Database: ascl_db_v4"
    echo ""

    # Start Uvicorn in background
    nohup $UVICORN_CMD > logs/production.log 2>&1 &
    echo $! > "$PID_FILE"

    sleep 2

    if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo "✓ Production app started successfully (PID: $(cat "$PID_FILE"))"
        echo "  Access at: http://$HOST:$PORT"
        echo "  Logs: logs/production.log"
    else
        echo "✗ Failed to start production app. Check logs/production.log for errors."
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Production app is not running (no PID file found)"
        exit 1
    fi

    PID=$(cat "$PID_FILE")

    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "Production app is not running (PID $PID not found)"
        rm -f "$PID_FILE"
        exit 1
    fi

    echo "Stopping ASCL.net production app (PID: $PID)..."
    kill "$PID"

    # Wait for graceful shutdown (max 10 seconds)
    for i in {1..10}; do
        if ! ps -p "$PID" > /dev/null 2>&1; then
            echo "✓ Production app stopped successfully"
            rm -f "$PID_FILE"
            exit 0
        fi
        sleep 1
    done

    # Force kill if still running
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Force killing production app..."
        kill -9 "$PID"
        rm -f "$PID_FILE"
    fi
}

status() {
    if [ ! -f "$PID_FILE" ]; then
        echo "Production app is not running (no PID file)"
        exit 1
    fi

    PID=$(cat "$PID_FILE")

    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Production app is running (PID: $PID)"
        echo "  Access at: http://$HOST:$PORT"
        echo "  Logs: logs/production.log"

        # Show process info
        echo ""
        ps -p "$PID" -o pid,user,%cpu,%mem,etime,cmd
    else
        echo "Production app is not running (PID $PID not found)"
        rm -f "$PID_FILE"
        exit 1
    fi
}

restart() {
    echo "Restarting production app..."
    stop
    sleep 2
    start
}

# Main
ACTION=${1:-start}

case "$ACTION" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        echo ""
        echo "  start   - Start the production app"
        echo "  stop    - Stop the production app"
        echo "  restart - Restart the production app"
        echo "  status  - Check if the production app is running"
        exit 1
        ;;
esac
