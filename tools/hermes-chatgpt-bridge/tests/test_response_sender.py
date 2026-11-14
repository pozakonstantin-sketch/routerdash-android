"""Тесты для Response Sender с mock-сервером."""

import unittest
from unittest.mock import patch, MagicMock
from bridge.response_sender import ResponseSender


class TestResponseSender(unittest.TestCase):
    """Тесты Response Sender."""

    def setUp(self):
        self.mock_cdp = MagicMock()
        self.sender = ResponseSender(self.mock_cdp)

    def test_send_message_input_not_found(self):
        """Тест: элемент ввода не найден."""
        self.mock_cdp._send_sync.side_effect = [
            {"result": {"result": {"value": "Input not found"}}}
        ]
        result = self.sender.send_message("Test message")
        self.assertFalse(result)

    def test_send_message_send_not_found(self):
        """Тест: кнопка отправки не найдена."""
        self.mock_cdp._send_sync.side_effect = [
            {"result": {"result": {"value": "Input set"}}},
            {"result": {"result": {"value": "Send button not found"}}}
        ]
        result = self.sender.send_message("Test message")
        self.assertFalse(result)

    def test_send_message_success(self):
        """Тест: успешная отправка."""
        self.mock_cdp._send_sync.side_effect = [
            {"result": {"result": {"value": "Input set"}}},
            {"result": {"result": {"value": "Sent via send"}}}
        ]
        result = self.sender.send_message("Test message")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
