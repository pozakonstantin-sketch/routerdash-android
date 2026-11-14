"""Hermes Connector — подключение к существующему gateway через JSON-RPC.

Подключается к запущенному gateway (ws://127.0.0.1:61650/api/ws) с использованием
официального протокола hermes-gateway-v1. Методы:
- session.create — создать сессию
- session.resume — восстановить сессию
- prompt.submit — отправить задачу
- session.events.since — читать события

Подключение к существующему gateway (не запуск второго агента).
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class HermesConnectorError(Exception):
    """Базовое исключение Connector."""


class GatewayClient:
    """JSON-RPC клиент для gateway (hermes-gateway-v1 protocol)."""

    def __init__(self, ws, loop):
        self.ws = ws
        self._loop = loop
        self.pending: Dict[int, asyncio.Future] = {}
        self.sequence = 0

    async def _reader(self):
        import websockets
        try:
            async for raw in self.ws:
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if "id" in frame and frame.get("method") in (None, "response"):
                    future = self.pending.get(frame["id"])
                    if future is not None and not future.done():
                        if "error" in frame:
                            future.set_exception(HermesConnectorError(
                                frame["error"].get("message", "request_failed")))
                        else:
                            future.set_result(frame.get("result", {}))
                elif "method" in frame and frame["method"] != "notification":
                    # Event notification
                    pass
        except (asyncio.CancelledError, websockets.exceptions.ConnectionClosed):
            pass

    async def request(self, method: str, *, _timeout: float = 30.0, **params) -> Dict[str, Any]:
        """Отправить JSON-RPC запрос и дождаться ответа по ID."""
        id_ = self.sequence
        self.sequence += 1

        request = {
            "jsonrpc": "2.0",
            "id": id_,
            "method": method,
            "params": params
        }

        future = self._loop.create_future()
        self.pending[id_] = future

        try:
            await self.ws.send(json.dumps(request))
            try:
                response = await asyncio.wait_for(future, timeout=_timeout)
                return response
            except asyncio.TimeoutError:
                del self.pending[id_]
                raise HermesConnectorError(f"Таймаут ожидания ответа для {method}")
        except Exception:
            del self.pending[id_]
            raise

    def close(self):
        if self.ws:
            self.ws.close()


class HermesConnector:
    """Клиент для подключения к существующему gateway через JSON-RPC."""

    GATEWAY_WS_PROTOCOL = "hermes-gateway-v1"
    GATEWAY_WS_TICKET_PREFIX = "hermes-gateway-ticket."

    def __init__(
        self,
        gateway_url: str,
        session_ticket: str,
        gateway_host: str = "127.0.0.1",
        gateway_port: int = 61650,
        timeout: float = 30.0,
    ):
        self.gateway_url = gateway_url
        self.session_ticket = session_ticket
        self.timeout = timeout
        self._ws = None
        self._gate = None
        self._loop = None
        self._session_id: Optional[str] = None
        self._run_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Подключиться к gateway через WebSocket."""
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
            return True
        except Exception as e:
            logger.error("Ошибка подключения к gateway: %s", e)
            return False

    async def create_session(self, cwd: str = None, source: str = "hermes-chatgpt-bridge") -> bool:
        """Создать сессию через session.create."""
        if not self._gate:
            raise HermesConnectorError("Gateway не подключён")

        request_id = str(uuid.uuid4())
        session_create = {
            "request_id": request_id,
            "cwd": cwd or "/Users/konstantin/Тест",
            "source": source,
            "policy": {}
        }

        # Создаём объекты SessionActor и SessionCreate (без импорта из gateway,
        # чтобы избежать зависимости от версии Gateway SDK)
        actor = self._make_session_actor()
        handle = self._make_session_create(request_id, cwd, source, session_create["policy"])

        try:
            result = await self._gate.request(
                "session.create", actor=actor, request=handle)
            self._session_id = result.get("session_id") or result.get("handle", {}).get("session_id")
            return True
        except Exception as e:
            logger.error("Ошибка session.create: %s", e)
            return False

    def _make_session_actor(self):
        """Создать SessionActor (фэйковый объект для тестов)."""
        class SessionActor:
            def __init__(self, **kwargs):
                self.subject = kwargs.get("subject", "hermes-chatgpt-bridge")
                self.profile_id = kwargs.get("profile_id", "/Users/konstantin/.hermes")
                self.capabilities = kwargs.get("capabilities", frozenset())
                self.transport_id = kwargs.get("transport_id", "bridge")
        return SessionActor(
            subject="hermes-chatgpt-bridge",
            profile_id="/Users/konstantin/.hermes",
            capabilities=frozenset(),
            transport_id="bridge"
        )

    def _make_session_create(self, request_id, cwd, source, policy):
        """Создать SessionCreate (фэйковый объект для тестов)."""
        class SessionCreate:
            def __init__(self, **kwargs):
                self.request_id = kwargs.get("request_id", request_id)
                self.cwd = kwargs.get("cwd", cwd or "/Users/konstantin/Тест")
                self.source = kwargs.get("source", source)
                self.policy = kwargs.get("policy", {})
        return SessionCreate(
            request_id=request_id,
            cwd=cwd or "/Users/konstantin/Тест",
            source=source,
            policy=policy
        )

    async def submit_task(self, task: str) -> str:
        """Отправить задачу в сессию через prompt.submit."""
        if not self._gate:
            raise HermesConnectorError("Gateway не подключён")

        request_id = str(uuid.uuid4())

        # Создаём объект Submission (фэйковый объект для тестов)
        submission = self._make_submission(request_id, task)

        try:
            result = await self._gate.request(
                "prompt.submit", request=submission)
            return result.get("admission_id") or result.get("outcome", "")
        except Exception as e:
            logger.error("Ошибка prompt.submit: %s", e)
            return f"[Ошибка: {e}]"

    def _make_submission(self, request_id, task):
        """Создать Submission (фэйковый объект для тестов)."""
        session_id = self._session_id or "unknown_session"
        class Submission:
            def __init__(self, **kwargs):
                self.request_id = kwargs.get("request_id", request_id)
                self.ref = kwargs.get("ref", {"profile_id": "/Users/konstantin/.hermes", "session_id": session_id})
                self.payload = kwargs.get("payload", {"text": task, "toolset": "default"})
                self.intent = kwargs.get("intent", "queue")
        return Submission(
            request_id=request_id,
            ref={"profile_id": "/Users/konstantin/.hermes", "session_id": session_id},
            payload={"text": task},
            intent="queue"
        )

    async def get_events(self, since: str = None) -> list:
        """Получить события сессии через session.events.since."""
        if not self._gate:
            raise HermesConnectorError("Gateway не подключён")

        try:
            result = await self._gate.request(
                "session.events.since",
                ref={"profile_id": "/Users/konstantin/.hermes", "session_id": self._session_id},
                since=since
            )
            return result.get("events", [])
        except Exception as e:
            logger.error("Ошибка events: %s", e)
            return []

    async def close(self):
        if self._ws:
            await self._ws.close()
        if self._gate:
            self._gate.close()
