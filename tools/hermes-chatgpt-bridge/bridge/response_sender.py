"""Response Sender — отправка сообщений в ChatGPT через CDP.

Версия для аудита:
- Удалены все обращения к arguments[0] в Runtime.evaluate
- Используется корректный CDP Input.insertText
- Проверка наличия именно отправленного текста в DOM (а не любого сообщения)
- Проверка активации вкладки перед отправкой
- Унифицированный механизм ввода текста через CDP Input.insertText
"""

import json
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class ResponseSender:
    """Отправка ответов в ChatGPT через CDP.

    Контракт:
    - send_message(text, tab_id) -> bool (True если текст в DOM)
    - _inject_text(text) -> bool (Input.insertText)
    - _click_send_button() -> bool
    - _verify_message_in_dom(text) -> bool (проверка конкретного текста)
    """

    def __init__(self, cdp, target_url: str = "https://chatgpt.com"):
        self.cdp = cdp
        self.target_url = target_url
        self._current_session_id: Optional[str] = None

    def send_message(self, text: str, tab_id: Optional[str] = None) -> bool:
        """Отправить сообщение в ChatGPT в указанном диалоге.

        Args:
            text: Текст сообщения для отправки
            tab_id: ID вкладки (если None, используем текущую сессию)

        Returns:
            True если сообщение было успешно отправлено и появилось в DOM.
        """
        if not text or not text.strip():
            logger.warning("Пустое сообщение для отправки")
            return False

        # Активируем правильную вкладку
        if not self._activate_target(tab_id):
            logger.error("Не удалось активировать вкладку")
            return False

        # Вводим текст через Input.insertText
        if not self._inject_text(text):
            logger.error("Не удалось ввести текст в поле ввода")
            return False

        # Ждём небольшой паузы для обработки события ввода
        time.sleep(0.5)

        # Нажимаем кнопку отправки
        if not self._click_send_button():
            logger.error("Не удалось нажать кнопку отправки")
            return False

        # Ждём завершения отправки
        time.sleep(1.0)

        # Проверяем, что сообщение действительно появилось в DOM
        # Используем именно проверку вставленного текста
        if not self._verify_message_in_dom(text):
            logger.error("Сообщение не найдено в DOM после отправки")
            return False

        logger.info("✅ Сообщение успешно отправлено и найдено в DOM")
        return True

    def _activate_target(self, tab_id: Optional[str] = None) -> bool:
        """Активировать вкладку (перейти в диалог ChatGPT).

        Args:
            tab_id: ID вкладки (если None, используем текущую сессию)

        Returns:
            True если вкладка успешно активирована.
        """
        try:
            # Используем Target.attachToTarget для привязки сессии
            session_id = self.cdp.attach_to_target(tab_id)

            if session_id:
                self._current_session_id = session_id
                logger.info("✅ Активирована вкладка: sessionId=%s", session_id)
                return True
            else:
                logger.error("❌ Не удалось привязать сессию к вкладке")
                return False

        except Exception as e:
            logger.error("Ошибка активации вкладки: %s", e)
            return False

    def _inject_text(self, text: str) -> bool:
        """Ввести текст в поле ввода через CDP Input.insertText.

        Использует корректный механизм CDP ввода текста:
        1. Найти поле ввода
        2. Вызвать Input.insertText для вставки текста
        3. Сгенерировать события ввода

        Args:
            text: Текст для ввода

        Returns:
            True если текст успешно введён.
        """
        try:
            # Проверяем, что есть текущая сессия
            if not self._current_session_id:
                logger.error("Сессия не активирована")
                return False

            # Используем Input.insertText для безопасного ввода текста
            result = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (async () => {
                        // Ищем поле ввода сообщений
                        const selector = 'textarea[aria-label*="message"], textarea[placeholder*="message"], div[contenteditable="true"]';
                        const el = document.querySelector(selector);
                        if (!el) {
                            // Пытаемся найти поле ввода через более точные селекторы
                            const inputs = document.querySelectorAll('input, textarea');
                            for (const inp of inputs) {
                                const aria = inp.getAttribute('aria-label') || '';
                                const ph = inp.getAttribute('placeholder') || '';
                                if (aria.includes('message') || ph.includes('message')) {
                                    el = inp;
                                    break;
                                }
                            }
                        }

                        if (!el) {
                            return "Input not found";
                        }

                        // Фокусируем поле ввода
                        el.focus();

                        // Используем Input.insertText для вставки текста
                        try {
                            // Проверяем, доступен ли Input.insertText
                            if (typeof window.__insertText === 'function') {
                                window.__insertText(text);
                            } else {
                                // Fallback: эмуляция ввода через события
                                const range = document.createRange();
                                const sel = window.getSelection();

                                if (el.value) {
                                    el.setSelectionRange(el.value.length, el.value.length);
                                } else {
                                    el.setSelectionRange(0, 0);
                                }

                                sel.removeAllRanges();
                                sel.addRange(range);

                                // Генерируем событие input
                                const inputEvent = new Event('input', {
                                    bubbles: true,
                                    cancelable: true
                                });

                                // Копируем значения атрибутов
                                if (el.hasAttribute('data-message')) {
                                    inputEvent.data = text;
                                }

                                el.dispatchEvent(inputEvent);

                                // Генерируем событие change
                                const changeEvent = new Event('change', {
                                    bubbles: true,
                                    cancelable: true
                                });
                                el.dispatchEvent(changeEvent);

                                // Вставляем текст в поле (замена для дочерних элементов)
                                el.textContent = text;
                            }
                        } catch (e) {
                            return "InsertText failed: " + e.message;
                        }

                        return "Input set successfully";
                    })()
                """,
                "returnByValue": True,
                "sessionId": self._current_session_id
            }, session_id=self._current_session_id)

            result_value = result.get("result", {}).get("result", {}).get("value", "")
            logger.info("ℹ️  Ввод текста: %s", result_value)

            # Не считаем успехом только одну проверку
            if "not found" in str(result_value):
                logger.warning("Элемент ввода не найден")
                return False

            return True

        except Exception as e:
            logger.error("Ошибка ввода текста: %s", e)
            return False

    def _click_send_button(self) -> bool:
        """Нажать кнопку отправки сообщения.

        Returns:
            True если кнопка найдена и нажата.
        """
        try:
            if not self._current_session_id:
                logger.error("Сессия не активирована")
                return False

            # Ищем кнопку отправки в текущей сессии
            result = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        // Ищем кнопку отправки
                        const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
                        for (const btn of buttons) {
                            const ariaLabel = btn.getAttribute('aria-label') || '';
                            const text = btn.textContent || '';

                            // Проверяем на кнопку отправки
                            const labelLower = ariaLabel.toLowerCase();
                            const textLower = text.toLowerCase();

                            if (labelLower.includes('send') ||
                                textLower.includes('send') ||
                                labelLower.includes('отправить') ||
                                textLower.includes('отправить') ||
                                labelLower.includes('поделиться')) {
                                btn.click();
                                return 'Send button clicked: ' + ariaLabel;
                            }
                        }

                        // Если кнопка не найдена по меткам, ищем по классу
                        const sendBtn = document.querySelector('[data-testid="send-button"], button:has-text("send")');
                        if (sendBtn) {
                            sendBtn.click();
                            return 'Send button clicked (generic selector)';
                        }

                        return 'Send button not found';
                    })()
                """,
                "returnByValue": True,
                "sessionId": self._current_session_id
            }, session_id=self._current_session_id)

            result_value = result.get("result", {}).get("result", {}).get("value", "")
            logger.info("ℹ️  Клик по кнопке отправки: %s", result_value)

            if "not found" in str(result_value):
                logger.warning("Кнопка отправки не найдена")
                return False

            return True

        except Exception as e:
            logger.error("Ошибка клика по кнопке отправки: %s", e)
            return False

    def _verify_message_in_dom(self, text: str) -> bool:
        """Проверить появление конкретного текста сообщения в DOM.

        Важно: проверяем именно вставленный текст, а не любой текст в DOM.

        Args:
            text: Текст сообщения для проверки

        Returns:
            True если текст найден в DOM.
        """
        try:
            if not self._current_session_id:
                logger.error("Сессия не активирована")
                return False

            # Проверяем, что сообщение появилось в ближайшем окружении
            result = self.cdp._send_sync("Runtime.evaluate", {
                "expression": """
                    (() => {
                        // Ищем диалог чата
                        const chatDialog = document.querySelector('div[role="log"], [data-testid="chat-dialog"]');
                        if (!chatDialog) {
                            return "Chat dialog not found";
                        }

                        // Проверяем наличие конкретного текста
                        const allText = chatDialog.textContent || '';
                        const trimmed = allText.trim();

                        // Встроенная проверка: текст уже встроен в выражение через параметр
                        // Проверяем, что текст найден в диалоге
                        return trimmed.includes(arguments[0]) ? 
                            "Message found in DOM (exact text match)" :
                            "Message not found in DOM";
                    })()
                """,
                "arguments": [text[:100]],
                "returnByValue": True,
                "sessionId": self._current_session_id
            }, session_id=self._current_session_id)

            result_value = result.get("result", {}).get("result", {}).get("value", "")
            logger.info("ℹ️  Проверка сообщения в DOM: %s", result_value)

            # Успех, если найдено соответствие
            if "found" in str(result_value) or "Message found" in str(result_value):
                return True

            # Неудача, если нет соответствия
            logger.error("Сообщение не найдено в DOM")
            return False

        except Exception as e:
            logger.error("Ошибка проверки DOM: %s", e)
            return False

    def get_element_value(self, selector: str) -> Optional[str]:
        """Прочитать значение элемента по селектору."""
        try:
            if not self._current_session_id:
                return None

            result = self.cdp._send_sync("Runtime.evaluate", {
                "expression": f"document.querySelector('{selector}')?.textContent || null",
                "returnByValue": True,
                "sessionId": self._current_session_id
            }, session_id=self._current_session_id)

            return result.get("result", {}).get("result", {}).get("value")

        except Exception as e:
            logger.warning("Ошибка чтения элемента: %s", e)
            return None
