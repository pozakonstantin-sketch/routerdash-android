"""Message Reader — чтение новых сообщений с дедупликацией.

Читает сообщения ТОЛЬКО из текущего диалога ChatGPT, а не из всего DOM.
"""

import logging
import time
from typing import List, Dict, Any, Optional

from .state_manager import StateManager
from .cdp_client import CDPClient, CDPError

logger = logging.getLogger(__name__)


class MessageReader:
    """Чтение сообщений из ChatGPT с дедупликацией."""

    def __init__(self, cdp: CDPClient, state: StateManager):
        self.cdp = cdp
        self.state = state
        self._dialog_root: Optional[str] = None

    def _find_dialog_root(self) -> Optional[str]:
        """Найти корневой элемент диалога."""
        if self._dialog_root:
            return self._dialog_root

        # Проверяем активную вкладку
        tabs = self.cdp.get_targets()
        for tab in tabs:
            url = tab.get("url", "")
            title = tab.get("title", "")
            if "chatgpt.com" in url or "chatgpt" in title.lower():
                self._dialog_root = url
                return url

        return None

    def read_new_messages(self, since_message_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Прочитать новые сообщения из текущего диалога, исключая уже обработанные."""
        # Проверяем, что это ChatGPT-диалог
        if not self._find_dialog_root():
            logger.warning("Не найден ChatGPT-диалог")
            return []

        messages = []
        try:
            # Читаем сообщения из диалога
            result = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        const messages = [];
                        // Ищем диалог через role="log" или data-testid="chat-dialog"
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
                if isinstance(raw, list):
                    messages = raw

        except Exception as e:
            logger.warning("Ошибка чтения сообщений: %s", e)

        # Фильтруем уже обработанные
        unique = []
        for m in messages:
            msg_id = m.get("id")
            if not msg_id:
                continue
            if self.state.is_processed(msg_id):
                continue
            unique.append(m)

        # Маркируем как обработанные
        for m in unique:
            self.state.mark_processed(m["id"], "chatgpt", "https://chatgpt.com")

        return unique

    def get_dialog_messages(self) -> List[Dict[str, Any]]:
        """Все сообщения текущего диалога (для диагностики)."""
        return self.read_new_messages()
