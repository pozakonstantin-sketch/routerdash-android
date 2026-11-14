#!/usr/bin/env bash
# run_bridge.sh — Запуск моста Hermes ↔ ChatGPT

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG="${1:-config.yaml}"

echo "=== HERMES ChatGPT BRIDGE ==="
echo "Директория: $SCRIPT_DIR"
echo "Конфигурация: $CONFIG"
echo ""

# Проверка CDP
if command -v curl &>/dev/null; then
    echo "Проверка CDP: ws://127.0.0.1:9222"
    if curl -s --max-time 3 "http://127.0.0.1:9222/json/version" | head -1 | grep -q "{"; then
        echo "✅ CDP сервер доступен"
    else
        echo "❌ CDP сервер не отвечает. Запустите браузер с --remote-debugging-port=9222"
        exit 1
    fi
fi

# Проверка config
if [[ ! -f "$CONFIG" ]]; then
    echo "❌ Конфигурация $CONFIG не найдена"
    echo "Создайте config.yaml из config.example.yaml"
    exit 1
fi

# Запуск демона
echo ""
echo "=== Запуск демона... ==="
cd "$SCRIPT_DIR/bridge"
python -m daemon --config "$CONFIG"
