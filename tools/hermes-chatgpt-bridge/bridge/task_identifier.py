"""Task Identifier — распознавание задач для Hermes."""

import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TaskIdentifier:
    """Распознавание адресованных задач от пользователя."""

    # Префиксы, указывающие на адресацию к Hermes
    TASK_PREFIXES = [
        "HERMES", "ХЕРМЕС", "хермес", " Hermes", " Hermes", "🤖", "🤖",
        "бот", "боту", "боту", " Бот", "бот",
    ]

    # Регулярные выражения для распознавания адресации
    ADDRESSEE_PATTERNS = [
        re.compile(r"\b(HERMES|ХЕРМЕС|хермес)\b", re.IGNORECASE),
        re.compile(r"\b(Hermes|Hermes|hermes|Хермес)\b", re.IGNORECASE),
        re.compile(r"🤖"),
        re.compile(r"\[HERMES\]"),
        re.compile(r"\[ХЕРМЕС\]"),
    ]

    # Префиксы меток задач
    LABEL_PATTERNS = [
        re.compile(r"^\s*\[task\]\s*", re.IGNORECASE),
        re.compile(r"^\s*\[задача\]\s*", re.IGNORECASE),
        re.compile(r"^\s*TASK:\s*", re.IGNORECASE),
        re.compile(r"^\s*Задача:\s*", re.IGNORECASE),
    ]

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.include_quotes = config.get("include_quotes", False)
        self.quote_prefix = config.get("quote_prefix", ">")

    def is_task(self, message: str) -> bool:
        """Является ли сообщение адресованной задачей для Hermes?"""
        text = message.strip()

        # Проверка по префиксам
        for prefix in self.TASK_PREFIXES:
            if text.startswith(prefix):
                return True

        # Проверка по регулярным выражениям
        for pattern in self.ADDRESSEE_PATTERNS:
            if pattern.search(text):
                return True

        # Проверка по меткам задач
        for pattern in self.LABEL_PATTERNS:
            if pattern.match(text):
                return True

        # Если включены цитаты, проверяем внутреннее содержание
        if self.include_quotes and self.quote_prefix in text:
            # Ищем "task" внутри цитаты
            if re.search(r"task|задача", text, re.IGNORECASE):
                return True

        return False

    def extract_task_text(self, message: str) -> str:
        """Извлечь текст задачи из сообщения."""
        text = message.strip()

        # Убрать метки задач
        for pattern in self.LABEL_PATTERNS:
            text = pattern.sub("", text)

        # Убрать префиксы адресации
        for prefix in self.TASK_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Убрать цитаты
        if self.quote_prefix in text:
            parts = text.split(self.quote_prefix, 1)
            if len(parts) > 1:
                text = parts[1].strip()

        return text.strip()
