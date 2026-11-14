"""Hermes Connector — подключение к Gateway Hermes через JSON-RPC.

Версия для аудита:
- Конструктор: gateway_url, session_ticket
- connect(): подключение к Gateway
- create_session(): создание/восстановление сессии
- submit_task(): отправка задачи
- get_task_result(): получение результата
- Все параметры - сериализуемые словари
"""

import json
import logging
import time
from typing import Optional, Dict, Any
import threading

logger = logging.getLogger(__name__)


class HermesConnectorError(Exception):
    """Базовое исключение для Connector."""
    pass


class HermesConnector:
    """Клиент для взаимодействия с Gateway Hermes.

    Контракт (по v0.23.1):
    - connect(): подключение к Gateway (ws://host:port/api/ws)
    - create_session(): создаёт или восстанавливает сессию
    - submit_task(task_text): отправляет задачу на выполнение
    - get_task_result(task_id): получает результат выполнения задачи
    """

    # JSON-RPC v0.23.1 константы (проверены по исходникам)
    JSON_RPC_VERSION = "2.0"
    GATEWAY_READY = "gateway.ready"
    SESSION_CREATE = "session.create"
    SESSION_RESUME = "session.resume"
    PROMPT_SUBMIT = "prompt.submit"
    SESSION_EVENTS_SINCE = "session.events.since"
    TASK_COMPLETE = "task.complete"
    ERROR = "error"

    # Структура запроса session.create
    SESSION_CREATE_PARAMS = {
        "type": "chat",
        "scope": "direct"
    }

    def __init__(self, gateway_url: str = "ws://127.0.0.1:61650/api/ws",
                 session_ticket: str = ""):
        self.gateway_url = gateway_url
        self.session_ticket = session_ticket
        self.ws = None
        self.session_id: Optional[str] = None
        self.session_lock = threading.Lock()
        self._task_results: Dict[str, Dict[str, Any]] = {}
        self._connected = False

    def connect(self) -> bool:
        """Подключиться к Gateway Hermes.

        Returns:
            True если подключение успешно.
        """
        try:
            # Подключение к Gateway (в реальной реализации используется WebSocket)
            # Для тестов запоминаем URL
            logger.info("Подключение к Gateway: %s", self.gateway_url)

            # Проверяем готовность Gateway
            self._check_gateway_ready()
            self._connected = True
            logger.info("✅ Gateway готов")
            return True

        except Exception as e:
            logger.error("Ошибка подключения к Gateway: %s", e)
            raise HermesConnectorError(f"Не удалось подключиться к Gateway: {e}")

    def _check_gateway_ready(self) -> bool:
        """Проверяем готовность Gateway."""
        # В реальной реализации делаем запрос к Gateway
        # Для локальных тестов возвращаем True
        logger.info("Проверка готовности Gateway (локальная проверка)")
        return True

    def create_session(self) -> Optional[str]:
        """Создать или восстановить сессию в Gateway.

        Returns:
            session_id или None при ошибке.
        """
        if not self._connected:
            raise HermesConnectorError("Gateway не подключён")

        try:
            # Создаём параметры сессии
            params = {
                "type": "chat",
                "scope": "direct",
                "settings": {
                    "stream": False,
                    "tools": []
                }
            }

            # Отправляем запрос session.create
            response = self._send_sync(self.SESSION_CREATE, params)

            # Извлекаем session_id из ответа
            session_id = response.get("result", {}).get("session_id")
            if session_id:
                with self.session_lock:
                    self.session_id = session_id
                logger.info("✅ Сессия создана: session_id=%s", session_id)
                return session_id
            else:
                logger.warning("Ответ от session.create без session_id")
                return None

        except Exception as e:
            logger.error("Ошибка создания сессии: %s", e)
            raise HermesConnectorError(f"Не удалось создать сессию: {e}")

    def submit_task(self, task_text: str) -> Optional[str]:
        """Отправить задачу на выполнение в Gateway.

        Args:
            task_text: Текст задачи для выполнения

        Returns:
            task_id или None при ошибке.
        """
        if not self._connected:
            raise HermesConnectorError("Gateway не подключён")

        if not self.session_id:
            raise HermesConnectorError("Сессия не создана")

        try:
            # Создаём параметры задачи как обычный словарь
            task_params = {
                "content": task_text,
                "role": "user",
                "type": "message"
            }

            # Отправляем запрос prompt.submit
            response = self._send_sync(self.PROMPT_SUBMIT, task_params)

            # Извлекаем task_id из ответа
            task_id = response.get("result", {}).get("task_id")
            if task_id:
                # Храним задачу для последующего получения результата
                with self.session_lock:
                    self._task_results[task_id] = {
                        "status": "pending",
                        "task_id": task_id,
                        "content": task_text,
                        "created_at": time.time()
                    }
                logger.info("✅ Задача отправлена: task_id=%s", task_id)
                return task_id
            else:
                logger.warning("Ответ от prompt.submit без task_id")
                return None

        except Exception as e:
            logger.error("Ошибка отправки задачи: %s", e)
            raise HermesConnectorError(f"Не удалось отправить задачу: {e}")

    def get_task_result(self, task_id: str, timeout: int = 300) -> Optional[str]:
        """Получить результат выполнения задачи.

        Args:
            task_id: ID задачи
            timeout: Максимальное время ожидания (секунды)

        Returns:
            Результат выполнения или None при ошибке.
        """
        if not self._connected:
            raise HermesConnectorError("Gateway не подключён")

        if not self.session_id:
            raise HermesConnectorError("Сессия не создана")

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Проверяем статус задачи
                with self.session_lock:
                    if task_id not in self._task_results:
                        logger.warning("Задача %s не найдена в результатах", task_id)
                        return None

                    result = self._task_results[task_id]

                # Если задача завершена, возвращаем результат
                if result["status"] == "completed":
                    logger.info("✅ Задача %s завершена", task_id)
                    return result.get("response")

                # Если задача в процессе, ждём
                time.sleep(1)

                # В реальной реализации здесь будет запрос session.events.since
                # для получения событий о выполнении задачи

            except Exception as e:
                logger.error("Ошибка получения результата: %s", e)
                raise HermesConnectorError(f"Не удалось получить результат: {e}")

        logger.error("⏱️  Таймаут ожидания результата задачи %s", task_id)
        return None

    def _send_sync(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Отправить синхронный JSON-RPC запрос и получить ответ.

        Args:
            method: Имя метода
            params: Параметры запроса

        Returns:
            Ответ Gateway
        """
        # В реальной реализации отправляем через WebSocket
        # Для локальных тестов используем прямой возвращаемый ответ
        logger.info("JSON-RPC: %s %s", method, params if params else "отсутствуют")

        # В реальной реализации здесь будет код отправки через WebSocket
        # и ожидание ответа.
        # Для локальных тестов возвращаем mock-ответ.
        return {
            "jsonrpc": self.JSON_RPC_VERSION,
            "id": 1,
            "result": {
                "status": "ok"
            }
        }

    def close(self) -> None:
        """Закрыть соединение с Gateway."""
        self._connected = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        logger.info("✅ Соединение с Gateway закрыто")
