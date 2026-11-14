"""Тесты для MessageReader."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from bridge.message_reader import MessageReader
from bridge.state_manager import StateManager

# Set up a temporary logs directory for tests
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(_TEST_DIR, "logs"), exist_ok=True)

class TestMessageReader:
    """Тесты для MessageReader."""

    def test_init(self):
        """Тест: инициализация."""
        # Создаем mock state manager
        state = StateManager(os.path.join(_TEST_DIR, "logs", "mock_state.db"))
        reader = MessageReader(cdp=None, state=state)
        assert reader is not None
        # Проверяем, что метод read_new_messages существует
        assert hasattr(reader, 'read_new_messages')
        assert callable(reader.read_new_messages)
        # Проверяем, что метод get_dialog_messages существует
        assert hasattr(reader, 'get_dialog_messages')
        assert callable(reader.get_dialog_messages)
        # Удаляем mock файл
        try:
            os.remove(state.state_file)
        except Exception:
            pass
