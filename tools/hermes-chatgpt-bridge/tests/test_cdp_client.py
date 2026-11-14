"""Тесты для CDPClient."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from bridge.cdp_client import CDPClient

# Set up a temporary logs directory for tests
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(_TEST_DIR, "logs"), exist_ok=True)

class TestCDPClient:
    """Тесты для CDPClient."""

    def test_init(self):
        """Тест: инициализация."""
        client = CDPClient(cdp_url="ws://localhost:9222/devtools/browser")
        assert client is not None
        assert client.cdp_url == "ws://localhost:9222/devtools/browser"

    def test_connecting(self):
        """Тест: подключение."""
        client = CDPClient(cdp_url="ws://localhost:9222/devtools/browser")
        # В тестовом режиме без реального подключения
        # проверяем, что метод connect существует
        assert hasattr(client, 'connect')
        assert callable(client.connect)

    def test_send_sync(self):
        """Тест: синхронная отправка."""
        client = CDPClient(cdp_url="ws://localhost:9222/devtools/browser")
        # Проверяем, что метод _send_sync существует
        assert hasattr(client, '_send_sync')
        assert callable(client._send_sync)

    def test_get_targets(self):
        """Тест: получение целей."""
        client = CDPClient(cdp_url="ws://localhost:9222/devtools/browser")
        # Проверяем, что метод get_targets существует
        assert hasattr(client, 'get_targets')
        assert callable(client.get_targets)

    def test_get_tab_id_by_url(self):
        """Тест: получение tab_id по URL."""
        client = CDPClient(cdp_url="ws://localhost:9222/devtools/browser")
        # Проверяем, что метод get_tab_id_by_url существует
        assert hasattr(client, 'get_tab_id_by_url')
        assert callable(client.get_tab_id_by_url)

    def test_attach_to_target(self):
        """Тест: подключение к цели."""
        client = CDPClient(cdp_url="ws://localhost:9222/devtools/browser")
        # Проверяем, что метод attach_to_target существует
        assert hasattr(client, 'attach_to_target')
        assert callable(client.attach_to_target)

    def test_read_dom(self):
        """Тест: чтение DOM."""
        client = CDPClient(cdp_url="ws://localhost:9222/devtools/browser")
        # Проверяем, что метод read_dom существует
        assert hasattr(client, 'read_dom')
        assert callable(client.read_dom)
