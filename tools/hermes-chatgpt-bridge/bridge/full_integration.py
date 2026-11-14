"""Интеграционные тесты для полного цикла Hermes <-> ChatGPT."""

import os
import json
import time
import threading
import logging
from typing import Dict, Any, Optional, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MockWebSocket:
    """Мок WebSocket для тестирования."""
    def __init__(self, messages: List[Dict[str, Any]] = None):
        self.messages = messages or []
        self._index = 0
        self._callbacks = {}
        self.closed = False
        self._lock = threading.Lock()

    def send(self, data: str):
        with self._lock:
            try:
                msg = json.loads(data)
            except Exception:
                msg = data
            self.messages.append(msg)
            if self._index < len(self.messages):
                self._index = min(self._index + 1, len(self.messages))

    def close(self):
        self.closed = True

class IntegratedBridge:
    """Интеграционный мост для тестирования."""

    def __init__(self, cdp_url: str, logs_dir: str, cdp_headers: Dict[str, str] = None):
        self.cdp_url = cdp_url
        self.logs_dir = logs_dir
        self.cdp_headers = cdp_headers or {}
        self.websocket = None
        self.running = False
        self.session_id = None
        self.tasks = {}
        self.responses = {}

    def create_test_websocket(self, mock_messages: List[Dict[str, Any]] = None):
        """Создание тестового WebSocket."""
        self.websocket = MockWebSocket(mock_messages)
        return self.websocket

    def initialize_simple(self):
        """Простая инициализация (без реального подключения)."""
        self.running = True
        self.session_id = "test-session-" + str(int(time.time() * 1000))
        logger.info(f"Мок-сессия создана: {self.session_id}")
        return {
            "success": True,
            "session_id": self.session_id,
            "mode": "mock"
        }

    def parse_incoming_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Парсинг входящего сообщения."""
        if not isinstance(message, dict):
            return None
        if message.get("method") == "message" and "params" in message:
            return message["params"]
        return None

    def send_message(self, text: str, target: str = "ChatGPT", dry_run: bool = False) -> bool:
        """Отправка сообщения."""
        if dry_run:
            logger.info(f"DRY-RUN: сообщение не отправлено в {target}: {text[:50]}...")
            return True
        logger.info(f"Сообщение отправлено в {target}: {text[:50]}...")
        return True

    def process_messages_loop(self, timeout: float = 5.0, dry_run: bool = False):
        """Обработка сообщений в цикле в тестовом режиме."""
        if dry_run:
            logger.info("DRY-RUN: цикл обработки сообщений не запущен")
            return []
        return []
