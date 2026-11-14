# Hermes ↔ ChatGPT Bridge — прототип

Минимальный двусторонний мост между авторизованным диалогом ChatGPT в браузере и сессией Hermes Desktop на этом компьютере.

> **Предварительный аудит:** macOS 27.3 · Hermes Agent v0.23.1 · CDP не запущен (порт 9222 свободен) · В системе установлены Yandex и Safari.

## Быстрый старт / 4 шага

1. **Запустите браузер с удалённой отладкой** (CDP). Например, в терминале:
   ```bash
   open -a Yandex --args --remote-debugging-port=9222 --user-data-dir=/tmp/yandex-cdp-profile
   ```
   (либо Safari: `open -a Safari --args --remote-debugging-port=9222`)
2. **Войдите в ChatGPT** в этой браузербразе.
3. **Создайте копию config.example.yaml → config.yaml** и настройте:
   - `cdp_url: ws://127.0.0.1:9222`
   - `target_url: https://chatgpt.com`
   - `target_dialog_selector`: CSS-селектор активного диалога (необязательно, по умолчанию автоматически)
4. **Запустите мост:**
   ```bash
   cd tools/hermes-chatgpt-bridge
   chmod +x scripts/run_bridge.sh
   ./scripts/run_bridge.sh
   ```

## Архитектура

```
ChatGPT (браузер, CDP)
  ↓ (CDP: табы, DOM-схема, ввод)
CDP Client (Python)
  ↓ (JSON)
Bridge Daemon (Python)
  ↓ (задача)
Hermes Agent (постоянный фоновый сеанс)
  ↓ (ответ)
Bridge Daemon
  ↓ (CDP: ввод, отправка)
ChatGPT (браузер)
```

### Компоненты

| Компонент | Файл | Назначение |
|-----------|------|------------|
| CDP Client | `bridge/cdp_client.py` | Подключение, просмотр вкладок, чтение DOM |
| Tab Monitor | `bridge/tab_monitor.py` | Обнаружение вкладки chatgpt.com |
| Message Reader | `bridge/message_reader.py` | Чтение новых сообщений с дедупликацией |
| Task Identifier | `bridge/task_identifier.py` | Распознавание задач для Hermes |
| Hermes Connector | `bridge/hermes_connector.py` | Обмен с сессией AI-агента |
| Response Sender | `bridge/response_sender.py` | Отправка результата в тот же диалог |
| State Manager | `bridge/state_manager.py` | SQLite-сохранение состояния переписки |
| Error Handler | `bridge/error_handler.py` | Обработка ошибок, таймаутов, переподключения |

### Сохранение состояния

- База: `logs/bridge_state.db` (SQLite)
- Журнал handshake: `logs/handshake.log`
- Все секреты просто **не логируются**.

## Безопасность

- `hermes chat -q` в цикле **не используется**; мост запускает постоянный фоновый сеанс.
- CDP **только локально** (ws://127.0.0.1:9222). Порт 9222 **не публикуется** в сеть.
- Запрещён `--disable-web-security`.
- Не читаются cookies, localStorage, пароли, токены, session DB, профили браузера.
- Не устанавливаются расширения и не отключаются защиты браузера.
- В отчётах/логах **нет секретов и персональных данных**.
- При потере браузера мост останавливается и ждёт ручное переподключение.

## Тесты

```bash
cd tools/hermes-chatgpt-bridge
python -m pytest tests/ -v
```

## Совет по воспроизводимости

Если стоит Yandex и Safari — в настройках браузера нужно явно разрешить «Удалённую отладку» и сделать это сейчас:
- Yandex: `Настройки → Конфиденциальность и безопасность → Удалённая отладка`
- Safari: `С nocturnalmenus → Разработка (Develop)`, затем `Активная страница → Включить удалённую отладку`

## Лимитации

- **Тест B «HERMES CONNECTED»** пока **BLOCKED** из-за отсутствия CDP.
- Чтобы перейти в тестовую фазу, пользователь должен запустить браузер с CDP и войти в ChatGPT в нём.
