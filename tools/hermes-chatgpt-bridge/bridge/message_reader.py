"""Message Reader — чтение новых сообщений с дедупликацией."""

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
        self._last_scroll: Optional[str] = None

    def read_new_messages(self, since_message_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Прочитать новые сообщения, исключая уже обработанные."""
        messages = self.cdp.get_new_messages()
        if not messages:
            return []

        unique = []
        for m in messages:
            msg_id = m.get("id")
            if not msg_id:
                continue
            if self.state.is_processed(msg_id):
                continue
            unique.append(m)

        for m in unique:
            self.state.mark_processed(m["id"], "chatgpt", "https://chatgpt.com")

        return unique

    def get_all_messages(self) -> List[Dict[str, Any]]:
        """Все сообщения (для диагностики)."""
        return self.cdp.get_new_messages()
