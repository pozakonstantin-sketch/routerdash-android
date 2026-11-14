# HERMES-GITHUB-WORKER

Фоновый агент приёма задач для Hermes Desktop, интегрирующий GitHub Issues как очередь заданий.

## Архитектура

```
GitHub Issues (с префиксом [HERMES-TASK]) → Cron (5m) → Worker-скрипт → LLM (hermes chat) → GitHub комментарии
```

## Установка

1. Скрипт: `~/.hermes/scripts/github_worker.sh`
2. Cron-задача: `hermes cron create "5m" --script github_worker.sh --name "github-monitor"`
3. Требуется авторизация `gh` CLI с доступом `repo`.

## Протокол статусов

| Статус | Значение | Пример комментария |
|--------|----------|-------------------|
| IN_PROGRESS | Задача запущена | `🤖 *STATUS: IN_PROGRESS*` |
| DONE | Задача выполнена | `🤖 *STATUS: DONE*` + отчёт |
| BLOCKED | Ошибка | `🤖 *STATUS: BLOCKED*` + причина |

## Порядок работы

1. **Получение**: Cron запускает скрипт каждые 5 минут.
2. **Фильтрация**: Ищет open issues с префиксом `[HERMES-TASK]`.
3. **Дедупликация**: Проверяет `processed_issues.txt`.
4. **Включение**: Публикует `STATUS: IN_PROGRESS`.
5. **Обработка**: Отправляет задачу в LLM через `hermes chat`.
6. **Финал**: Публикует `STATUS: DONE` с отчётом.
7. **Упаковка**: Добавляет номер в `processed_issues.txt`.

## Восстановление после перезапуска

- Крон-задача автоматически возобновляет выполнение.
- Проверка: `hermes cron status` показывает PID и следующее выполнение.
- Логи: `<WORK_DIR>/logs/worker.log`.

## Ограничения

- Использует только `gh` CLI + `hermes chat` (встроенные средства).
- Интервал опроса: 5 минут (настраивается).
- LLM-ответ обрезается до 3000 символов.

## Остановка

- `hermes cron pause <job_id>` — приостановить
- `hermes cron resume <job_id>` — возобновить
- `hermes cron remove <job_id>` — удалить
