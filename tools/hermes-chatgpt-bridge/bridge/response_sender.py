"""Response Sender — отправка результата в тот же диалог ChatGPT.

Использует CDP для:
1. Активации вкладки
2. Вставки текста в поле composer
3. Имитации событий ввода
4. Нажатия кнопки отправки
"""

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

            # Вставляем текст через Input.insertText (корректный CDP-команда)
            result = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        // Ищем поле ввода сообщения
                        const el = document.querySelector('textarea[aria-label*="message"]') ||
                                    document.querySelector('input[aria-label*="message"]') ||
                                    document.querySelector('div[contenteditable="true"]');
                        if (!el) return "Input not found";
                        el.focus();
                        // Очищаем поле
                        while (el.firstChild) {
                            el.removeChild(el.firstChild);
                        }
                        // Вставляем текст
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        range.collapse(false);
                        const sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(range);
                        // Вставляем текст
                        el.textContent = arguments[0];
                        // Имитируем события ввода
                        el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));
                        // Эмулируем клавиатурное событие
                        el.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
                        return "Input set";
                    })()
                """,
                "arguments": [text],
                "returnByValue": True
            })
            result_str = str(result.get("result", {}).get("result", {}).get("value", ""))
            if "not found" in result_str:
                logger.warning("Элемент ввода не найден")
                return False
            if "Input set" not in result_str:
                logger.warning("Не удалось установить ввод: %s", result_str[:100])

            # Кликаем кнопку отправки
            result2 = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        const btns = Array.from(document.querySelectorAll('button'));
                        for (const b of btns) {
                            const label = b.getAttribute('aria-label') || '';
                            const id = b.id || '';
                            const classes = b.className || '';
                            const text = b.textContent || '';
                            const lower = (label + ' ' + text).toLowerCase();
                            if (lower.includes('send') || lower.includes('поделиться') || lower.includes('отправить')) {
                                b.click();
                                return 'Sent via ' + (label || 'button');
                            }
                        }
                        // Проверяем на кнопку с data-testid
                        const testBtns = Array.from(document.querySelectorAll('[data-testid]'));
                        for (const b of testBtns) {
                            const testId = (b.getAttribute('data-testid') || '').toLowerCase();
                            if (testId.includes('send') || testId.includes('submit') || testId.includes('send_message')) {
                                b.click();
                                return 'Sent via [data-testid]';
                            }
                        }
                        return 'Send button not found';
                    })()
                """
            })
            value2 = str(result2.get("result", {}).get("result", {}).get("value", ""))
            if "not found" in value2:
                logger.warning("Кнопка отправки не найдена")
                return False
            if "Sent via" not in value2:
                logger.warning("Не удалось отправить: %s", value2[:100])

            logger.info("Сообщение отправлено в ChatGPT")
            return True
        except Exception as e:
            logger.error("Ошибка отправки ответа: %s", e)
            return False
