"""Tab Monitor — обнаружение вкладки chatgpt.com и текущего диалога."""

import logging
import time
from typing import Optional, List, Dict, Any

from .cdp_client import CDPClient, CDPError

logger = logging.getLogger(__name__)


class TabMonitor:
    """Мониторинг вкладок и диалогов в браузере."""

    def __init__(self, cdp: CDPClient, target_url: str = "https://chatgpt.com",
                 dialog_selector: str = None):
        self.cdp = cdp
        self.target_url = target_url
        self.dialog_selector = dialog_selector
        self._tab_cache: Optional[str] = None

    def find_chatgpt_tab(self) -> Optional[str]:
        """Найти таймлайт ChatGPT."""
        targets = self.cdp.get_targets()
        for t in targets:
            url = t.get("url", "")
            title = t.get("title", "")
            if "chatgpt.com" in url or "chatgpt" in title.lower():
                logger.info("Найдена вкладка ChatGPT: %s", url)
                self._tab_cache = t.get("targetId")
                return t.get("targetId")
        return None

    def is_chatgpt_tab(self, tab_id: str) -> bool:
        """Проверить, является ли таймлайт ChatGPT."""
        targets = self.cdp.get_targets()
        for t in targets:
            if t.get("targetId") == tab_id:
                url = t.get("url", "")
                return "chatgpt.com" in url
        return False

    def get_current_dialog(self) -> Optional[Dict[str, Any]]:
        """Получить текущий диалог (активную вкладку)."""
        targets = self.cdp.get_targets()
        for t in targets:
            if t.get("url", "").startswith(self.target_url):
                return {
                    "target_id": t.get("targetId"),
                    "url": t.get("url"),
                    "title": t.get("title", "")
                }
        return None

    def wait_for_chatgpt(self, timeout: int = 60) -> bool:
        """Дождаться вкладки ChatGPT."""
        start = time.time()
        while time.time() - start < timeout:
            tab = self.find_chatgpt_tab()
            if tab:
                return True
            time.sleep(1)
        logger.warning("Вкладка ChatGPT не найдена за %.1f с", time.time() - start)
        return False

    def get_all_tabs(self) -> List[Dict[str, Any]]:
        """Все вкладки."""
        return self.cdp.get_targets()

    def is_connected(self) -> bool:
        return self.cdp.is_connected()
