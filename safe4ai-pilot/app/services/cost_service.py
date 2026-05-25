"""Cost tracking and ceiling enforcement for chat requests.

Extracted from app/api/chat_routes.py so that cost business logic can be
tested and reused without importing FastAPI (no HTTPException anywhere here).
"""
from __future__ import annotations

import math

import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.services.provider_clients import ProviderUsage
from observability.cost_tracker import CostTracker

logger = structlog.get_logger(__name__)


class CostCeilingExceeded(Exception):
    """Daily or monthly cost ceiling has been reached.

    Carry the user-facing message in ``detail`` so the route handler
    can set it directly in the HTTP 429 response without re-formatting.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


def estimate_tokens(text: str) -> int:
    """Approximate token count with a chars-per-token heuristic."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, math.ceil(len(stripped) / 4))


def usage_or_estimate(
    question: str, answer: str, provider_usage: ProviderUsage | None
) -> ProviderUsage:
    """Return provider_usage if available; otherwise estimate from text lengths."""
    if provider_usage is not None:
        return provider_usage
    prompt_tokens = estimate_tokens(question)
    completion_tokens = estimate_tokens(answer)
    return ProviderUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        source="estimated",
    )


def check_cost_ceiling(
    db: Session,
    *,
    projected_question: str | None = None,
) -> None:
    """Raise CostCeilingExceeded if the daily or monthly ceiling has been reached.

    Swallows unexpected exceptions (e.g. DB unavailable) with a warning so
    that a broken cost-tracker never blocks a legitimate chat request.
    """
    try:
        from app.services.app_config_store import load_app_config

        db_overrides = load_app_config(db)
        daily_ceiling = float(db_overrides.get("daily_ceiling_usd", 50))
        monthly_ceiling = float(db_overrides.get("monthly_ceiling_usd", 500))
        tracker = CostTracker(settings.cost_per_1k_tokens)
        projected_cost = 0.0
        if projected_question:
            prompt_tokens = estimate_tokens(projected_question)
            completion_tokens = max(estimate_tokens(projected_question), 256)
            projected_cost = tracker.calculate(prompt_tokens, completion_tokens)

        today_cost = tracker.get_stats(db, days=1)["total_cost_usd"]
        if today_cost >= daily_ceiling:
            raise CostCeilingExceeded(
                f"Daily cost ceiling reached (${today_cost:.2f} / ${daily_ceiling:.2f})"
            )
        if projected_cost and (today_cost + projected_cost) > daily_ceiling:
            raise CostCeilingExceeded(
                "Projected request would exceed daily cost ceiling "
                f"(${today_cost + projected_cost:.2f} / ${daily_ceiling:.2f})"
            )

        month_cost = tracker.get_stats(db, days=30)["total_cost_usd"]
        if month_cost >= monthly_ceiling:
            raise CostCeilingExceeded(
                f"Monthly cost ceiling reached (${month_cost:.2f} / ${monthly_ceiling:.2f})"
            )
        if projected_cost and (month_cost + projected_cost) > monthly_ceiling:
            raise CostCeilingExceeded(
                "Projected request would exceed monthly cost ceiling "
                f"(${month_cost + projected_cost:.2f} / ${monthly_ceiling:.2f})"
            )
    except CostCeilingExceeded:
        raise
    except Exception as exc:
        logger.warning("cost_ceiling_check_failed", error=str(exc))
