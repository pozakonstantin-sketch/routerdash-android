#!/usr/bin/env bash
# stop_bridge.sh — Остановка моста

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== HERMES ChatGPT BRIDGE — остановка ==="

# Найти процесс демона
PID=$(pgrep -f "bridge/daemon" 2>/dev/null || true)
if [[ -n "$PID" ]]; then
    echo "Завершение процесса: $PID"
    kill "$PID" 2>/dev/null || true
    sleep 2
    echo "✅ Демон остановлен"
else
    echo "Демон не запущен или уже остановлен"
fi
