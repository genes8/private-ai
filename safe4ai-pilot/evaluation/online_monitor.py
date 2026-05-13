#!/usr/bin/env python3
"""Online monitoring: sample recent queries from audit_logs and score heuristically.

Run:
    python evaluation/online_monitor.py [--days 1] [--sample-rate 0.1]

Metrics:
    - fallback_rate: fraction of sampled queries where answer is the fallback string
    - avg_retrieval_score: mean max retrieval score across sampled agent_runs
    - user_feedback_ratio: positive / (positive + negative) from query_feedback

Writes results to evaluation/eval_results/monitor_YYYY-MM-DD.json.
Logs WARN if fallback_rate > 0.20 or avg_retrieval_score < 0.5.
"""

from __future__ import annotations

import json
import os
import random
import sys
import warnings
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

RESULTS_DIR = Path(__file__).parent / "eval_results"
RESULTS_DIR.mkdir(exist_ok=True)

_FALLBACK_THESHOLD = 0.20
_RETRIEVAL_SCORE_THRESHOLD = 0.5
_NO_ANSWER_MARKER = "don't have enough information"


def _get_db_url() -> str:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv()
    return os.environ.get("POSTGRES_URL", "")


def _sample_audit_logs(db_url: str, days: int, sample_rate: float) -> list[dict]:
    """Return a random sample of recent audit_log rows as dicts."""
    try:
        import sqlalchemy as sa
        engine = sa.create_engine(db_url)
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT id, trace_id, query_text, action_type "
                    "FROM audit_logs WHERE timestamp >= :cutoff ORDER BY timestamp DESC LIMIT 2000"
                ),
                {"cutoff": cutoff},
            ).fetchall()
        sample_size = max(1, int(len(rows) * sample_rate))
        sampled = random.sample(rows, min(sample_size, len(rows)))
        return [dict(r._mapping) for r in sampled]
    except Exception as exc:
        warnings.warn(f"online_monitor: could not query audit_logs: {exc}", stacklevel=2)
        return []


def _get_agent_runs(db_url: str, trace_ids: list[str]) -> dict[str, dict]:
    """Return agent_run data keyed by trace_id."""
    if not trace_ids:
        return {}
    try:
        import sqlalchemy as sa
        engine = sa.create_engine(db_url)
        with engine.connect() as conn:
            placeholders = ", ".join(f":t{i}" for i in range(len(trace_ids)))
            params = {f"t{i}": t for i, t in enumerate(trace_ids)}
            rows = conn.execute(
                sa.text(
                    f"SELECT trace_id, retrieval_score_max, final_answer "
                    f"FROM agent_runs WHERE trace_id IN ({placeholders})"
                ),
                params,
            ).fetchall()
        return {r.trace_id: dict(r._mapping) for r in rows}
    except Exception as exc:
        warnings.warn(f"online_monitor: could not query agent_runs: {exc}", stacklevel=2)
        return {}


def _get_feedback_ratio(db_url: str, days: int) -> float | None:
    try:
        import sqlalchemy as sa
        engine = sa.create_engine(db_url)
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with engine.connect() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT rating, COUNT(*) as cnt FROM query_feedback "
                    "WHERE created_at >= :cutoff GROUP BY rating"
                ),
                {"cutoff": cutoff},
            ).fetchall()
        counts: dict[str, int] = {}
        for r in rows:
            counts[r.rating] = int(r.cnt)
        positive = counts.get("positive", 0)
        negative = counts.get("negative", 0)
        total = positive + negative
        return positive / total if total > 0 else None
    except Exception as exc:
        warnings.warn(f"online_monitor: could not query query_feedback: {exc}", stacklevel=2)
        return None


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Online RAG quality monitor")
    parser.add_argument("--days", type=int, default=1, help="Look-back window in days")
    parser.add_argument("--sample-rate", type=float, default=0.1, help="Fraction of queries to sample")
    args = parser.parse_args()

    db_url = _get_db_url()
    if not db_url:
        print("WARN: POSTGRES_URL not set; skipping database metrics")
        db_url = ""

    logs = _sample_audit_logs(db_url, args.days, args.sample_rate) if db_url else []
    trace_ids = [r.get("trace_id", "") for r in logs if r.get("trace_id")]
    agent_runs = _get_agent_runs(db_url, trace_ids) if trace_ids else {}

    # Fallback rate: fraction of sampled log entries that are the no-answer response
    fallback_count = 0
    retrieval_scores: list[float] = []

    for log in logs:
        tid = log.get("trace_id", "")
        run = agent_runs.get(tid, {})
        answer = run.get("final_answer", log.get("query_text", ""))
        if answer and _NO_ANSWER_MARKER in str(answer).lower():
            fallback_count += 1
        score = run.get("retrieval_score_max")
        if score is not None:
            retrieval_scores.append(float(score))

    fallback_rate = fallback_count / len(logs) if logs else 0.0
    avg_retrieval_score = sum(retrieval_scores) / len(retrieval_scores) if retrieval_scores else None
    feedback_ratio = _get_feedback_ratio(db_url, args.days) if db_url else None

    # Alerts
    alerts: list[str] = []
    if fallback_rate > _FALLBACK_THESHOLD:
        msg = f"WARN: fallback_rate={fallback_rate:.2%} > {_FALLBACK_THESHOLD:.0%} threshold"
        print(msg)
        alerts.append(msg)
    if avg_retrieval_score is not None and avg_retrieval_score < _RETRIEVAL_SCORE_THRESHOLD:
        msg = f"WARN: avg_retrieval_score={avg_retrieval_score:.3f} < {_RETRIEVAL_SCORE_THRESHOLD}"
        print(msg)
        alerts.append(msg)

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "look_back_days": args.days,
        "sample_rate": args.sample_rate,
        "sampled_queries": len(logs),
        "fallback_rate": round(fallback_rate, 4),
        "avg_retrieval_score": round(avg_retrieval_score, 4) if avg_retrieval_score is not None else None,
        "user_feedback_ratio": round(feedback_ratio, 4) if feedback_ratio is not None else None,
        "alerts": alerts,
    }

    out_path = RESULTS_DIR / f"monitor_{datetime.now(UTC).strftime('%Y-%m-%d')}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"Monitor results written to {out_path}")

    for k, v in summary.items():
        if k not in ("alerts",):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
