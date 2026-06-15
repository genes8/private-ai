from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import httpx
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models import Session as DbSession
from app.models import Message, PrivateAIState
from app.prompts.registry import get_prompt

_SUMMARIZE_THRESHOLD = 10
_MAX_STATE_JSON_BYTES = 1_000_000  # 1 MB hard limit for sessions.state_json
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _strip_control_chars(text: str) -> str:
    return _CONTROL_CHAR_RE.sub("", text)


class ConversationManager:
    def __init__(self, db: Session) -> None:
        self._db = db

    def new_session(self, user_id: str, workspace_id: str) -> str:
        session_id = str(uuid.uuid4())
        # The session is permanently bound to this workspace (see the 409 check in
        # the chat route): its history must never mix contexts across workspaces.
        state = PrivateAIState(
            session_id=session_id, user_id=user_id, workspace_ids=[workspace_id]
        )
        db_row = DbSession(
            id=session_id,
            user_id=user_id,
            workspace_id=workspace_id,
            state_json=state.model_dump(mode="json"),
        )
        self._db.add(db_row)
        self._db.commit()
        return session_id

    def load_session(self, session_id: str) -> PrivateAIState:
        row = self._db.get(DbSession, session_id)
        if row is None:
            raise KeyError(f"Session {session_id!r} not found")
        state_data = cast(dict[str, Any], row.state_json or {})
        try:
            return PrivateAIState(**state_data)
        except ValidationError as exc:
            raise ValueError(f"Invalid session state for {session_id!r}: {exc}") from exc

    def save_session(self, state: PrivateAIState) -> None:
        row = self._db.get(DbSession, state.session_id)
        if row is None:
            raise KeyError(f"Session {state.session_id!r} not found")
        clean_messages = [
            m.model_copy(update={"content": _strip_control_chars(m.content)})
            for m in state.messages
        ]
        clean_state = state.model_copy(update={"messages": clean_messages})
        dumped = clean_state.model_dump(mode="json")
        encoded = json.dumps(dumped).encode()
        if len(encoded) > _MAX_STATE_JSON_BYTES:
            raise ValueError(
                f"Session state exceeds {_MAX_STATE_JSON_BYTES // 1024} KB limit "
                f"({len(encoded)} bytes); truncate messages before saving"
            )
        row.state_json = dumped
        self._db.commit()

    def get_recent_messages(self, session_id: str, n: int = 10) -> list[Message]:
        state = self.load_session(session_id)
        return state.messages[-n:]

    async def maybe_summarize(
        self,
        session_id: str,
        *,
        ollama_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Summarize conversation history when it exceeds the threshold."""
        state = self.load_session(session_id)
        if len(state.messages) <= _SUMMARIZE_THRESHOLD:
            return

        template = get_prompt("conversation_summarizer", "v1")
        conversation_text = "\n".join(f"{m.role}: {m.content}" for m in state.messages)
        prompt = template.template.format(conversation=conversation_text)

        async def _call(c: httpx.AsyncClient) -> str:
            resp = await c.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=60.0,
            )
            resp.raise_for_status()
            return str(resp.json().get("response", "")).strip()

        try:
            if client is not None:
                summary = await _call(client)
            else:
                async with httpx.AsyncClient() as c:
                    summary = await _call(c)
        except Exception:
            # Summarization failed — truncate to the last N messages to prevent unbounded growth
            keep = _SUMMARIZE_THRESHOLD - 1
            truncated_state = state.model_copy(update={"messages": state.messages[-keep:]})
            self.save_session(truncated_state)
            return

        summary_message = Message(
            role="assistant",
            content=f"[Conversation summary] {summary}",
            created_at=datetime.now(UTC),
        )
        recent_tail = (
            state.messages[-(_SUMMARIZE_THRESHOLD - 1):] if _SUMMARIZE_THRESHOLD > 1 else []
        )
        updated_state = state.model_copy(update={"messages": [summary_message, *recent_tail]})
        self.save_session(updated_state)
