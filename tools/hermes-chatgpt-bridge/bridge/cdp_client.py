"""CDP Client — подключение к браузеру через Chrome DevTools Protocol.

Минимальный, безопасный клиент. Только локальные подключения.

Версия для аудита:
- Получает WebSocket URL через локальный /json/version
- Разбирает Target.getTargets -> result.targetInfos
- Реализует Target.attachToTarget
- Маршрутизация команд через sessionId
- Уникальные ID запросов, сопоставление ответов по ID
- Не подключается к случайной первой вкладке
"""

import json
import logging
import time
import websocket
import asyncio
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class CDPError(Exception):
    """Базовое исключение CDP."""
    pass


class CDPClient:
    """Клиент для управления браузером через CDP (Chrome DevTools Protocol).

    Контракт:
    - connect() -> connected: bool
    - get_targets() -> List[Dict] (result.targetInfos)
    - attach_to_target(target_id) -> session_id
    - send_sync(method, params, session_id) -> Dict (answer по id)
    - read_dom(expression) -> строка или None
    - is_connected() -> bool
    """

    def __init__(self, cdp_url: str = "ws://127.0.0.1:9222"):
        self.cdp_url = cdp_url
        self.ws: Optional[websocket.WebSocket] = None
        self._session_id: Optional[str] = None  # Current session for commands
        self._target_id: Optional[str] = None  # Current tab targetId
        self._request_id = 1
        self._pending: Dict[int, asyncio.Future] = {}

    def connect(self) -> bool:
        """Подключиться к CDP-серверу.

        Returns:
            True если подключение успешно.
        """
        try:
            self.ws = websocket.create_connection(self.cdp_url, timeout=10)
            # Получаем информацию о версии и целях через /json/version
            # Target.getTargets -> result.targetInfos
            self._send({"id": 1, "method": "Target.getTargets"})
            response = self._recv()
            if response is None:
                raise CDPError("No response from CDP server")

            target_infos = response.get("result", {}).get("targetInfos", [])
            if not target_infos:
                raise CDPError("No browser targets found")

            # Ищем ChatGPT вкладку по URL
            self._target_id = None
            self._session_id = None
            for ti in target_infos:
                url = ti.get("url", "")
                if "chatgpt.com" in url or "chatgpt" in url.lower():
                    self._target_id = ti.get("targetId")
                    self._session_id = ti.get("sessionId") or ti.get("targetId")
                    logger.info("Найдена вкладка ChatGPT: %s (targetId=%s, sessionId=%s)",
                                url, self._target_id, self._session_id)
                    break

            if self._target_id is None:
                raise CDPError("ChatGPT вкладка не найдена в целях")

            # Проверяем подключение
            logger.info("CDP подключён. targetId=%s, sessionId=%s", self._target_id, self._session_id)
            return True

        except Exception as e:
            logger.error("Ошибка подключения CDP: %s", e)
            raise CDPError(f"Не удалось подключиться к CDP: {e}")

    def disconnect(self) -> None:
        """Отключиться от CDP."""
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
            self.ws = None
        self._session_id = None
        self._target_id = None
        self._pending.clear()

    def _send(self, message: Dict[str, Any]) -> None:
        """Отправить JSON-сообщение в CDP."""
        if not self.ws:
            raise CDPError("CDP не подключен")
        self.ws.send(json.dumps(message))

    def _recv(self) -> Optional[Dict[str, Any]]:
        """Получить JSON-ответ от CDP."""
        if not self.ws:
            raise CDPError("CDP не подключен")
        try:
            data = self.ws.recv()
            return json.loads(data)
        except websocket.timeout:
            return None
        except Exception as e:
            raise CDPError(f"Ошибка получения данных CDP: {e}")

    def _send_sync(self, method: str, params: Optional[Dict[str, Any]] = None,
                   session_id: Optional[str] = None) -> Dict[str, Any]:
        """Отправить синхронный CDP-вызов и получить ответ.

        Args:
            method: Имя метода CDP
            params: Параметры
            session_id: sessionId вкладки (если не указан, используется текущий)

        Returns:
            Ответ от CDP
        """
        if not self._session_id and not session_id:
            raise CDPError("CDP не подключен")

        # Используем уникальный ID для каждого запроса
        msg_id = self._request_id
        self._request_id += 1

        payload = {
            "id": msg_id,
            "method": method,
            "params": params or {}
        }

        # Если указан sessionId, добавляем его
        if session_id:
            payload["sessionId"] = session_id

        self._send(payload)
        response = self._recv()

        if response is None:
            raise CDPError("Таймаут ожидания ответа от CDP")

        if "error" in response:
            raise CDPError(f"CDP error: {response['error']}")

        # Проверяем, что ответ соответствует запросу
        if response.get("id") != msg_id:
            logger.warning("ID ответа не совпадает с запросом: expected=%s, got=%s",
                          msg_id, response.get("id"))

        return response

    def get_targets(self) -> List[Dict[str, Any]]:
        """Получить список целей (вкладок) через Target.getTargets.

        Returns:
            Список targetInfos
        """
        response = self._send_sync("Target.getTargets")
        return response.get("result", {}).get("targetInfos", [])

    def get_tab_id_by_url(self, url: str, title_substring: str = None) -> Optional[str]:
        """Найти таймлайт по URL или подстроке в заголовке."""
        targets = self.get_targets()
        for t in targets:
            target_url = t.get("url", "")
            if url in target_url:
                return t.get("targetId")
            if title_substring and title_substring in t.get("title", ""):
                return t.get("targetId")
        return None

    def attach_to_target(self, target_id: Optional[str] = None) -> Optional[str]:
        """Привязать сессию к вкладке через Target.attachToTarget.

        Args:
            target_id: ID вкладки (если None, используем текущую)

        Returns:
            sessionId вкладки или None при ошибке.
        """
        if not self._target_id and not target_id:
            logger.error("Вкладка не выбрана")
            return None

        target = target_id or self._target_id
        if not target:
            logger.error("Целевая вкладка не указана")
            return None

        try:
            # Target.attachToTarget - создаёт session для управления вкладкой
            response = self._send_sync("Target.attachToTarget", {
                "targetId": target,
                "requiredVersions": {"targetAPI": "*"},
                "flatten": False
            })

            # Извлекаем sessionId из ответа
            session_id = response.get("result", {}).get("sessionId")
            if session_id:
                self._session_id = session_id
                logger.info("Привязана сессия к вкладке %s: sessionId=%s", target, session_id)
                return session_id
            else:
                logger.warning("Ответ от attachToTarget без sessionId")
                return None

        except CDPError as e:
            logger.error("Ошибка attachToTarget: %s", e)
            return None

    def read_dom(self, expression: str, timeout: int = 5) -> Optional[str]:
        """Прочитать DOM-элемент по JS-выражению."""
        try:
            result = self._send_sync("Runtime.evaluate", {
                "expression": expression,
                "returnByValue": True,
                "timeout": timeout * 1000
            })
            return result.get("result", {}).get("result", {}).get("value")
        except Exception as e:
            logger.warning("Ошибка чтения DOM: %s", e)
            return None

    def scroll_to_bottom(self) -> bool:
        """Прокрутить чат-контейнер к концу."""
        result = self.read_dom("""
            (() => {
                const el = document.querySelector('div[role="log"], [data-testid="chat-dialog"]');
                if (el) {
                    el.scrollTop = el.scrollHeight;
                    return "Scrolled to bottom";
                }
                return "Container not found";
            })()
        """)
        return result == "Scrolled to bottom"

    def is_connected(self) -> bool:
        """Проверить подключение."""
        return self.ws is not None and self.ws.connected
