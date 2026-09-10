#!/usr/bin/env bash
# Stop all ForestGuard services
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Kill by PID files if present
for pidfile in "$DIR/data_storage/"*.pid; do
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null
        fi
        rm -f "$pidfile"
    fi
done

# Kill any remaining python processes bound to ports 20000, 8000, 8002
for port in 20000 8000 8002; do
    PIDS=$(ss -tulpn "sport = :$port" 2>/dev/null | grep -o 'pid=[0-9]*' | cut -d= -f2)
    for p in $PIDS; do
        kill -9 "$p" 2>/dev/null
    done
done

# Kill any legacy python main.py or web/app.py in forestguard
pkill -f "python3 main.py" 2>/dev/null || true
pkill -f "python3 web/app.py" 2>/dev/null || true
pkill -f "scripts/run_ingestion.py" 2>/dev/null || true
pkill -f "scripts/run_ai.py" 2>/dev/null || true
pkill -f "scripts/run_web.py" 2>/dev/null || true

echo "[+] All ForestGuard services stopped."
