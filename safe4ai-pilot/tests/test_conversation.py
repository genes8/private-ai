from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models import Message, PrivateAIState
from app.services.conversation import ConversationManager


def _make_manager(db: MagicMock | None = None) -> ConversationManager:
    return ConversationManager(db=db or MagicMock())


def _make_state(session_id: str = "sess-1", user_id: str = "user-1") -> PrivateAIState:
    return PrivateAIState(session_id=session_id, user_id=user_id)


def test_new_session_creates_db_row() -> None:
    db = MagicMock()
    manager = _make_manager(db=db)

    session_id = manager.new_session("user-1", "ws-1")

    assert isinstance(session_id, str)
    assert len(session_id) > 0
    db.add.assert_called_once()
    db.commit.assert_called_once()

    added_row = db.add.call_args[0][0]
    assert added_row.user_id == "user-1"
    assert added_row.workspace_id == "ws-1"
    assert added_row.id == session_id


def test_load_session_success() -> None:
    db = MagicMock()
    state = _make_state()
    mock_row = MagicMock()
    mock_row.state_json = state.model_dump()
    db.get.return_value = mock_row

    manager = _make_manager(db=db)
    loaded = manager.load_session("sess-1")

    assert isinstance(loaded, PrivateAIState)
    assert loaded.session_id == "sess-1"
    assert loaded.user_id == "user-1"


def test_load_session_not_found() -> None:
    db = MagicMock()
    db.get.return_value = None

    manager = _make_manager(db=db)

    with pytest.raises(KeyError):
        manager.load_session("nonexistent")


def test_save_session_updates_db() -> None:
    db = MagicMock()
    state = _make_state()
    mock_row = MagicMock()
    db.get.return_value = mock_row

    manager = _make_manager(db=db)
    manager.save_session(state)

    assert mock_row.state_json == state.model_dump()
    db.commit.assert_called_once()


def test_load_session_raises_value_error_on_invalid_state() -> None:
    db = MagicMock()
    mock_row = MagicMock()
    # current_step must be one of the Literal values; "invalid_step" triggers ValidationError
    mock_row.state_json = {"session_id": "sess-1", "user_id": "u1", "current_step": "invalid_step"}
    db.get.return_value = mock_row

    manager = _make_manager(db=db)
    with pytest.raises(ValueError, match="Invalid session state"):
        manager.load_session("sess-1")


def test_save_session_strips_control_characters() -> None:
    db = MagicMock()
    state = _make_state()
    state.messages = [Message(role="user", content="Hello\x00World\x01!")]
    mock_row = MagicMock()
    db.get.return_value = mock_row

    manager = _make_manager(db=db)
    manager.save_session(state)

    saved = mock_row.state_json
    messages = saved.get("messages", [])
    assert len(messages) == 1
    assert "\x00" not in messages[0]["content"]
    assert messages[0]["content"] == "HelloWorld!"


def test_save_session_preserves_newlines() -> None:
    """Tab and newline (\\t, \\n) are allowed; only unsafe control chars are stripped."""
    db = MagicMock()
    state = _make_state()
    state.messages = [Message(role="user", content="Line1\nLine2\tTabbed")]
    mock_row = MagicMock()
    db.get.return_value = mock_row

    manager = _make_manager(db=db)
    manager.save_session(state)

    saved = mock_row.state_json
    content = saved["messages"][0]["content"]
    assert "\n" in content
    assert "\t" in content


def test_get_recent_messages() -> None:
    db = MagicMock()
    state = _make_state()
    state.messages = [Message(role="user", content=f"msg {i}") for i in range(5)]
    mock_row = MagicMock()
    mock_row.state_json = state.model_dump()
    db.get.return_value = mock_row

    manager = _make_manager(db=db)
    msgs = manager.get_recent_messages("sess-1", n=3)

    assert len(msgs) == 3
    assert msgs[-1].content == "msg 4"
