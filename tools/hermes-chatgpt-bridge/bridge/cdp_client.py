"""CDP Client — подключение к браузеру по Chrome DevTools Protocol."""

import json
import logging
import time
import websocket
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class CDPError(Exception):
    """Базовое исключение CDP."""
    pass


class CDPClient:
    """Клиент для управления браузером через CDP (Chrome DevTools Protocol)."""

    def __init__(self, cdp_url: str = "ws://127.0.0.1:9222"):
        self.cdp_url = cdp_url
        self.ws: Optional[websocket.WebSocket] = None
        self.session_id: Optional[str] = None

    def connect(self) -> bool:
        """Подключиться к CDP-серверу."""
        try:
            self.ws = websocket.create_connection(self.cdp_url, timeout=10)
            self._send({"id": 1, "method": "Target.getTargets"})
            response = self._recv()
            if response is None:
                raise CDPError("No response from CDP server")
            targets = response.get("result", [])
            if not targets:
                raise CDPError("No browser targets found")
            self.session_id = targets[0].get("targetId")
            logger.info("CDP подключён. Сессия: %s", self.session_id)
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

    def get_targets(self) -> List[Dict[str, Any]]:
        """Получить список целей (вкладок)."""
        self._send({"id": 2, "method": "Target.getTargets"})
        response = self._recv()
        if response and "result" in response:
            return response["result"]
        return []

    def get_tab_id_by_url(self, url: str, title_substring: str = None) -> Optional[str]:
        """Найти таймлайт по URL или подстроке в заголовке."""
        targets = self.get_targets()
        for t in targets:
            target_url = t.get("url", "")
            title = t.get("title", "")
            if url in target_url or (title_substring and title_substring in title):
                return t.get("targetId")
        return None

    def _send_sync(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Отправить синхронный CDP-вызов и получить ответ."""
        if not self.session_id:
            raise CDPError("CDP не подключен")
        msg_id = int(time.time() * 1000) % 100000
        self._send({"id": msg_id, "method": method, "params": params or {}})
        response = self._recv()
        if response is None:
            raise CDPError("Таймаут ожидания ответа от CDP")
        if "error" in response:
            raise CDPError(f"CDP error: {response['error']}")
        return response

    def list_tabs(self) -> List[Dict[str, Any]]:
        """Список вкладок (через Target.getTargets)."""
        return self.get_targets()

    def new_tab(self, url: str) -> bool:
        """Открыть новую вкладку или перейти в существующую."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "")
        targets = self.get_targets()
        for t in targets:
            if domain in t.get("url", ""):
                self._send({"id": 99, "method": "Target.activateTarget", "params": {"targetId": t["targetId"]}})
                return True
        # Если вкладка не найдена, создаём новую
        try:
            self._send({"id": 100, "method": "Target.createTarget", "params": {"url": url}})
            response = self._recv()
            if response and "result" in response:
                return True
        except Exception as e:
            logger.warning("Новая вкладка не создана: %s", e)
        return False

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

    def send_message(self, text: str) -> bool:
        """Отправить сообщение в ChatGPT через CDP."""
        try:
            # Фокус на поле ввода
            result = self._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        const el = document.querySelector('textarea[aria-label*="message"]') ||
                                    document.querySelector('input[aria-label*="message"]') ||
                                    document.querySelector('div[contenteditable="true"]');
                        if (!el) return "Input not found";
                        el.focus();
                        el.textContent = "";
                        el.textContent = arguments[0];
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        return "Input set";
                    })()
                """,
                "arguments": [text],
                "returnByValue": True
            })
            if "not found" in result.get("result", {}).get("result", {}).get("value", ""):
                logger.warning("Элемент ввода не найден")
                return False
            # Кликаем кнопку отправки
            result2 = self._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        for (const b of btns) {
                            const label = b.getAttribute('aria-label') || '';
                            if (label.toLowerCase().includes('send') || label.toLowerCase().includes('поделиться')) {
                                b.click();
                                return 'Sent via ' + label;
                            }
                        }
                        return 'Send button not found';
                    })()
                """
            })
            value2 = result2.get("result", {}).get("result", {}).get("value", "")
            if "not found" in value2:
                logger.warning("Кнопка отправки не найдена")
                return False
            return True
        except Exception as e:
            logger.error("Ошибка отправки: %s", e)
            return False

    def get_new_messages(self, since_message_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Прочитать новые сообщения из чата."""
        self.scroll_to_bottom()
        time.sleep(1)
        messages = []
        try:
            result = self._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        const messages = [];
                        const el = document.querySelector('div[role="log"], [data-testid="chat-dialog"]');
                        if (!el) return messages;
                        const items = el.querySelectorAll('[data-message-id]');
                        for (const item of items) {
                            const id = item.getAttribute('data-message-id');
                            const text = item.textContent.trim();
                            if (text && id) {
                                messages.push({ id, text });
                            }
                        }
                        return messages;
                    })()
                """
            })
            if result and "result" in result:
                raw = result["result"].get("result", [])
                return raw if isinstance(raw, list) else []
        except Exception as e:
            logger.warning("Ошибка чтения сообщений: %s", e)
        return messages

    def is_connected(self) -> bool:
        """Проверить подключение."""
        return self.ws is not None and self.ws.connected
