"""Bridge Daemon — главный демон моста Hermes ↔ ChatGPT.

Основные требования:
- Получить безопасные параметры подключения к существующему Gateway
- connect() → create_session() → submit_task() → get_task_result()
- Проверить фактическое завершение
- Передать только готовый результат в ResponseSender

- dry_run=true: ни одного обращения к Hermes, ни одной отправки в ChatGPT
- Сохранять контекст переписки и продолжать после перезапуска
"""

import argparse
import json
import logging
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from .cdp_client import CDPClient, CDPError
from .tab_monitor import TabMonitor
from .message_reader import MessageReader
from .task_identifier import TaskIdentifier
from .hermes_connector import HermesConnector, HermesConnectorError
from .response_sender import ResponseSender
from .state_manager import StateManager, STATE_NEW, STATE_PROCESSING, STATE_SUBMITTED, STATE_RESPONSE_READY, STATE_SENT, STATE_FAILED

logger = logging.getLogger(__name__)


class BridgeDaemon:
    """Основной демон моста."""

    def __init__(self, config: dict):
        self.config = config
        self.running = False
        self.cdp: Optional[CDPClient] = None
        self.tab_monitor: Optional[TabMonitor] = None
        self.message_reader: Optional[MessageReader] = None
        self.task_identifier: Optional[TaskIdentifier] = None
        self.hermes_connector: Optional[HermesConnector] = None
        self.response_sender: Optional[ResponseSender] = None
        self.state: Optional[StateManager] = None
        self.dry_run: bool = config.get("dry_run", False)

    def setup_components(self) -> bool:
        """Инициализировать компоненты моста."""
        try:
            self.state = StateManager(self.config.get("state_file", "logs/bridge_state.db"))
            self.cdp = CDPClient(self.config.get("cdp_url", "ws://127.0.0.1:9222"))
            self.tab_monitor = TabMonitor(
                self.cdp,
                self.config.get("target_url", "https://chatgpt.com"),
                self.config.get("target_dialog_selector")
            )
            self.message_reader = MessageReader(self.cdp, self.state)
            self.task_identifier = TaskIdentifier(self.config)
            self.hermes_connector = HermesConnector(
                gateway_url=self.config.get("gateway_url", "ws://127.0.0.1:61650/api/ws"),
                session_ticket=self.config.get("session_ticket", "")
            )
            self.response_sender = ResponseSender(
                self.cdp,
                self.config.get("target_url", "https://chatgpt.com")
            )
            return True
        except Exception as e:
            logger.error("Ошибка инициализации компонентов: %s", e)
            return False

    def start(self) -> bool:
        """Запустить мост."""
        self.running = True
        logger.info("=== HERMES ChatGPT BRIDGE запущен (dry_run=%s) ===",
                    self.dry_run)

        # 1. Быстрая проверка dry_run до подключения к каким-либо внешним ресурсам
        if self.dry_run:
            logger.info("🔒 DRY-RUN OFFLINE: блокировка всех внешних операций")
            logger.info("   - Не подключение к CDP")
            logger.info("   - Не поиск вкладок ChatGPT")
            logger.info("   - Не чтение сообщений")
            logger.info("   - Не отправка в Hermes")
            logger.info("   - Не отправка в ChatGPT")
            logger.info("   - Только анализ кода и тестирование")
            self.state.append_to_log("🔒 DRY-RUN OFFLINE: блокировка всех внешних операций", "INFO")
            return True

        logger.info("Таймауты: connect=%ss read=%ss task=%ss",
                    self.config.get("timeout_connect", "?"),
                    self.config.get("timeout_read", "?"),
                    self.config.get("timeout_task", "?"))

        # Регистрация обработчиков прерывания
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # 1. Подключение к CDP
        logger.info("Попытка подключения к CDP: %s", self.config.get("cdp_url"))
        try:
            self.cdp.connect()
        except CDPError as e:
            logger.error("Не удалось подключиться к CDP: %s", e)
            self.state.append_to_log(f"BLOCKED: CDP не доступен – {e}", "ERROR")
            return False

        # 2. Поиск вкладки ChatGPT
        logger.info("Ожидание вкладки ChatGPT...")
        if not self.tab_monitor.wait_for_chatgpt(timeout=self.config.get("timeout_connect", 60)):
            logger.error("Вкладка ChatGPT не найдена")
            self.cdp.disconnect()
            self.state.append_to_log("BLOCKED: ChatGPT вкладка не найдена", "ERROR")
            return False

        logger.info("✅ Вкладка ChatGPT найдена")
        self.state.append_to_log("✅ ChatGPT вкладка найдена", "INFO")

        # 3. Главный цикл мониторинга
        self._main_loop()
        return True

    def _main_loop(self) -> None:
        """Главный цикл мониторинга и обработки."""
        while self.running:
            try:
                # Проверка подключения
                if not self.cdp.is_connected():
                    logger.warning("CDP отключен, переподключение...")
                    try:
                        self.cdp.connect()
                    except CDPError as e:
                        logger.error("Переподключение не удалось: %s", e)
                        self.state.append_to_log(f"CDP недоступен: {e}", "ERROR")
                        time.sleep(self.config.get("timeout_restart", 60))
                        continue

                # Поиск вкладки
                tab_id = self.tab_monitor.find_chatgpt_tab()
                if not tab_id:
                    logger.warning("ChatGPT вкладка не найдена, ожидание...")
                    time.sleep(5)
                    continue

                # Чтение новых сообщений
                new_messages = self.message_reader.read_new_messages()
                logger.info("Новых сообщений: %d", len(new_messages))

                for msg in new_messages:
                    text = msg.get("text", "").strip()
                    if not text:
                        continue

                    # Игнорируем пустые сообщения
                    if len(text) < 2:
                        continue

                    # Проверка на адресацию к Hermes
                    if not self.task_identifier.is_task(text):
                        logger.info("Сообщение не адресовано Hermes, пропуск")
                        continue

                    # Извлечение текста задачи
                    task_text = self.task_identifier.extract_task_text(text)

                    # Проверка на пустую задачу
                    if not task_text:
                        logger.warning("Пустая задача, пропуск")
                        continue

                    # Создание задачи в StateManager
                    task = self.state.create_task(msg.get("id", ""), task_text)
                    logger.info("📥 Задача создана: task_id=%s", task)

                    # 1. Отправка в Hermes (если не dry_run)
                    agent_response = None
                    if self.dry_run:
                        logger.info("🔒 DRY-RUN: не выполняем задачу")
                        self.state.mark_task_failed(task, "DRY-RUN режим")
                        self.state.append_to_log("🔒 DRY-RUN: задача не выполнена", "INFO")
                        continue

                    # 2. Полная последовательность: connect → create_session → submit_task → get_task_result
                    try:
                        # Подключаемся к Gateway
                        self.hermes_connector.connect()
                        logger.info("✅ Подключение к Gateway")

                        # Создаём/восстанавливаем сессию
                        self.hermes_connector.create_session()
                        logger.info("✅ Сессия создана")

                        # Отправляем задачу
                        self.hermes_connector.submit_task(task_text)
                        logger.info("✅ Задача отправлена")

                        # Дожидаемся результата
                        result = self.hermes_connector.get_task_result(task, timeout=self.config.get("timeout_task", 60))
                        if result:
                            logger.info("✅ Результат получен от Gateway")
                            agent_response = result
                            self.state.mark_task_response_ready(task, result)
                            self.state.append_to_log(f"📤 Результат от Gateway: {str(result)[:100]}...", "INFO")
                        else:
                            logger.error("❌ Не удалось получить результат от Gateway")
                            self.state.mark_task_failed(task, "Не удалось получить результат")
                            self.state.append_to_log("❌ Ошибка получения результата от Gateway", "ERROR")

                    except HermesConnectorError as e:
                        logger.error("❌ Ошибка HermesConnector: %s", e)
                        self.state.mark_task_failed(task, str(e))
                        self.state.append_to_log(f"❌ Ошибка Gateway: {e}", "ERROR")
                    except Exception as e:
                        logger.error("❌ Непредвиденная ошибка: %s", e)
                        self.state.mark_task_failed(task, str(e))
                        self.state.append_to_log(f"❌ Непредвиденная ошибка: {e}", "ERROR")

                    # 3. Отправка в ChatGPT (если не dry_run)
                    if not self.dry_run:
                        if agent_response:
                            # Отправляем готовый результат
                            if self.response_sender.send_message(agent_response, tab_id):
                                logger.info("✅ Ответ отправлен в ChatGPT")
                                self.state.mark_task_sent(task)
                                self.state.append_to_log("✅ Ответ отправлен в ChatGPT", "INFO")
                            else:
                                logger.error("❌ Не удалось отправить ответ в ChatGPT")
                                self.state.mark_task_failed(task, "Ошибка отправки в ChatGPT")
                                self.state.append_to_log("❌ Отправка ответа в ChatGPT не удалась", "ERROR")
                        else:
                            logger.warning("⚠️  Нет результата для отправки")
                    else:
                        logger.info("🔒 DRY-RUN: ответ не отправлен в ChatGPT")
                        self.state.append_to_log("🔒 DRY-RUN: ответ не отправлен в ChatGPT", "INFO")

                time.sleep(5)

            except Exception as e:
                logger.error("Ошибка в главном цикле: %s", e, exc_info=True)
                self.state.append_to_log(f"Ошибка: {e}", "ERROR")
                time.sleep(self.config.get("timeout_restart", 60))

    def _signal_handler(self, signum, frame) -> None:
        """Обработчик сигналов."""
        logger.info("Получен сигнал %s, остановка...", signum)
        self.running = False

    def stop(self) -> None:
        """Остановить мост."""
        logger.info("Остановка моста...")
        self.running = False
        if self.cdp:
            self.cdp.disconnect()


def main():
    """Точка входа."""
    parser = argparse.ArgumentParser(description="Hermes ↔ ChatGPT Bridge")
    parser.add_argument("--config", default="config.yaml",
                        help="Путь к конфигурационному файлу")
    args = parser.parse_args()

    try:
        import yaml
    except ImportError:
        logger.error("PyYAML не установлен. Установите: pip install pyyaml")
        sys.exit(1)

    config = {"cdp_url": "ws://127.0.0.1:9222"}
    if args.config and Path(args.config).exists():
        try:
            config = BridgeDaemon(None).load_config(args.config)
        except Exception as e:
            logger.error("Ошибка чтения конфигурации: %s", e)
            sys.exit(1)

    daemon = BridgeDaemon(config)
    daemon.setup_logging()
    daemon.setup_components()

    if not daemon.start():
        sys.exit(1)


if __name__ == "__main__":
    main()
