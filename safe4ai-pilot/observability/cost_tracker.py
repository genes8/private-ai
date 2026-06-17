from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select
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

    def get_stats(
        self,
        db: Session,
        user_id: str | None = None,
        days: int = 30,
        workspace_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Return aggregate cost stats over the last `days` days.

        If user_id is provided, only runs for sessions owned by that user are included.
        If workspace_ids is provided, only runs in those workspaces are included
        (cost is filtered by AgentRun.workspace_id — the row's own column).
        Returns:
            {
                "total_cost_usd": float,
                "total_tokens": float,   # not stored directly; omitted if unavailable
                "runs_count": int,
                "by_day": [{"date": "YYYY-MM-DD", "cost_usd": float, "runs": int}, ...],
            }
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        base_filter = AgentRun.started_at >= cutoff
        join_clause = None
        if user_id is not None:
            from app.db.models import Session as DBSession
            join_clause = (AgentRun.session_id == DBSession.id, DBSession.user_id == user_id)

        def _scope(stmt: Any) -> Any:
            if workspace_ids is not None:
                stmt = stmt.where(AgentRun.workspace_id.in_(workspace_ids))
            return stmt

        # Total cost & count via SQL aggregation (no Python-side loading)
        agg_stmt = _scope(
            select(
                func.coalesce(func.sum(AgentRun.cost_usd), 0.0),
                func.count(AgentRun.id),
            ).where(base_filter)
        )
        if join_clause:
            agg_stmt = agg_stmt.join(join_clause[0].clause).where(join_clause[1])
        total_cost, runs_count = db.execute(agg_stmt).one()
        total_cost = float(total_cost) if total_cost else 0.0
        runs_count = int(runs_count) if runs_count else 0

        # Per-day breakdown via SQL aggregation
        day_stmt = _scope(
            select(
                func.date(AgentRun.started_at).label("day"),
                func.coalesce(func.sum(AgentRun.cost_usd), 0.0).label("day_cost"),
                func.count(AgentRun.id).label("day_runs"),
            ).where(base_filter)
        ).group_by(func.date(AgentRun.started_at)).order_by("day")
        if join_clause:
            day_stmt = day_stmt.join(join_clause[0].clause).where(join_clause[1])

        by_day = []
        for day, day_cost, day_runs in db.execute(day_stmt):
            by_day.append({
                "date": str(day),
                "cost_usd": round(float(day_cost), 6),
                "runs": int(day_runs),
            })

        return {
            "total_cost_usd": round(total_cost, 6),
            "runs_count": runs_count,
            "by_day": by_day,
        }
