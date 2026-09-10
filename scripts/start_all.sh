#!/usr/bin/env bash
# Start all ForestGuard services in background
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

export PYTHONPATH="$DIR"
if [ -f "$DIR/.env" ]; then
    set -a
    source "$DIR/.env"
    set +a
fi

mkdir -p data_storage/logs data_storage/images

echo "[*] Stopping any existing ForestGuard processes..."
bash "$DIR/scripts/stop_all.sh"

echo "[*] Starting AI Inference Service on port ${AI_PORT:-8002}..."
nohup python3 scripts/run_ai.py > data_storage/logs/ai_service.log 2>&1 &
echo $! > data_storage/ai.pid

echo "[*] Starting TCP Ingestion Service on port 20000..."
nohup python3 scripts/run_ingestion.py > data_storage/logs/ingestion.log 2>&1 &
echo $! > data_storage/ingestion.pid

echo "[*] Starting Web Backend & Map Dashboard on port ${WEB_PORT:-8000}..."
nohup python3 scripts/run_web.py > data_storage/logs/web_backend.log 2>&1 &
echo $! > data_storage/web.pid

sleep 2
echo "[+] Services started. Checking status:"
bash "$DIR/scripts/status.sh"
