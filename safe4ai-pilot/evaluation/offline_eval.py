#!/usr/bin/env python3
"""Offline evaluation against the golden dataset.

Run:
    python evaluation/offline_eval.py [--threshold 0.75] [--collection default]

Scores:
    - retrieval_recall: did the correct source filename appear in citations? (binary)
    - answer_correctness: LLM-as-judge 1-5 scale → normalised to 0–1
    - citation_precision: fraction of citations matching expected sources
    - fallback_accuracy: for out-of-scope questions, did we return the fallback?

Writes results to evaluation/eval_results/YYYY-MM-DD_HH-MM.json.
Exits non-zero if overall score < threshold.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_DIR = Path(__file__).parent / "eval_results"
RESULTS_DIR.mkdir(exist_ok=True)

_NO_ANSWER_MARKER = "don't have enough information"


def _load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return json.load(f)


def _judge_answer(question: str, expected: str, generated: str, ollama_url: str, model: str) -> tuple[float, str]:
    """LLM-as-judge: score the generated answer vs. expected 1-5."""
    prompt = (
        f"Question: {question}\n\n"
        f"Expected answer: {expected}\n\n"
        f"Generated answer: {generated}\n\n"
        "Rate the generated answer on a scale of 1-5 for correctness and completeness "
        'compared to the expected answer. Return ONLY valid JSON: {"score": <int>, "reasoning": "<str>"}.'
    )
    try:
        resp = httpx.post(
            f"{ollama_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "{}")
        data = json.loads(raw)
        score = max(1, min(5, int(data.get("score", 1))))
        return (score - 1) / 4, str(data.get("reasoning", ""))
    except Exception as exc:
        return 0.0, f"judge error: {exc}"


def _score_entry(
    entry: dict,
    answer: str,
    citations: list[dict],
    ollama_url: str,
    model: str,
) -> dict:
    is_out_of_scope = entry.get("is_out_of_scope", False)
    expected_answer = entry.get("expected_answer")
    expected_citations = entry.get("expected_citations", [])

    result: dict = {"id": entry["id"], "difficulty": entry["difficulty"]}

    # Fallback accuracy: out-of-scope questions should trigger fallback
    if is_out_of_scope:
        triggered_fallback = _NO_ANSWER_MARKER in answer.lower()
        result["fallback_accuracy"] = 1.0 if triggered_fallback else 0.0
        result["retrieval_recall"] = None
        result["answer_correctness"] = None
        result["citation_precision"] = None
        result["overall"] = result["fallback_accuracy"]
        return result

    # Retrieval recall: did at least one expected source appear in citations?
    cited_files = {c.get("filename", "") for c in citations}
    expected_files = {c.get("filename", "") for c in expected_citations}
    retrieval_recall = 1.0 if expected_files and expected_files & cited_files else (0.0 if expected_files else 1.0)
    result["retrieval_recall"] = retrieval_recall

    # Answer correctness: LLM-as-judge
    if expected_answer and _NO_ANSWER_MARKER not in answer.lower():
        correctness, reasoning = _judge_answer(entry["question"], expected_answer, answer, ollama_url, model)
        result["answer_correctness"] = correctness
        result["judge_reasoning"] = reasoning
    else:
        result["answer_correctness"] = 0.0
        result["judge_reasoning"] = "no-answer or fallback returned"

    # Citation precision: fraction of citations that match expected sources
    if citations and expected_files:
        matched = sum(1 for c in citations if c.get("filename", "") in expected_files)
        result["citation_precision"] = matched / len(citations)
    else:
        result["citation_precision"] = 1.0 if not expected_files else 0.0

    result["fallback_accuracy"] = None

    weights = {"retrieval_recall": 0.4, "answer_correctness": 0.4, "citation_precision": 0.2}
    result["overall"] = sum(
        weights[k] * result[k] for k in weights if result[k] is not None
    )
    return result


def _run_pipeline(question: str, ollama_url: str, model: str, collection: str) -> tuple[str, list[dict]]:
    """Call the live RAG pipeline via HTTP."""
    try:
        resp = httpx.post(
            "http://localhost:8000/chat",
            json={"question": question, "collection": collection},
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return str(data.get("answer", "")), list(data.get("citations", []))
    except Exception as exc:
        return f"pipeline error: {exc}", []


def _previous_overall_score(results_dir: Path) -> float | None:
    files = sorted(results_dir.glob("*.json"), reverse=True)
    for f in files:
        try:
            data = json.loads(f.read_text())
            score = data.get("summary", {}).get("overall_score")
            if score is not None:
                return float(score)
        except Exception:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline RAG evaluation")
    parser.add_argument("--threshold", type=float, default=0.75, help="Min acceptable overall score")
    parser.add_argument("--collection", default="default", help="Qdrant collection to query")
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("OLLAMA_URL", "http://localhost:11434"),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
    )
    args = parser.parse_args()

    dataset = _load_dataset()
    print(f"Loaded {len(dataset)} golden Q&A pairs")

    results = []
    for entry in dataset:
        print(f"  [{entry['id']}] {entry['question'][:70]}...", end=" ", flush=True)
        answer, citations = _run_pipeline(entry["question"], args.ollama_url, args.model, args.collection)
        scored = _score_entry(entry, answer, citations, args.ollama_url, args.model)
        results.append(scored)
        print(f"overall={scored['overall']:.2f}")

    # Summary
    in_scope = [r for r in results if r.get("retrieval_recall") is not None]
    oos = [r for r in results if r.get("fallback_accuracy") is not None]

    avg_overall = sum(r["overall"] for r in results) / len(results) if results else 0.0
    avg_recall = sum(r["retrieval_recall"] for r in in_scope) / len(in_scope) if in_scope else None
    avg_correctness = sum(r["answer_correctness"] for r in in_scope) / len(in_scope) if in_scope else None
    avg_precision = sum(r["citation_precision"] for r in in_scope) / len(in_scope) if in_scope else None
    fallback_rate = sum(r["fallback_accuracy"] for r in oos) / len(oos) if oos else None

    by_difficulty: dict[str, dict] = {}
    for d in ("easy", "medium", "hard"):
        group = [r for r in in_scope if r["difficulty"] == d]
        by_difficulty[d] = {
            "count": len(group),
            "avg_overall": sum(r["overall"] for r in group) / len(group) if group else None,
        }

    summary = {
        "timestamp": datetime.now(UTC).isoformat(),
        "collection": args.collection,
        "model": args.model,
        "total_questions": len(results),
        "overall_score": round(avg_overall, 4),
        "avg_retrieval_recall": round(avg_recall, 4) if avg_recall is not None else None,
        "avg_answer_correctness": round(avg_correctness, 4) if avg_correctness is not None else None,
        "avg_citation_precision": round(avg_precision, 4) if avg_precision is not None else None,
        "fallback_accuracy": round(fallback_rate, 4) if fallback_rate is not None else None,
        "by_difficulty": by_difficulty,
        "threshold": args.threshold,
        "passed": avg_overall >= args.threshold,
    }

    prev_score = _previous_overall_score(RESULTS_DIR)
    if prev_score is not None:
        regression = prev_score - avg_overall
        summary["regression_vs_previous"] = round(regression, 4)
        if regression > 0.05:
            print(f"\nWARN: score regressed {regression:.2%} vs. previous run ({prev_score:.4f})")

    output = {"summary": summary, "results": results}
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M")
    out_path = RESULTS_DIR / f"{timestamp}.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\nResults written to {out_path}")

    print("\n--- Summary ---")
    print(f"Overall score:       {avg_overall:.4f}  (threshold: {args.threshold})")
    if avg_recall is not None:
        print(f"Retrieval recall:    {avg_recall:.4f}")
    if avg_correctness is not None:
        print(f"Answer correctness:  {avg_correctness:.4f}")
    if avg_precision is not None:
        print(f"Citation precision:  {avg_precision:.4f}")
    if fallback_rate is not None:
        print(f"Fallback accuracy:   {fallback_rate:.4f}")

    for d, info in by_difficulty.items():
        score_str = f"{info['avg_overall']:.4f}" if info["avg_overall"] is not None else "N/A"
        print(f"  {d.capitalize()} ({info['count']} Qs): {score_str}")

    if not summary["passed"]:
        print(f"\nFAIL: overall score {avg_overall:.4f} < threshold {args.threshold}")
        sys.exit(1)
    else:
        print(f"\nPASS: overall score {avg_overall:.4f} >= threshold {args.threshold}")


if __name__ == "__main__":
    main()
