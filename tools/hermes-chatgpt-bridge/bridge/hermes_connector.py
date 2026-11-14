"""Hermes Connector — подключение к существующему gateway через JSON-RPC v0.23.1.

Подключается к запущенному gateway (ws://127.0.0.1:61650/api/ws) с использованием
официального протокола hermes-gateway-v1. JSON-RPC методы:
- session.create      — создать или восстановить сессию
- prompt.submit       — отправить задачу в сессию
- session.events.since — читать события сессии

Интерфейс предназначен для подключения к существующему gateway (не запуск второго агента).
Первый JSON-RPC запрос — session.create, а не допуск соединения.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class HermesConnectorError(Exception):
    """Базовое исключение Connector."""


class GatewayClient:
    """JSON-RPC клиент для gateway (hermes-gateway-v1 protocol).

    Передаёт только сериализуемые словари структур.
    """

    def __init__(self, ws, loop):
        self.ws = ws
        self._loop = loop
        self.pending: Dict[int, asyncio.Future] = {}
        self.sequence = 0
        self._connected = False

    async def _reader(self):
        import websockets
        try:
            async for raw in self.ws:
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "id" in frame:
                    future = self.pending.get(frame["id"])
                    if future is not None and not future.done():
                        if "error" in frame:
                            future.set_exception(HermesConnectorError(
                                frame["error"].get("message", "request_failed")))
                        else:
                            future.set_result(frame.get("result", {}))
                elif "method" in frame and frame["method"] != "notification":
                    # Event notification — игнорируем, так как используем только request/response
                    pass
        except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
            pass

    async def request(self, method: str, params: Dict[str, Any], _timeout: float = 60.0) -> Dict[str, Any]:
        """Отправить JSON-RPC запрос и дождаться ответа по ID."""
        if not self._connected:
            raise HermesConnectorError("Gateway не подключён")

        request_id = self.sequence
        self.sequence += 1
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        future = self._loop.create_future()
        self.pending[request_id] = future

        try:
            await self.ws.send(json.dumps(request))
            try:
                response = await asyncio.wait_for(future, timeout=_timeout)
                return response
            except asyncio.TimeoutError:
                del self.pending[request_id]
                raise HermesConnectorError(f"Таймаут ожидания ответа для {method}")

        except Exception:
            del self.pending[request_id]
            raise

    def mark_connected(self):
        self._connected = True

    def close(self):
        if self.ws:
            self.ws.close()


class HermesConnector:
    """Клиент для подключения к существующему gateway через JSON-RPC v0.23.1.

    Контракт (поддерживается оригинальным кодом Hermes v0.23.1):
    - session.create(params)  → {"session_id": str, "stored_session_id": str, "message_count": int}
    - prompt.submit(params)   → {"admission_id": str, "ref": {...}, "sequence": int, "status": str, "outcome": str}
    - session.events.since(params) → {"events": [...], "replay_epoch": str, "last_sequence": int}
    """

    GATEWAY_WS_PROTOCOL = "hermes-gateway-v1"
    GATEWAY_WS_TICKET_PREFIX = "hermes-gateway-ticket."

    def __init__(
        self,
        gateway_url: str,
        session_ticket: str,
        gateway_host: str = "127.0.0.1",
        gateway_port: int = 61650,
        timeout: float = 60.0,
    ):
        """Конструктор.

        Args:
            gateway_url: WebSocket URL, например 'ws://127.0.0.1:61650/api/ws'
            session_ticket: Одноразовый билет сессии от 'hermes gateway attach'
            gateway_host: Хост gateway (по умолчанию 127.0.0.1)
            gateway_port: Порт gateway (по умолчанию 61650)
            timeout: Таймаут ожидания ответа (секунды)
        """
        self.gateway_url = gateway_url
        self.session_ticket = session_ticket
        self.gateway_host = gateway_host
        self.gateway_port = gateway_port
        self.timeout = timeout
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._gate: Optional[GatewayClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._run_task: Optional[asyncio.Task] = None
        self._session_id: Optional[str] = None
        self._connected = False

    async def connect(self) -> bool:
        """Подключиться к gateway через WebSocket.

        Returns:
            True если подключение успешно, иначе False.
            ВАЖНО: успешное подключение НЕ означает успешное выполнение задачи.
            Задача выполняется только после session.create + prompt.submit.
        """
        try:
            import websockets
            self._loop = asyncio.get_event_loop()
            self._ws = await websockets.connect(
                self.gateway_url,
                subprotocols=[
                    self.GATEWAY_WS_PROTOCOL,
                    self.GATEWAY_WS_TICKET_PREFIX + self.session_ticket
                ],
                open_timeout=10.0
            )
            self._gate = GatewayClient(self._ws, self._loop)
            self._run_task = asyncio.ensure_future(self._gate._reader())
            self._connected = True
            logger.info("Подключено к gateway")
            return True
        except Exception as e:
            logger.error("Ошибка подключения к gateway: %s", e)
            self._connected = False
            return False

    async def create_session(
        self,
        cwd: str = None,
        source: str = "hermes-chatgpt-bridge",
        model: str = "upstage/solar-mini4:free",
        provider: str = "nous-portal"
    ) -> bool:
        """Создать или восстановить сессию через session.create.

        Args:
            cwd: Рабочая директория агента
            source: Источник задачи
            model: Модель AI-агента
            provider: Провайдер AI-агента

        Returns:
            True если сессия успешно создана или восстановлена.
            ВАЖНО: не путать с успешным выполнением задачи.
        """
        if not self._connected or not self._gate:
            raise HermesConnectorError("Gateway не подключён (connect() сначала)")

        request_id = str(uuid.uuid4())
        params = {
            "profile": "/Users/konstantin/.hermes",
            "source": source,
            "cwd_override": cwd or "/Users/konstantin/Тест",
            "model": model,
            "provider": provider,
            "idempotency_key": f"{source}:{uuid.uuid4().hex[:8]}"
        }

        try:
            result = await self._gate.request(
                "session.create",
                params=params,
                _timeout=self.timeout
            )
            # Извлекаем session_id из ответа
            self._session_id = result.get("session_id") or result.get("stored_session_id")
            if not self._session_id:
                logger.error("Нет session_id в ответе: %s", result)
                return False

            logger.info("Сессия создана/восстановлена: %s", self._session_id)
            return True

        except Exception as e:
            logger.error("Ошибка session.create: %s", e)
            return False

    async def submit_task(self, task: str) -> str:
        """Отправить задачу в сессию через prompt.submit.

        Args:
            task: Текст задачи для выполнения

        Returns:
            admission_id или пустая строка. Не является гарантией успешного результата.
        """
        if not self._connected or not self._gate:
            raise HermesConnectorError("Gateway не подключён (connect() сначала)")

        if not self._session_id:
            raise HermesConnectorError("Сессия не создана (create_session() сначала)")

        request_id = str(uuid.uuid4())
        params = {
            "session_id": self._session_id,
            "payload": {
                "text": task,
                "toolset": "default"
            }
        }

        try:
            result = await self._gate.request(
                "prompt.submit",
                params=params,
                _timeout=self.timeout
            )
            admission_id = result.get("admission_id") or ""
            outcome = result.get("outcome", "")
            logger.info("Задача отправлена: admission=%s outcome=%s", admission_id, outcome)
            return admission_id or str(result)
        except asyncio.TimeoutError:
            logger.error("Таймаут prompt.submit для задачи: %s", task[:80])
            return f"[timeout]"
        except Exception as e:
            logger.error("Ошибка prompt.submit: %s", e)
            return f"[error: {e}]"

    async def get_task_result(self, admission_id: str, timeout: float = 600.0) -> str:
        """Получить результат выполнения задачи.

        Args:
            admission_id: admission_id от prompt.submit
            timeout: Максимальное время ожидания (секунды)

        Returns:
            Результат выполнения задачи.
        """
        if not self._connected or not self._gate:
            raise HermesConnectorError("Gateway не подключён")

        # Ждём завершения задачи через events или polling
        start = time.time()
        while time.time() - start < timeout:
            try:
                events = await self._gate.request(
                    "session.events.since",
                    params={
                        "session_id": self._session_id,
                        "since": ""  # начало отсчёта
                    },
                    _timeout=10.0
                )
                # Ищем результат задачи
                events_list = events.get("events", [])
                for event in events_list:
                    if event.get("type") == "completion" and event.get("admission_id") == admission_id:
                        payload = event.get("payload", {})
                        if payload.get("status") == "completed":
                            return payload.get("response", "Задача завершена без ответа")

                # Ошибка или отказ
                for event in events_list:
                    if event.get("type") == "error" and event.get("admission_id") == admission_id:
                        return f"Ошибка задачи: {event.get('message', 'Unknown error')}"

            except Exception as e:
                logger.warning("Ошибка ожидания результата: %s", e)

            # Перезапрашиваем события
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                raise

        return "[timeout waiting task result]"

    def get_session_id(self) -> Optional[str]:
        """Вернуть session_id."""
        return self._session_id

    def is_connected(self) -> bool:
        """Проверить, подключен ли клиент к Gateway."""
        return self._connected

    async def close(self):
        """Закрыть соединение."""
        self._connected = False
        if self._ws:
            await self._ws.close()
        if self._gate:
            self._gate.close()
