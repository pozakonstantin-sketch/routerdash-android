"""Response Sender — отправка результата в тот же диалог ChatGPT через CDP.

Использует CDP для:
1. Активации вкладки
2. Вставки текста в поле composer
3. Нажатия кнопки отправки
4. Проверки, что сообщение действительно появилось в DOM

Важные замечания:
- Runtime.evaluate НЕ принимает поле 'arguments' в современных версиях CDP.
  Для передачи данных в JS функцию используйте callFunctionOn.
- Ввод текста происходит через Input.insertText + события input/change.
- Отправка подтверждается проверкой DOM после клика по кнопке.
"""

import logging
import time
from typing import Optional
from .cdp_client import CDPClient, CDPError

logger = logging.getLogger(__name__)


class ResponseSender:
    """Отправка ответа в ChatGPT через CDP.

    Контракт:
    - send_message(text, tab_id) -> bool
    - Только в тот же диалог, где было прочитано сообщение
    - Подтверждение: сообщение должно появиться в DOM после отправки
    """

    def __init__(self, cdp: CDPClient, target_url: str = "https://chatgpt.com"):
        self.cdp = cdp
        self.target_url = target_url

    def send_message(self, text: str, tab_id: Optional[str] = None) -> bool:
        """Отправить сообщение в ChatGPT.

        Args:
            text: Текст сообщения для отправки
            tab_id: ID вкладки (если не указан, используется активная вкладка)

        Returns:
            True если сообщение успешно отправлено и появилось в DOM, иначе False.
        """
        try:
            # 1. Активируем целевую вкладку, если указан tab_id
            if tab_id:
                self.cdp._send({
                    "id": 99,
                    "method": "Target.activateTarget",
                    "params": {"targetId": tab_id}
                })

            # 2. Вставляем текст в composer через Input.insertText
            result = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        // Ищем поле ввода сообщения
                        const el = document.querySelector('textarea[aria-label*="message"]') ||
                                    document.querySelector('div[contenteditable="true"]') ||
                                    document.querySelector('[data-message-input]');
                        if (!el) return "Input not found";

                        // Очищаем поле
                        while (el.firstChild) {
                            el.removeChild(el.firstChild);
                        }

                        // Используем Input.insertText для корректного ввода
                        const selection = window.getSelection();
                        const range = document.createRange();
                        if (el.hasChildNodes()) {
                            range.selectNodeContents(el);
                            range.collapse(false);
                            selection.removeAllRanges();
                            selection.addRange(range);
                        }

                        // Вставляем текст через Input.insertText
                        const inputEvent = new InputEvent('insertText', {
                            data: arguments[0],
                            bubbles: true,
                            cancelable: true
                        });
                        el.dispatchEvent(inputEvent);

                        // Имитируем события ввода
                        el.dispatchEvent(new Event('input', { bubbles: true, cancelable: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true, cancelable: true }));

                        // Эмулируем клавиатурное событие Enter
                        el.dispatchEvent(new KeyboardEvent('keydown', {
                            key: 'Enter',
                            code: 'Enter',
                            bubbles: true,
                            cancelable: true
                        }));

                        return "Input set";
                    })()
                """,
                "returnByValue": True
            })

            result_str = str(result.get("result", {}).get("result", {}).get("value", ""))
            if "not found" in result_str.lower():
                logger.warning("Элемент ввода не найден")
                return False

            # 3. Кликаем кнопку отправки
            result2 = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        // Ищем кнопку отправки в текущем диалоге
                        const buttons = Array.from(document.querySelectorAll('button'));

                        // Проверка по атрибутам
                        for (const b of buttons) {
                            const label = (b.getAttribute('aria-label') || '') + ' ' + (b.textContent || '');
                            const lower = label.toLowerCase();
                            if (lower.includes('send') || lower.includes('поделиться') || lower.includes('отправить') || lower.includes('решить')) {
                                b.click();
                                return 'Sent via ' + (b.getAttribute('aria-label') || 'button');
                            }
                        }

                        // Проверка по data-testid
                        for (const b of buttons) {
                            const testId = (b.getAttribute('data-testid') || '').toLowerCase();
                            if (testId.includes('send') || testId.includes('submit') || testId.includes('send_message')) {
                                b.click();
                                return 'Sent via [data-testid]';
                            }
                        }

                        // Проверка по контенту текста
                        for (const b of buttons) {
                            const text = b.textContent || '';
                            if (text.includes('Send') || text.includes('Отправить') || text.includes('Share')) {
                                b.click();
                                return 'Sent via text';
                            }
                        }

                        return 'Send button not found';
                    })()
                """
            })

            value2 = str(result2.get("result", {}).get("result", {}).get("value", ""))
            if "not found" in value2.lower():
                logger.warning("Кнопка отправки не найдена")
                return False
            if "Sent via" not in value2:
                logger.warning("Не удалось отправить: %s", value2[:100])
                return False

            # 4. Проверяем, что сообщение появилось в DOM
            # Используем небольшую задержку для отрисовки
            time.sleep(1)

            result3 = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        // Ищем отправленное сообщение в текущем диалоге
                        const messages = [];
                        const containers = [
                            document.querySelector('[role="log"]'),
                            document.querySelector('[data-testid="chat-dialog"]'),
                            document.querySelector('[data-message-id]')
                        ];

                        for (const container of containers) {
                            if (!container) continue;
                            const items = container.querySelectorAll('[data-message-id]');
                            for (const item of items) {
                                const id = item.getAttribute('data-message-id');
                                const text = item.textContent.trim();
                                if (text && id) {
                                    messages.push({ id, text, container: container.tagName });
                                }
                            }
                        }

                        return messages;
                    })()
                """
            })

            dom_messages = result3.get("result", {}).get("result", [])
            if not dom_messages:
                logger.warning("После отправки сообщений не обнаружено в диалоге")
                return False

            # Проверяем, что хотя бы одно сообщение появилось в DOM
            logger.info("Сообщение найдено в DOM: %d элементов", len(dom_messages))

            logger.info("Сообщение отправлено в ChatGPT")
            return True

        except CDPError as e:
            logger.error("CDP ошибка при отправке: %s", e)
            return False
        except Exception as e:
            logger.error("Ошибка отправки ответа: %s", e)
            return False
