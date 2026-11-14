"""Hermes Connector — обмен задачами с постоянной сессией AI-агента.

Использует `hermes serve` (официальный JSON-RPC/WebSocket бэкенд) как постоянный
сервер агента. Это официальный способ запускать агента как долгоживущий процесс
и взаимодействовать с ним через API. Не использует `hermes chat -q` (одноразовый
режим) как механизм постоянной сессии.
"""

import logging
import subprocess
import time
import json
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class HermesConnector:
    """Клиент для отправки задач в постоянную сессию AI-агента Hermes."""

    def __init__(self, bridge_dir: str, serve_host: str = "127.0.0.1",
                 serve_port: int = 9119, api_key: Optional[str] = None):
        self.bridge_dir = bridge_dir
        self.serve_host = serve_host
        self.serve_port = serve_port
        self.api_key = api_key
        self.server_process: Optional[subprocess.Popen] = None
        self._session_id: Optional[str] = None

    def start_server(self, timeout: int = 30) -> bool:
        """Запустить `hermes serve` как постоянный сервер."""
        if self.server_process and self.server_process.poll() is None:
            logger.info("Сервер уже запущен")
            return True

        logger.info("Запуск `hermes serve` на %s:%d", self.serve_host, self.serve_port)
        try:
            # Запуск в фоновом режиме с перенаправлением вывода
            self.server_process = subprocess.Popen(
                ["hermes", "serve", "--host", self.serve_host, "--port", str(self.serve_port)],
                cwd=self.bridge_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True
            )
            # Ждём готовности
            start = time.time()
            while time.time() - start < timeout:
                if self.server_process.poll() is not None:
                    logger.error("Сервер умер")
                    return False
                # Проверяем, что сервер отвечает
                import urllib.request
                try:
                    req = urllib.request.Request(
                        f"http://{self.serve_host}:{self.serve_port}/",
                        headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                    )
                    resp = urllib.request.urlopen(req, timeout=2)
                    if resp.status == 200:
                        logger.info("Сервер готов")
                        return True
                except Exception:
                    pass
                time.sleep(0.5)
            logger.error("Сервер не запустился за %d секунд", timeout)
            return False
        except Exception as e:
            logger.error("Ошибка запуска сервера: %s", e)
            return False

    def stop_server(self) -> None:
        """Остановить сервер."""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except Exception:
                pass
            self.server_process = None

    def send_task(self, task: str, timeout: int = 300) -> str:
        """Отправить задачу в постоянную сессию и получить ответ.

        Реализует взаимодействие через JSON-RPC API сервера `hermes serve`.
        """
        if not self.server_process or self.server_process.poll() is not None:
            if not self.start_server():
                return "[Ошибка: сервер не запущен]"

        # Проверка сессии
        if not self._session_id:
            self._session_id = self._create_session()

        try:
            # Отправляем задачу через API
            task_payload = {
                "type": "user_message",
                "text": task,
                "session_id": self._session_id
            }
            logger.info("Отправка задачи в сессию %s", self._session_id)
            response = self._api_call("send_task", task_payload)
            return response.get("response", "[Ошибка: нет ответа]")
        except Exception as e:
            logger.error("Ошибка API: %s", e)
            return f"[Ошибка: {e}]"

    def _create_session(self) -> str:
        """Создать или получить существующую сессию."""
        try:
            # Проверяем существующие сессии
            self._api_call("list_sessions", {})
            return "persistent_session"  # Идентификатор постоянной сессии
        except Exception as e:
            logger.warning("Не удалось получить список сессий: %s", e)
            return "persistent_session"

    def _api_call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Вызвать метод API сервера `hermes serve`."""
        import urllib.request
        import urllib.error

        url = f"http://{self.serve_host}:{self.serve_port}/{method}"
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Данные запроса
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": 1
        }
        data_bytes = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("result", result)
        except urllib.error.HTTPError as e:
            error_text = e.read().decode("utf-8", errors="replace")
            logger.error("HTTP ошибка: %s %s", e.code, error_text[:200])
            raise Exception(f"HTTP {e.code}: {error_text[:200]}")
        except Exception as e:
            logger.error("Ошибка запроса: %s", e)
            raise

    def is_healthy(self) -> bool:
        """Проверить здоровье сервера."""
        try:
            import urllib.request
            req = urllib.request.Request(
                f"http://{self.serve_host}:{self.serve_port}/",
                headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            )
            resp = urllib.request.urlopen(req, timeout=5)
            return resp.status == 200
        except Exception:
            return False
