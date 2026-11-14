"""Hermes Connector — обмен задачами с сессией AI-агента."""

import logging
import subprocess
import time
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class HermesConnector:
    """Клиент для отправки задач сессии AI-агента Hermes."""

    def __init__(self, bridge_dir: str):
        self.bridge_dir = bridge_dir
        self._session_running = False

    def _run_hermes(self, prompt: str, timeout: int = 300) -> str:
        """Запустить одну-shot `hermes chat -q` и получить ответ."""
        try:
            cmd = [
                "hermes", "chat", "-q",
                "--model", "upstage/solar-mini4:free",
                "--provider", "nous-portal",
                prompt
            ]
            logger.info("Запуск Hermes: %s", cmd)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.bridge_dir
            )
            if result.returncode != 0:
                logger.error("Ошибка Hermes: %s", result.stderr[:500])
                return f"[Ошибка: {result.stderr[:500]}]"
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("Таймаут выполнения Hermes")
            return "[Ошибка: таймаут]"
        except Exception as e:
            logger.error("Ошибка запуска Hermes: %s", e)
            return f"[Ошибка: {e}]"

    def send_task(self, task: str) -> str:
        """Отправить задачу в сессию Hermes и получить ответ."""
        # Защита от длинных сообщений
        task = task[:5000]
        logger.info("Отправка задачи в Hermes: %s", task)
        response = self._run_hermes(task)
        return response

    def is_healthy(self) -> bool:
        """Проверить, запущен ли Hermes."""
        try:
            # Быстрая проверка: запуск test-запроса
            result = subprocess.run(
                ["hermes", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
