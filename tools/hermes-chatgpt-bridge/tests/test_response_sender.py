"""Тесты для Response Sender — отправка результата в ChatGPT через CDP."""

import unittest
from unittest.mock import patch, MagicMock
from bridge.response_sender import ResponseSender
from bridge.cdp_client import CDPClient, CDPError


class TestResponseSender(unittest.TestCase):
    """Тесты Sender'а."""

    def setUp(self):
        self.mock_cdp = MagicMock(spec=CDPClient)
        self.sender = ResponseSender(self.mock_cdp, target_url="https://chatgpt.com")

    @patch("bridge.response_sender.time.sleep")
    @patch("bridge.response_sender.logger")
    def test_send_message_success(self, mock_logger, mock_sleep):
        """Тест: успешная отправка."""
        self.mock_cdp._send_sync.side_effect = [
            {"result": {"result": {"value": "Input set"}}},
            {"result": {"result": {"value": "Sent via send"}}},
            {"result": {"result": {"value": "[{'id': 'test123', 'text': 'Hello'}]"}}}
        ]
        result = self.sender.send_message("Test message")
        self.assertTrue(result)
        self.assertEqual(self.mock_cdp._send_sync.call_count, 3)

    @patch("bridge.response_sender.time.sleep")
    @patch("bridge.response_sender.logger")
    def test_send_message_input_not_found(self, mock_logger, mock_sleep):
        """Тест: элемент ввода не найден."""
        self.mock_cdp._send_sync.side_effect = [
            {"result": {"result": {"value": "Input not found"}}}
        ]
        result = self.sender.send_message("Test message")
        self.assertFalse(result)

    @patch("bridge.response_sender.time.sleep")
    @patch("bridge.response_sender.logger")
    def test_send_message_send_not_found(self, mock_logger, mock_sleep):
        """Тест: кнопка отправки не найдена."""
        self.mock_cdp._send_sync.side_effect = [
            {"result": {"result": {"value": "Input set"}}},
            {"result": {"result": {"value": "Send button not found"}}}
        ]
        result = self.sender.send_message("Test message")
        self.assertFalse(result)

    def test_init(self):
        """Тест: инициализация."""
        self.assertEqual(self.sender.cdp, self.mock_cdp)
        self.assertEqual(self.sender.target_url, "https://chatgpt.com")


if __name__ == "__main__":
    unittest.main()
