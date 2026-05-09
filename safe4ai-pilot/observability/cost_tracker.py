from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentRun

logger = structlog.get_logger(__name__)


class CostTracker:
    """Tracks token usage and compute cost for agent runs."""

    def __init__(self, cost_per_1k_tokens: float) -> None:
        self._cost_per_1k = cost_per_1k_tokens

    def calculate(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Return cost_usd = (prompt_tokens + completion_tokens) / 1000 * cost_per_1k_tokens."""
        total_tokens = prompt_tokens + completion_tokens
        return total_tokens / 1000.0 * self._cost_per_1k

    def record_run(
        self,
        db: Session,
        session_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        status: str = "completed",
    ) -> str:
        """Create an AgentRun row in the database and return its UUID."""
        run_id = str(uuid.uuid4())
        cost_usd = self.calculate(prompt_tokens, completion_tokens)
        now = datetime.now(UTC)
        run = AgentRun(
            id=run_id,
            session_id=session_id,
            started_at=now,
            finished_at=now,
            status=status,
            cost_usd=cost_usd,
            final_output=None,
            error=None,
        )
        db.add(run)
        db.commit()
        logger.info(
            "agent_run_recorded",
            run_id=run_id,
            session_id=session_id,
            model=model,
            cost_usd=cost_usd,
            status=status,
        )
        return run_id

    def get_stats(self, db: Session, user_id: str | None = None, days: int = 30) -> dict[str, Any]:
        """Return aggregate cost stats over the last `days` days.

        If user_id is provided, only runs for sessions owned by that user are included.
        Returns:
            {
                "total_cost_usd": float,
                "total_tokens": float,   # not stored directly; omitted if unavailable
                "runs_count": int,
                "by_day": [{"date": "YYYY-MM-DD", "cost_usd": float, "runs": int}, ...],
            }
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        stmt = select(AgentRun).where(AgentRun.started_at >= cutoff)

        if user_id is not None:
            # AgentRun has no direct user_id; filter via Session table
            from app.db.models import Session as DBSession  # local import to avoid circular

            stmt = stmt.join(DBSession, AgentRun.session_id == DBSession.id).where(
                DBSession.user_id == user_id
            )

        rows: list[AgentRun] = list(db.execute(stmt).scalars().all())

        total_cost = sum(r.cost_usd or 0.0 for r in rows)
        runs_count = len(rows)

        # Group by calendar date (UTC)
        by_day_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            dt = row.started_at
            # started_at may be naive (no tzinfo) when returned from DB depending on dialect
            if dt is None:
                continue
            date_key = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
            entry = by_day_map.setdefault(date_key, {"date": date_key, "cost_usd": 0.0, "runs": 0})
            entry["cost_usd"] = round(entry["cost_usd"] + (row.cost_usd or 0.0), 6)
            entry["runs"] += 1

        by_day = sorted(by_day_map.values(), key=lambda x: x["date"])

        return {
            "total_cost_usd": round(total_cost, 6),
            "runs_count": runs_count,
            "by_day": by_day,
        }
