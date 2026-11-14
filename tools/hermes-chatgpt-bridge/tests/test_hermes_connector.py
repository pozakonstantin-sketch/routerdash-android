"""Тесты для Hermes Connector (новый JSON-RPC API)."""

import asyncio
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Добавляем путь к Hermes пакету для работы импортов
sys.path.insert(0, "/Users/konstantin/.hermes/hermes-agent")

from bridge.hermes_connector import HermesConnector, HermesConnectorError


class TestHermesConnector(unittest.TestCase):
    """Тесты Hermes Connector (новый JSON-RPC API)."""

    def setUp(self):
        self.connector = HermesConnector(
            gateway_url="ws://127.0.0.1:61650/api/ws",
            session_ticket="test_ticket"
        )

    @patch("websockets.connect")
    def test_connect_success(self, mock_connect):
        """Тест: успешное подключение."""
        # Создаем асинхронный макет WebSocket
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()
        # connect возвращает корутину, внутри которой будет mock_ws
        async def connect_coro(*args, **kwargs):
            return mock_ws
        mock_connect.side_effect = connect_coro

        async def run_test():
            result = await self.connector.connect()
            self.assertTrue(result)
            self.assertIsNotNone(self.connector._gate)
            self.assertIsNotNone(self.connector._ws)
            return result

        asyncio.run(run_test())

    @patch("websockets.connect")
    def test_connect_error(self, mock_connect):
        """Тест: ошибка подключения."""
        mock_connect.side_effect = Exception("Connection refused")

        async def run_test():
            result = await self.connector.connect()
            self.assertFalse(result)
            return result

        asyncio.run(run_test())

    @patch("websockets.connect")
    def test_create_session(self, mock_connect):
        """Тест: создание сессии."""
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws

        mock_gate = MagicMock()
        mock_gate.request = AsyncMock(return_value={
            "session_id": "test_session_id",
            "handle": {"session_id": "test_session_id"}
        })
        self.connector._gate = mock_gate

        async def run_test():
            # Тестируем только методы создания объектов (без импорта gateway)
            actor = self.connector._make_session_actor()
            handle = self.connector._make_session_create(
                "test_req_id", "/tmp/test", "hermes-chatgpt-bridge", {})
            self.assertEqual(actor.subject, "hermes-chatgpt-bridge")
            self.assertTrue(hasattr(actor, "profile_id"))
            self.assertTrue(hasattr(handle, "request_id"))
            # Тестируем flow через gateway
            result = await self.connector.create_session()
            self.assertTrue(result)
            self.assertEqual(self.connector._session_id, "test_session_id")
            return result

        asyncio.run(run_test())

    @patch("websockets.connect")
    def test_submit_task(self, mock_connect):
        """Тест: отправка задачи."""
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws

        mock_gate = MagicMock()
        mock_gate.request = AsyncMock(return_value={
            "admission_id": "test_admission",
            "outcome": "accepted"
        })
        self.connector._gate = mock_gate
        self.connector._session_id = "test_session_id"

        async def run_test():
            # Тестируем только метод создания объекта Submission
            submission = self.connector._make_submission("test_req", "test task")
            self.assertEqual(submission.request_id, "test_req")
            self.assertIn("ref", submission.__dict__)
            # Тестируем flow через gateway
            result = await self.connector.submit_task("test task")
            self.assertEqual(result, "test_admission")
            return result

        asyncio.run(run_test())

    @patch("websockets.connect")
    def test_get_events(self, mock_connect):
        """Тест: получение событий."""
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws

        mock_gate = MagicMock()
        mock_gate.request = AsyncMock(return_value={"events": [{"type": "message"}]})
        self.connector._gate = mock_gate
        self.connector._session_id = "test_session_id"

        async def run_test():
            result = await self.connector.get_events(since="1")
            self.assertEqual(len(result), 1)
            return result

        asyncio.run(run_test())

    @patch("websockets.connect")
    def test_close(self, mock_connect):
        """Тест: закрытие соединения."""
        mock_ws = AsyncMock()
        mock_connect.return_value = mock_ws

        async def run_test():
            await self.connector.connect()
            await self.connector.close()
            return True

        asyncio.run(run_test())


if __name__ == "__main__":
    unittest.main()
