"""
Unit tests for backend/history.py

All PostgreSQL calls are mocked via a fake connection/cursor so
no real database is required.
"""
import pytest
from unittest.mock import MagicMock, call
from tests.conftest import make_mock_conn
import backend.history as hist


# ---------------------------------------------------------------------------
# Fixture — mock DB connection per test
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db(monkeypatch):
    """Patch get_conn and put_conn as imported in backend.history."""
    mock_conn, mock_cursor = make_mock_conn()
    monkeypatch.setattr(hist, "get_conn", MagicMock(return_value=mock_conn))
    monkeypatch.setattr(hist, "put_conn", MagicMock())
    return mock_conn, mock_cursor


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------

class TestGetHistory:
    def test_returns_empty_for_none_conversation_id(self):
        # Short-circuits before any DB call — no mock needed
        assert hist.get_history(None) == []

    def test_returns_empty_when_db_has_no_rows(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchall.return_value = []

        result = hist.get_history("nonexistent-conv-id")
        assert result == []

    def test_returns_rows_as_dicts(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchall.return_value = [
            ("user", "What is aspirin?"),
            ("assistant", "Aspirin is an analgesic."),
        ]

        turns = hist.get_history("conv-1")
        assert turns == [
            {"role": "user", "content": "What is aspirin?"},
            {"role": "assistant", "content": "Aspirin is an analgesic."},
        ]

    def test_passes_conversation_id_to_query(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchall.return_value = []

        hist.get_history("my-conv-id")

        # Check the SQL was called with the correct conversation_id
        args = mock_cursor.execute.call_args[0]
        assert "my-conv-id" in args[1]

    def test_passes_limit_to_query(self, mock_db):
        from backend.config import MAX_HISTORY_TURNS
        mock_conn, mock_cursor = mock_db
        mock_cursor.fetchall.return_value = []

        hist.get_history("conv-limit")

        args = mock_cursor.execute.call_args[0]
        assert MAX_HISTORY_TURNS * 2 in args[1]


# ---------------------------------------------------------------------------
# save_turn
# ---------------------------------------------------------------------------

class TestSaveTurn:
    def test_none_conversation_id_is_noop(self, monkeypatch):
        mock_get = MagicMock()
        monkeypatch.setattr(hist, "get_conn", mock_get)
        monkeypatch.setattr(hist, "put_conn", MagicMock())

        hist.save_turn(None, "question", "answer")
        mock_get.assert_not_called()

    def test_inserts_user_and_assistant_rows(self, mock_db):
        mock_conn, mock_cursor = mock_db

        hist.save_turn("conv-save", "user question", "assistant answer")

        assert mock_cursor.execute.call_count == 2
        calls = mock_cursor.execute.call_args_list
        # First INSERT should be the user row
        assert "user" in calls[0][0][1]
        assert "user question" in calls[0][0][1]
        # Second INSERT should be the assistant row
        assert "assistant" in calls[1][0][1]
        assert "assistant answer" in calls[1][0][1]

    def test_commits_after_inserts(self, mock_db):
        mock_conn, mock_cursor = mock_db
        hist.save_turn("conv-commit", "q", "a")
        mock_conn.commit.assert_called_once()

    def test_rollback_on_error(self, mock_db):
        mock_conn, mock_cursor = mock_db
        mock_cursor.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception, match="DB error"):
            hist.save_turn("conv-err", "q", "a")

        mock_conn.rollback.assert_called_once()

    def test_connection_always_released(self, mock_db, monkeypatch):
        mock_conn, mock_cursor = mock_db
        mock_put = MagicMock()
        monkeypatch.setattr(hist, "put_conn", mock_put)

        hist.save_turn("conv-release", "q", "a")
        mock_put.assert_called_once_with(mock_conn)
