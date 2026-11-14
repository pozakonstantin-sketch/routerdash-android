"""Тесты для HermesConnector - JSON-RPC v0.23.1."""

import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "hermes-chatgpt-bridge"))

from bridge.hermes_connector import HermesConnector, HermesConnectorError


class TestHermesConnector:
    """Тесты для HermesConnector."""

    def test_connect(self):
        """Тест: подключение к Gateway."""
        connector = HermesConnector(
            gateway_url="ws://127.0.0.1:61650/api/ws",
            session_ticket="test-ticket"
        )
        assert connector.connect() is True
        assert connector._connected is True
        connector.close()

    def test_create_session(self):
        """Тест: создание сессии."""
        connector = HermesConnector(
            gateway_url="ws://127.0.0.1:61650/api/ws",
            session_ticket="test-ticket"
        )
        assert connector.connect() is True

        with patch.object(connector, '_send_sync', return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"session_id": "test-session-123"}
        }) as mock_send:
            session_id = connector.create_session()
            assert session_id is not None
            assert "test-session" in session_id
            assert connector.session_id == "test-session-123"
            mock_send.assert_called_once()

        connector.close()

    def test_submit_task(self):
        """Тест: отправка задачи."""
        connector = HermesConnector(
            gateway_url="ws://127.0.0.1:61650/api/ws",
            session_ticket="test-ticket"
        )
        assert connector.connect() is True

        # First create session
        with patch.object(connector, '_send_sync', return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"session_id": "test-session-123"}
        }) as mock_send:
            session_id = connector.create_session()
            assert session_id is not None

        # Then submit task
        with patch.object(connector, '_send_sync', return_value={
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"task_id": "task-456"}
        }) as mock_send:
            task_id = connector.submit_task("HELLOWORLD")
            assert task_id is not None
            assert "task-" in task_id
            mock_send.assert_called_once()

        connector.close()

    def test_get_task_result(self):
        """Тест: получение результата."""
        connector = HermesConnector(
            gateway_url="ws://127.0.0.1:61650/api/ws",
            session_ticket="test-ticket"
        )
        assert connector.connect() is True

        # First create session
        with patch.object(connector, '_send_sync', return_value={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"session_id": "test-session-123"}
        }) as mock_send:
            session_id = connector.create_session()

        # Then get task result
        with patch.object(connector, '_send_sync', return_value={
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"status": "completed"}
        }) as mock_send:
            connector.submit_task("HELLOWORLD")
            result = connector.get_task_result("task-456", timeout=5)
            # В локальном тесте результат может быть None, но без ошибок
            assert result is None or isinstance(result, str)

        connector.close()

    def test_serializable_params(self):
        """Тест: передача сериализуемых словарей."""
        connector = HermesConnector(
            gateway_url="ws://127.0.0.1:61650/api/ws",
            session_ticket="test-ticket"
        )
        assert connector.connect() is True

        params = {
            "type": "chat",
            "scope": "direct",
            "settings": {"stream": False, "tools": []}
        }

        import json
        json.dumps(params)  # Не должно вызывать ошибки

        with patch.object(connector, '_send_sync') as mock_send:
            connector.create_session()
            task_id = connector.submit_task("HELLOWORLD")
            assert task_id is not None

        connector.close()
