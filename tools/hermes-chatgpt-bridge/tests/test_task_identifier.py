"""Тесты для TaskIdentifier - распознавание задач."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools", "hermes-chatgpt-bridge"))

from bridge.task_identifier import TaskIdentifier


class TestTaskIdentifier:
    """Тесты для TaskIdentifier."""

    def test_identify_task(self):
        """Тест: распознавание адресованных к Hermes сообщений."""
        identifier = TaskIdentifier({})

        # Тест: сообщение с префиксом HERMES
        assert identifier.is_task("HERMES В задаче: простой текст") is True

        # Тест: сообщение с префиксом ХЕРМЕС
        assert identifier.is_task("ХЕРМЕС: задача") is True

        # Тест: сообщение с меткой [задача]
        assert identifier.is_task("[задача]: простой текст") is True

        # Тест: сообщение с меткой TASK:
        assert identifier.is_task("TASK: простой текст") is True

        # Тест: сообщение без адресации
        assert identifier.is_task("Это обычное сообщение") is False

        # Тест: пустое сообщение
        assert identifier.is_task("") is False

    def test_extract_task_text(self):
        """Тест: извлечение текста задачи."""
        identifier = TaskIdentifier({})

        # Тест: обычное сообщение
        result = identifier.extract_task_text("HELLOWORLD В задаче: простой текст")
        assert "В задаче: простой текст" in result

        # Тест: сообщение с меткой задачи
        result = identifier.extract_task_text("[задача]: простой текст")
        assert "простой текст" in result

        # Тест: пустое сообщение
        result = identifier.extract_task_text("HELLOWORLD")
        assert result == "HELLOWORLD"
