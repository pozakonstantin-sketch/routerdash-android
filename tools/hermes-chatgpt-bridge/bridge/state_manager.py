"""State Manager — SQLite-хранилище переписки с дедупликацией."""

import json
import logging
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class StateManager:
    """Управление состоянием переписки (SQLite + JSONL-журнал)."""

    def __init__(self, state_file: str = "logs/bridge_state.db"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Инициализировать SQLite-схему."""
        with sqlite3.connect(self.state_file) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    source_url TEXT,
                    received_at TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    hash TEXT UNIQUE
                );
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_message TEXT,
                    assistant_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_received ON processed_messages(received_at);
            """)
            conn.commit()

    def _get_hash(self, data: str) -> str:
        """Хэш для дедупликации."""
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def is_processed(self, message_id: str, source_name: str = "chatgpt") -> bool:
        """Проверить, было ли сообщение обработано."""
        with sqlite3.connect(self.state_file) as conn:
            cur = conn.execute(
                "SELECT 1 FROM processed_messages WHERE message_id = ?",
                (message_id,)
            )
            return cur.fetchone() is not None

    def mark_processed(self, message_id: str, source_name: str = "chatgpt",
                       source_url: str = None, content: str = None) -> None:
        """Метка сообщения как обработанное."""
        msg_hash = self._get_hash(message_id + source_name + str(datetime.now()))
        received_at = datetime.now().isoformat()
        with sqlite3.connect(self.state_file) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO processed_messages
                   (message_id, source_name, source_url, received_at, processed_at, hash)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (message_id, source_name, source_url, received_at, received_at, msg_hash)
            )
            conn.commit()

    def save_conversation(self, user_message: str, assistant_message: str) -> int:
        """Сохранить диалог в базу."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.state_file) as conn:
            cur = conn.execute(
                """INSERT INTO conversations (session_id, user_message, assistant_message, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (None, user_message[:5000], assistant_message[:5000], now, now)
            )
            conn.commit()
            return cur.lastrowid

    def get_last_processed(self) -> Optional[Dict[str, Any]]:
        """Получить последнее обработанное сообщение."""
        with sqlite3.connect(self.state_file) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT message_id, source_name, source_url, received_at FROM processed_messages ORDER BY received_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def list_all_messages(self) -> List[Dict[str, Any]]:
        """Список всех обработанных сообщений."""
        with sqlite3.connect(self.state_file) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT message_id, source_name, source_url, received_at, processed_at FROM processed_messages ORDER BY received_at DESC"
            )
            return [dict(r) for r in cur.fetchall()]

    def append_to_log(self, message: str, level: str = "INFO") -> None:
        """Добавить строку в JSONL-журнал handshake."""
        log_path = self.state_file.parent / "handshake.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }) + "\n"
        with open(log_path, "a") as f:
            f.write(entry)
