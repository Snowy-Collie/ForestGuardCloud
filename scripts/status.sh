#!/usr/bin/env bash
echo "=== ForestGuard Listening Ports ==="
ss -tulpn | grep -E ":20000|:8000|:8002"
echo "=== ForestGuard Running Processes ==="
ps aux | grep -E "run_ai|run_ingestion|run_web|main.py|web/app.py" | grep -v grep
