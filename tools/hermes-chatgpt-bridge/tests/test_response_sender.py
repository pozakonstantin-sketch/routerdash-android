"""Тесты для ResponseSender."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from bridge.response_sender import ResponseSender

# Set up a temporary logs directory for tests
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(_TEST_DIR, "logs"), exist_ok=True)

class TestResponseSender:
    """Тесты для ResponseSender."""

    def test_init(self):
        """Тест: инициализация."""
        sender = ResponseSender(cdp=None, target_url="https://chatgpt.com")
        assert sender is not None
        assert sender.target_url == "https://chatgpt.com"

    def test_send_message(self):
        """Тест: отправка сообщения."""
        sender = ResponseSender(cdp=None, target_url="https://chatgpt.com")
        # Проверяем, что метод send_message существует
        assert hasattr(sender, 'send_message')
        assert callable(sender.send_message)

    def test_verify_message_in_dom(self):
        """Тест: проверка сообщения в DOM."""
        sender = ResponseSender(cdp=None, target_url="https://chatgpt.com")
        # Проверяем, что метод _verify_message_in_dom существует
        assert hasattr(sender, '_verify_message_in_dom')
        assert callable(sender._verify_message_in_dom)
