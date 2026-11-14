"""Response Sender — отправка результата в тот же диалог ChatGPT."""

import logging
from typing import Optional
from .cdp_client import CDPClient, CDPError

logger = logging.getLogger(__name__)


class ResponseSender:
    """Отправка ответа в ChatGPT через CDP."""

    def __init__(self, cdp: CDPClient, target_url: str = "https://chatgpt.com"):
        self.cdp = cdp
        self.target_url = target_url

    def send_message(self, text: str, tab_id: Optional[str] = None) -> bool:
        """Отправить сообщение в ChatGPT."""
        try:
            # Если таймлайт указан, активируем его
            if tab_id:
                self.cdp._send({"id": 99, "method": "Target.activateTarget", "params": {"targetId": tab_id}})

            # Вставляем текст
            result = self.cdp._send_sync("Runtime.evaluate", {
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
            result2 = self.cdp._send_sync("Runtime.evaluate", {
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

            logger.info("Сообщение отправлено в ChatGPT")
            return True
        except Exception as e:
            logger.error("Ошибка отправки ответа: %s", e)
            return False
