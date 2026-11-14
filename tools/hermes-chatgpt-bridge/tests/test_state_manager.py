"""Тесты для StateManager."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

from bridge.state_manager import StateManager, STATE_NEW, STATE_PROCESSING, STATE_SUBMITTED, STATE_RESPONSE_READY, STATE_SENT, STATE_FAILED

# Set up a temporary logs directory for tests
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(_TEST_DIR, "logs"), exist_ok=True)

class TestStateManager:
    """Тесты для StateManager."""

    def test_create_task(self):
        """Тест: создание задачи."""
        state = StateManager(os.path.join(_TEST_DIR, "logs", "test_state.db"))
        task_id = state.create_task("msg-1", "HELLOWORLD")
        assert task_id is not None
        assert task_id != ""
        assert state.get_task(task_id) is not None
        os.remove(state.state_file)

    def test_state_transitions(self):
        """Тест: переходы состояний."""
        state = StateManager(os.path.join(_TEST_DIR, "logs", "test_state.db"))
        task_id = state.create_task("msg-1", "HELLOWORLD")

        # NEW -> PROCESSING
        state.mark_task_processing(task_id)
        assert state.get_task(task_id)["state"] == STATE_PROCESSING

        # PROCESSING -> SUBMITTED
        state.mark_task_submitted(task_id)
        assert state.get_task(task_id)["state"] == STATE_SUBMITTED

        # SUBMITTED -> RESPONSE_READY
        state.mark_task_response_ready(task_id, "Результат")
        assert state.get_task(task_id)["state"] == STATE_RESPONSE_READY

        # RESPONSE_READY -> SENT
        state.mark_task_sent(task_id)
        assert state.get_task(task_id)["state"] == STATE_SENT

        state.mark_task_failed(task_id, "Ошибка")
        assert state.get_task(task_id)["state"] == STATE_FAILED
        os.remove(state.state_file)

    def test_admission_id_generation(self):
        """Тест: генерация admission_id."""
        state = StateManager(os.path.join(_TEST_DIR, "logs", "test_admission.db"))
        task_id = state.create_task("msg-1", "HELLOWORLD")
        task = state.get_task(task_id)
        assert "admission_id" in task
        assert len(task["admission_id"]) > 0
        os.remove(state.state_file)

    def test_recovery_after_restart(self):
        """Тест: восстановление после перезапуска."""
        state = StateManager(os.path.join(_TEST_DIR, "logs", "test_recovery.db"))
        task_id = state.create_task("msg-1", "HELLOWORLD")
        state.mark_task_processing(task_id)
        state2 = StateManager(state.state_file)
        pending = state2.get_pending_tasks()
        assert len(pending) == 1
        assert pending[0]["task_id"] == task_id
        os.remove(state.state_file)

    def test_dedup_after_sent(self):
        """Тест: исключение повторного выполнения отправленных задач."""
        state = StateManager(os.path.join(_TEST_DIR, "logs", "test_dedup.db"))
        task_id = state.create_task("msg-1", "HELLOWORLD")
        state.mark_task_sent(task_id)
        pending = state.get_pending_tasks()
        assert len(pending) == 0
        os.remove(state.state_file)
