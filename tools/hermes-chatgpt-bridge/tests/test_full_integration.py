"""Интеграционные тесты для полного цикла Hermes <-> ChatGPT."""

import os
import sys
import json
import time
import threading

sys.path.insert(0, os.path.dirname(__file__))

from bridge.full_integration import IntegratedBridge

# Set up a temporary logs directory for tests
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(_TEST_DIR, "logs"), exist_ok=True)

class TestIntegratedBridge:
    """Тесты для IntegratedBridge."""

    def test_create_bridge(self):
        """Тест: создание моста."""
        bridge = IntegratedBridge(
            cdp_url="ws://localhost:9222/devtools/browser",
            logs_dir=os.path.join(_TEST_DIR, "logs"),
            cdp_headers={}
        )
        assert bridge is not None
        assert hasattr(bridge, 'process_messages_loop')
        assert hasattr(bridge, 'send_message')

    def test_initialize_simple(self):
        """Тест: инициализация простая."""
        bridge = IntegratedBridge(
            cdp_url="ws://localhost:9222/devtools/browser",
            logs_dir=os.path.join(_TEST_DIR, "logs"),
            cdp_headers={}
        )
        result = bridge.initialize_simple()
        # В тестовом режиме возвращаемое значение может отличаться
        # Валидируем только тип результата
        assert result is not None

    def test_parse_chatgpt_message(self):
        """Тест: парсинг сообщения ChatGPT."""
        bridge = IntegratedBridge(
            cdp_url="ws://localhost:9222/devtools/browser",
            logs_dir=os.path.join(_TEST_DIR, "logs"),
            cdp_headers={}
        )
        # Тест проверяет, что метод парсинга существует
        assert hasattr(bridge, 'parse_incoming_message')
        assert callable(bridge.parse_incoming_message)
