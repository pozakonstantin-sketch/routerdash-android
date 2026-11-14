"""Тесты для моста — дедупликация и восстановление состояния."""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

from bridge.state_manager import StateManager


class TestStateManager:
    """Тесты для StateManager."""

    def test_init_creates_db(self):
        """Тест: инициализация создаёт SQLite-файл."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            sm = StateManager(db_path)
            assert os.path.exists(db_path)
            assert sm.state_file.exists()

    def test_mark_and_check_processed(self):
        """Тест: маркировка и проверка сообщения."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            sm = StateManager(db_path)

            msg_id = "msg_123"
            sm.mark_processed(msg_id, "chatgpt", "https://chatgpt.com")

            # Должно быть отмечено как обработанное
            assert sm.is_processed(msg_id)
            # Должно быть отмечено как не обработанное
            assert not sm.is_processed("msg_456")

    def test_duplicate_prevention(self):
        """Тест: предотвращение дублирования сообщений."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            sm = StateManager(db_path)

            msg_id = "msg_duplicate"
            sm.mark_processed(msg_id)

            # Повторная маркировка не должна создавать дубликатов
            sm.mark_processed(msg_id)
            with sqlite3.connect(db_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM processed_messages WHERE message_id = ?",
                    (msg_id,)
                ).fetchone()[0]
                assert count == 1

    def test_save_conversation(self):
        """Тест: сохранение диалога."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            sm = StateManager(db_path)

            uid = sm.save_conversation("Тестовое сообщение", "Ответ агента")
            assert uid > 0

            # Проверка записи в БД
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM conversations WHERE id = ?",
                    (uid,)
                ).fetchone()
                assert row is not None
                assert row["user_message"] == "Тестовое сообщение"
                assert row["assistant_message"] == "Ответ агента"

    def test_get_last_processed(self):
        """Тест: получение последнего обработанного сообщения."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            sm = StateManager(db_path)

            sm.mark_processed("msg_1", "chatgpt")
            sm.mark_processed("msg_2", "chatgpt")

            last = sm.get_last_processed()
            assert last is not None
            assert last["message_id"] == "msg_2"

    def test_list_all_messages(self):
        """Тест: список всех сообщений."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            sm = StateManager(db_path)

            sm.mark_processed("msg_1", "chatgpt")
            sm.mark_processed("msg_2", "chatgpt")

            messages = sm.list_all_messages()
            assert len(messages) == 2
