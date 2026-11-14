"""Тесты для TaskIdentifier."""

import pytest

from bridge.task_identifier import TaskIdentifier


class TestTaskIdentifier:
    """Тесты распознавания задач."""

    def test_default_config(self):
        cfg = {}
        ti = TaskIdentifier(cfg)
        assert ti.include_quotes is False

    def test_task_with_prefix(self):
        """Тест: сообщение с префиксом HERMES — задача."""
        cfg = {}
        ti = TaskIdentifier(cfg)
        assert ti.is_task("HERMES помоги мне")
        assert ti.is_task("хермес проверь это")

    def test_task_with_emoticon(self):
        """Тест: сообщение с 🤖 — задача."""
        cfg = {}
        ti = TaskIdentifier(cfg)
        assert ti.is_task("🤖 проверь это")

    def test_normal_message_not_task(self):
        """Тест: обычное сообщение — не задача."""
        cfg = {}
        ti = TaskIdentifier(cfg)
        assert not ti.is_task("Привет, как дела?")
        assert not ti.is_task("Какой сегодня прогноз погоды?")

    def test_quote_with_task(self):
        """Тест: цитата с задачей."""
        cfg = {"include_quotes": True, "quote_prefix": ">"}
        ti = TaskIdentifier(cfg)
        assert ti.is_task("> HERMES помоги")
        assert not ti.is_task("> Просто цитата без задачи")

    def test_extract_task_text(self):
        """Тест: извлечение текста задачи."""
        cfg = {}
        ti = TaskIdentifier(cfg)
        text = ti.extract_task_text("HERMES сделай это")
        assert "сделай это" in text

    def test_extract_task_label(self):
        """Тест: метка [task] удаляется."""
        cfg = {}
        ti = TaskIdentifier(cfg)
        text = ti.extract_task_text("[task] проверь это")
        assert "проверь это" in text
