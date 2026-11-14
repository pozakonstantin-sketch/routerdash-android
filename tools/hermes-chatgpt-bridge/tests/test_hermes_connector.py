"""Тесты для Hermes Connector."""

import unittest
from unittest.mock import patch, MagicMock
from bridge.hermes_connector import HermesConnector


class TestHermesConnector(unittest.TestCase):
    """Тесты Hermes Connector."""

    def setUp(self):
        self.bridge_dir = "/tmp/test_bridge"
        self.connector = HermesConnector(self.bridge_dir)

    @patch("bridge.hermes_connector.subprocess")
    def test_start_server_success(self, mock_subprocess):
        """Тест: успешный запуск сервера."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_subprocess.Popen.return_value = mock_proc

        # Мок ответа сервера
        with patch("urllib.request.urlopen") as mock_urlopen:
            class MockResponse:
                status = 200
                def read(self):
                    return b"OK"
            mock_urlopen.return_value = MockResponse()
            result = self.connector.start_server(timeout=5)
            self.assertTrue(result)

    def test_is_healthy(self):
        """Тест: проверка здоровья."""
        self.connector.serve_host = "127.0.0.1"
        self.connector.serve_port = 9119
        # Замокаем запрос
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_urlopen.return_value = mock_resp
            result = self.connector.is_healthy()
            self.assertTrue(result)

    @patch("bridge.hermes_connector.HermesConnector._create_session")
    @patch("bridge.hermes_connector.HermesConnector._api_call")
    def test_send_task(self, mock_api, mock_create):
        """Тест: отправка задачи."""
        mock_create.return_value = "test_session"
        mock_api.return_value = {"response": "Test response"}
        # Имитируем запущенный сервер
        self.connector.server_process = MagicMock()
        self.connector.server_process.poll.return_value = None
        result = self.connector.send_task("Test task")
        self.assertEqual(result, "Test response")


if __name__ == "__main__":
    unittest.main()
