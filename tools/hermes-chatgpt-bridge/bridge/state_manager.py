"""Менеджер состояния_bridge."""

import os
import json
import threading
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

# Настройка логирования
logger = logging.getLogger(__name__)

# Состояния задач
STATE_NEW = "NEW"
STATE_PROCESSING = "PROCESSING"
STATE_SUBMITTED = "SUBMITTED"
STATE_RESPONSE_READY = "RESPONSE_READY"
STATE_SENT = "SENT"
STATE_FAILED = "FAILED"

class StateManager:
    """Менеджер состояния задач."""

    def __init__(self, state_file: str, logs_dir: str = None):
        """Инициализация менеджера состояния."""
        self.state_file = state_file
        self.logs_dir = logs_dir
        self._lock = threading.Lock()
        self._log_file = None
        if logs_dir:
            os.makedirs(logs_dir, exist_ok=True)
            # Лог текущей сессии
            self._log_file = os.path.join(logs_dir, "state_manager.log")

    def _log(self, message: str, level: str = "INFO"):
        """Запись лога."""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        if self._log_file:
            try:
                with open(self._log_file, "a", encoding="utf-8") as f:
                    f.write(log_entry)
            except Exception as e:
                logger.warning(f"Не удалось записать лог: {e}")
        logger.log(getattr(logging, level.upper(), logging.INFO), message)

    def _load_state(self) -> Dict[str, Any]:
        """Загрузка состояния из файла."""
        with self._lock:
            if os.path.exists(self.state_file):
                try:
                    with open(self.state_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            return {"tasks": {}, "next_id": 1}

    def _save_state(self, state: Dict[str, Any]):
        """Сохранение состояния в файл."""
        with self._lock:
            temp_file = self.state_file + ".tmp"
            try:
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                os.replace(temp_file, self.state_file)
            except Exception as e:
                logger.error(f"Ошибка сохранения состояния: {e}")
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass

    def create_task(self, task_id: str, message: str) -> str:
        """Создание новой задачи."""
        state = self._load_state()
        task_id_int = state.get("next_id", 1)
        state["next_id"] = task_id_int + 1

        task = {
            "task_id": task_id,
            "message": message,
            "state": STATE_NEW,
            "admission_id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "result": None
        }
        state["tasks"][task_id] = task
        self._save_state(state)
        self._log(f"Создана новая задача {task_id}")
        return task_id

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Получение задачи по ID."""
        state = self._load_state()
        return state["tasks"].get(str(task_id))

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Получение списка ожидающих задач."""
        state = self._load_state()
        pending = []
        for task_id, task in state["tasks"].items():
            if task["state"] in (STATE_NEW, STATE_PROCESSING, STATE_SUBMITTED, STATE_RESPONSE_READY):
                pending.append(task)
        return pending

    def mark_task_processing(self, task_id: int):
        """Метка задачи как обработанной."""
        state = self._load_state()
        if str(task_id) in state["tasks"]:
            task = state["tasks"][str(task_id)]
            task["state"] = STATE_PROCESSING
            task["updated_at"] = datetime.now().isoformat()
            self._save_state(state)
            self._log(f"Задача {task_id} переведена в PROCESSING")

    def mark_task_submitted(self, task_id: int):
        """Метка задачи как отправленной в Hermes."""
        state = self._load_state()
        if str(task_id) in state["tasks"]:
            task = state["tasks"][str(task_id)]
            task["state"] = STATE_SUBMITTED
            task["updated_at"] = datetime.now().isoformat()
            self._save_state(state)
            self._log(f"Задача {task_id} отправлена в Hermes (SUBMITTED)")

    def mark_task_response_ready(self, task_id: int, result: str):
        """Метка задачи как готовой с результатом."""
        state = self._load_state()
        if str(task_id) in state["tasks"]:
            task = state["tasks"][str(task_id)]
            task["state"] = STATE_RESPONSE_READY
            task["result"] = result
            task["updated_at"] = datetime.now().isoformat()
            self._save_state(state)
            self._log(f"Задача {task_id} готова с результатом (RESPONSE_READY)")

    def mark_task_sent(self, task_id: int):
        """Метка задачи как отправленной в ChatGPT."""
        state = self._load_state()
        if str(task_id) in state["tasks"]:
            task = state["tasks"][str(task_id)]
            task["state"] = STATE_SENT
            task["updated_at"] = datetime.now().isoformat()
            self._save_state(state)
            self._log(f"Задача {task_id} отправлена в ChatGPT (SENT)")

    def mark_task_failed(self, task_id: int, error: str):
        """Метка задачи как ошибки."""
        state = self._load_state()
        if str(task_id) in state["tasks"]:
            task = state["tasks"][str(task_id)]
            task["state"] = STATE_FAILED
            task["updated_at"] = datetime.now().isoformat()
            self._save_state(state)
            self._log(f"Ошибка задачи {task_id}: {error}", "ERROR")
