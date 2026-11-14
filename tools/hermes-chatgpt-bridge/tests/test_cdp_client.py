"""Тесты для CDP-клиента с моковым WebSocket."""

import json
import unittest
from unittest.mock import patch, MagicMock

from bridge.cdp_client import CDPClient, CDPError


class TestCDPClient(unittest.TestCase):
    """Тесты CDP-клиента."""

    def setUp(self):
        self.client = CDPClient("ws://127.0.0.1:9222")

    def test_init(self):
        """Тест: инициализация клиента."""
        client = CDPClient()
        self.assertIsNotNone(client)

    @patch("bridge.cdp_client.websocket")
    def test_connect_success(self, mock_ws):
        """Тест: успешное подключение."""
        mock_socket = MagicMock()
        mock_socket.recv.return_value = json.dumps({"result": [{"targetId": "tab1"}]})
        mock_socket.connected = True
        mock_ws.create_connection.return_value = mock_socket

        result = self.client.connect()
        self.assertTrue(result)
        self.assertIsNotNone(self.client.session_id)

    @patch("bridge.cdp_client.websocket")
    def test_connect_no_targets(self, mock_ws):
        """Тест: CDP без вкладок."""
        mock_socket = MagicMock()
        mock_socket.recv.return_value = json.dumps({"result": []})
        mock_ws.create_connection.return_value = mock_socket

        with self.assertRaises(CDPError):
            self.client.connect()

    @patch("bridge.cdp_client.websocket")
    def test_connect_error(self, mock_ws):
        """Тест: ошибка подключения."""
        mock_ws.create_connection.side_effect = Exception("Connection refused")

        with self.assertRaises(CDPError):
            self.client.connect()

    def test_disconnect(self):
        """Тест: отключение."""
        self.client.ws = MagicMock()
        self.client.disconnect()
        self.assertIsNone(self.client.ws)
        self.assertIsNone(self.client.session_id)

    def test_send_without_connection(self):
        """Тест: отправка без подключения."""
        with self.assertRaises(CDPError):
            self.client._send({"id": 1, "method": "test"})


if __name__ == "__main__":
    import json
    unittest.main()
