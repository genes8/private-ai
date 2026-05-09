from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy.orm import Session

from app.db.models import Session as DbSession
from app.models import Message, PrivateAIState


class ConversationManager:
    def __init__(self, db: Session) -> None:
        self._db = db

    def new_session(self, user_id: str) -> str:
        session_id = str(uuid.uuid4())
        state = PrivateAIState(session_id=session_id, user_id=user_id)
        db_row = DbSession(
            id=session_id,
            user_id=user_id,
            state_json=state.model_dump(),
        )
        self._db.add(db_row)
        self._db.commit()
        return session_id

    def load_session(self, session_id: str) -> PrivateAIState:
        row = self._db.get(DbSession, session_id)
        if row is None:
            raise KeyError(f"Session {session_id!r} not found")
        state_data = cast(dict[str, Any], row.state_json or {})
        return PrivateAIState(**state_data)

    def save_session(self, state: PrivateAIState) -> None:
        row = self._db.get(DbSession, state.session_id)
        if row is None:
            raise KeyError(f"Session {state.session_id!r} not found")
        setattr(row, "state_json", state.model_dump())
        self._db.commit()

    def get_recent_messages(self, session_id: str, n: int = 10) -> list[Message]:
        state = self.load_session(session_id)
        return state.messages[-n:]
