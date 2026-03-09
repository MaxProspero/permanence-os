#!/usr/bin/env python3
"""
Permanence OS — Model Judge System

Evaluates model output quality and automatically adjusts routing.
Uses a cheap/local model to judge expensive outputs, building a quality
profile per model over time. Routes future tasks to the best
quality-per-dollar model.

Flow:
  1. Task comes in → ModelRouter picks a model
  2. Model produces output → ModelJudge scores it (0-100)
  3. Scores logged to judge_scores.jsonl
  4. Over time, routing adapts: cheap models that score well get promoted,
     expensive models that score poorly get demoted

Judge criteria:
  - Coherence: Is the output logically consistent?
  - Completeness: Does it address the full task?
  - Relevance: Is it on-topic and useful?
  - Conciseness: Is it appropriately brief vs. verbose?
  - Canon compliance: Does it follow governance rules?

Usage:
  from core.model_judge import ModelJudge
  judge = ModelJudge()

  # Score a completed task
  score = judge.evaluate(task_type="research_synthesis", prompt="...", output="...", model="claude-sonnet-4-6")

  # Get model performance report
  report = judge.get_performance_report()

  # Get recommended model for a task
  recommendation = judge.recommend_model(task_type="planning")
"""

from __future__ import annotations

import json
import os
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_JUDGE_LOG = os.path.join(BASE_DIR, "logs", "judge_scores.jsonl")
DEFAULT_JUDGE_SUMMARY = os.path.join(BASE_DIR, "logs", "judge_model_summary.json")

# ── Scoring rubric ────────────────────────────────────────────────────────

SCORING_DIMENSIONS = {
    "coherence": {
        "weight": 0.25,
        "description": "Logical consistency and flow of reasoning",
    },
    "completeness": {
        "weight": 0.25,
        "description": "Addresses the full scope of the task",
    },
    "relevance": {
        "weight": 0.20,
        "description": "On-topic and useful for the stated purpose",
    },
    "conciseness": {
        "weight": 0.15,
        "description": "Appropriately brief — not padded, not truncated",
    },
    "canon_compliance": {
        "weight": 0.15,
        "description": "Follows governance rules and safety constraints",
    },
}

# Heuristic scoring thresholds (no LLM needed for basic quality signals)
MIN_USEFUL_OUTPUT_LENGTH = 50  # chars — below this is probably a failure
MAX_REASONABLE_OUTPUT_LENGTH = 50000  # chars — above this is probably rambling
IDEAL_OUTPUT_RATIO = 0.15  # ideal output/input ratio for most tasks


# ── Heuristic scorer (fast, free) ─────────────────────────────────────────

def _heuristic_score(
    task_type: str,
    prompt: str,
    output: str,
    model: str,
) -> Dict[str, Any]:
    """
    Fast heuristic scoring — no LLM call needed.
    Returns scores (0-100) for each dimension plus a weighted total.
    Good enough for 80% of routing decisions.
    """
    scores: Dict[str, float] = {}
    output_len = len(output.strip())
    prompt_len = max(1, len(prompt.strip()))

    # ── Coherence: check for structure signals ──
    coherence = 60.0  # baseline
    # Structured output (headers, lists, code blocks) = more coherent
    if any(marker in output for marker in ["## ", "- ", "1. ", "```", "**"]):
        coherence += 15
    # Very short outputs are less likely coherent
    if output_len < MIN_USEFUL_OUTPUT_LENGTH:
        coherence -= 30
    # Check for repetition (sign of degeneration)
    sentences = [s.strip() for s in output.split(".") if len(s.strip()) > 20]
    if len(sentences) > 3:
        unique_ratio = len(set(sentences)) / len(sentences)
        if unique_ratio < 0.5:
            coherence -= 25  # high repetition
        elif unique_ratio > 0.9:
            coherence += 10  # diverse content
    scores["coherence"] = max(0, min(100, coherence))

    # ── Completeness: output length relative to task complexity ──
    completeness = 50.0
    if output_len < MIN_USEFUL_OUTPUT_LENGTH:
        completeness = 10.0  # almost certainly incomplete
    elif output_len > prompt_len * 0.3:
        completeness = 70.0  # reasonable response
    if output_len > prompt_len * 0.5:
        completeness += 15
    # Task-specific expectations
    if task_type in ("research_synthesis", "strategy", "planning"):
        if output_len > 500:
            completeness += 10
    elif task_type in ("classification", "tagging"):
        # Brief outputs are preferred for classification tasks
        if output_len < 200:
            completeness += 15
        if output_len > 500:
            completeness -= 15  # penalize verbose classification
    scores["completeness"] = max(0, min(100, completeness))

    # ── Relevance: keyword overlap with prompt ──
    relevance = 50.0
    prompt_words = set(prompt.lower().split())
    output_words = set(output.lower().split())
    if prompt_words:
        overlap = len(prompt_words & output_words) / len(prompt_words)
        relevance = 30 + (overlap * 60)  # 30-90 range
    # Penalize if output contains common failure patterns
    failure_patterns = [
        "I cannot", "I'm unable", "I don't have access",
        "As an AI", "I apologize", "Error:", "exception",
    ]
    failure_count = sum(1 for p in failure_patterns if p.lower() in output.lower())
    relevance -= failure_count * 10
    scores["relevance"] = max(0, min(100, relevance))

    # ── Conciseness: not too short, not too long ──
    conciseness = 60.0
    ratio = output_len / prompt_len if prompt_len > 0 else 1.0
    if ratio < 0.05:
        conciseness = 20  # way too short
    elif ratio > 5.0:
        conciseness = 30  # way too long
    elif 0.1 <= ratio <= 2.0:
        conciseness = 80  # sweet spot
    scores["conciseness"] = max(0, min(100, conciseness))

    # ── Canon compliance: check for governance markers ──
    canon_score = 80.0  # assume compliant unless red flags
    # Red flags: leaked secrets, unauthorized actions
    secret_patterns = ["sk-", "api_key=", "token=", "password=", "secret="]
    if any(p in output.lower() for p in secret_patterns):
        canon_score -= 40
    # Check for appropriate caveats on high-risk tasks
    if task_type in ("strategy", "canon_interpretation"):
        if any(w in output.lower() for w in ["recommend", "suggest", "consider"]):
            canon_score += 10  # advisory language = good
    scores["canon_compliance"] = max(0, min(100, canon_score))

    # ── Weighted total ──
    total = sum(
        scores[dim] * SCORING_DIMENSIONS[dim]["weight"]
        for dim in SCORING_DIMENSIONS
    )

    return {
        "scores": {dim: round(scores[dim], 1) for dim in SCORING_DIMENSIONS},
        "total": round(total, 1),
        "method": "heuristic",
    }


# ── Model Judge class ─────────────────────────────────────────────────────

class ModelJudge:
    """
    Evaluates model output quality and tracks performance over time.
    Provides routing recommendations based on quality-per-dollar.
    """

    def __init__(
        self,
        log_path: Optional[str] = None,
        summary_path: Optional[str] = None,
    ):
        self.log_path = Path(log_path or os.getenv("PERMANENCE_JUDGE_LOG", DEFAULT_JUDGE_LOG))
        self.summary_path = Path(summary_path or os.getenv("PERMANENCE_JUDGE_SUMMARY", DEFAULT_JUDGE_SUMMARY))
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.summary_path.parent.mkdir(parents=True, exist_ok=True)

    def evaluate(
        self,
        task_type: str,
        prompt: str,
        output: str,
        model: str,
        provider: str = "",
        cost_usd: float = 0.0,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a model's output. Returns score dict with total 0-100.
        Automatically logs the evaluation.
        """
        result = _heuristic_score(
            task_type=task_type,
            prompt=prompt,
            output=output,
            model=model,
        )

        # Calculate quality-per-dollar
        qpd = (result["total"] / max(0.0001, cost_usd)) if cost_usd > 0 else float("inf")

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_type": task_type,
            "model": model,
            "provider": provider,
            "cost_usd": round(cost_usd, 6),
            "prompt_length": len(prompt),
            "output_length": len(output),
            "scores": result["scores"],
            "total_score": result["total"],
            "quality_per_dollar": round(qpd, 2) if qpd != float("inf") else "free",
            "method": result["method"],
            **(context or {}),
        }

        # Append to log
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass

        return entry

    def get_scores(
        self,
        model: Optional[str] = None,
        task_type: Optional[str] = None,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Load judge scores, optionally filtered by model/task/date."""
        if not self.log_path.exists():
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        results: List[Dict[str, Any]] = []

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(entry, dict):
                        continue

                    # Date filter
                    ts = entry.get("timestamp", "")
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass

                    # Model filter
                    if model and entry.get("model") != model:
                        continue

                    # Task filter
                    if task_type and entry.get("task_type") != task_type:
                        continue

                    results.append(entry)
        except OSError:
            pass

        return results

    def get_performance_report(self, days: int = 30) -> Dict[str, Any]:
        """
        Generate a performance report: average scores per model per task type.
        Used by the routing system to make smarter decisions.
        """
        scores = self.get_scores(days=days)
        if not scores:
            return {"models": {}, "task_types": {}, "total_evaluations": 0}

        # Aggregate by model
        by_model: Dict[str, List[float]] = {}
        by_model_task: Dict[str, Dict[str, List[float]]] = {}
        by_task: Dict[str, List[float]] = {}
        cost_by_model: Dict[str, List[float]] = {}

        for entry in scores:
            model = entry.get("model", "unknown")
            task = entry.get("task_type", "unknown")
            total = float(entry.get("total_score", 0))
            cost = float(entry.get("cost_usd", 0))

            by_model.setdefault(model, []).append(total)
            by_model_task.setdefault(model, {}).setdefault(task, []).append(total)
            by_task.setdefault(task, []).append(total)
            cost_by_model.setdefault(model, []).append(cost)

        # Build model summaries
        model_summaries: Dict[str, Dict[str, Any]] = {}
        for model, totals in by_model.items():
            avg_score = statistics.mean(totals)
            total_cost = sum(cost_by_model.get(model, []))
            avg_cost = statistics.mean(cost_by_model.get(model, [])) if cost_by_model.get(model) else 0

            task_breakdown = {}
            for task, task_totals in by_model_task.get(model, {}).items():
                task_breakdown[task] = {
                    "avg_score": round(statistics.mean(task_totals), 1),
                    "count": len(task_totals),
                    "min": round(min(task_totals), 1),
                    "max": round(max(task_totals), 1),
                }

            model_summaries[model] = {
                "avg_score": round(avg_score, 1),
                "total_evaluations": len(totals),
                "total_cost_usd": round(total_cost, 4),
                "avg_cost_per_call_usd": round(avg_cost, 6),
                "quality_per_dollar": round(avg_score / max(0.0001, avg_cost), 1) if avg_cost > 0 else "free",
                "task_breakdown": task_breakdown,
            }

        # Build task summaries
        task_summaries: Dict[str, Dict[str, Any]] = {}
        for task, totals in by_task.items():
            # Find best model for this task
            best_model = ""
            best_score = 0.0
            for model, model_tasks in by_model_task.items():
                if task in model_tasks:
                    avg = statistics.mean(model_tasks[task])
                    if avg > best_score:
                        best_score = avg
                        best_model = model

            task_summaries[task] = {
                "avg_score": round(statistics.mean(totals), 1),
                "count": len(totals),
                "best_model": best_model,
                "best_score": round(best_score, 1),
            }

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": days,
            "total_evaluations": len(scores),
            "models": model_summaries,
            "task_types": task_summaries,
        }

        # Save summary
        try:
            with open(self.summary_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        except OSError:
            pass

        return report

    def recommend_model(
        self,
        task_type: str,
        candidates: Optional[List[str]] = None,
        days: int = 30,
        min_evaluations: int = 3,
    ) -> Dict[str, Any]:
        """
        Recommend the best model for a task type based on historical quality scores.
        Returns the recommendation with confidence level.

        Balances quality and cost:
        - High-stakes tasks (opus tier): prioritize quality
        - Medium tasks (sonnet tier): balance quality and cost
        - Low-stakes tasks (haiku tier): prioritize cost-efficiency
        """
        from core.model_router import TASKS_OPUS, TASKS_HAIKU

        scores = self.get_scores(task_type=task_type, days=days)
        if not scores:
            return {
                "task_type": task_type,
                "recommendation": None,
                "confidence": "none",
                "reason": "No evaluation data available",
            }

        # Aggregate by model
        model_scores: Dict[str, List[float]] = {}
        model_costs: Dict[str, List[float]] = {}
        for entry in scores:
            model = entry.get("model", "")
            if candidates and model not in candidates:
                continue
            model_scores.setdefault(model, []).append(float(entry.get("total_score", 0)))
            model_costs.setdefault(model, []).append(float(entry.get("cost_usd", 0)))

        # Filter models with enough data
        eligible: Dict[str, Dict[str, float]] = {}
        for model, totals in model_scores.items():
            if len(totals) < min_evaluations:
                continue
            avg_score = statistics.mean(totals)
            avg_cost = statistics.mean(model_costs.get(model, [0]))

            # Calculate composite score based on task tier
            if task_type in TASKS_OPUS:
                # High-stakes: 80% quality, 20% cost
                composite = avg_score * 0.8 + (100 - avg_cost * 1000) * 0.2
            elif task_type in TASKS_HAIKU:
                # Low-stakes: 40% quality, 60% cost
                composite = avg_score * 0.4 + (100 - avg_cost * 1000) * 0.6
            else:
                # Medium: 60% quality, 40% cost
                composite = avg_score * 0.6 + (100 - avg_cost * 1000) * 0.4

            eligible[model] = {
                "avg_score": round(avg_score, 1),
                "avg_cost": round(avg_cost, 6),
                "composite": round(composite, 1),
                "evaluations": len(totals),
            }

        if not eligible:
            return {
                "task_type": task_type,
                "recommendation": None,
                "confidence": "low",
                "reason": f"Not enough evaluations (need {min_evaluations}+)",
                "models_seen": list(model_scores.keys()),
            }

        # Pick the best composite score
        best_model = max(eligible, key=lambda m: eligible[m]["composite"])
        best_data = eligible[best_model]

        # Confidence based on evaluation count
        confidence = "low"
        if best_data["evaluations"] >= 20:
            confidence = "high"
        elif best_data["evaluations"] >= 10:
            confidence = "medium"

        return {
            "task_type": task_type,
            "recommendation": best_model,
            "confidence": confidence,
            "avg_score": best_data["avg_score"],
            "avg_cost": best_data["avg_cost"],
            "composite": best_data["composite"],
            "evaluations": best_data["evaluations"],
            "all_candidates": eligible,
        }

    def get_model_ranking(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Rank all models by overall quality-per-dollar.
        Returns sorted list from best to worst value.
        """
        report = self.get_performance_report(days=days)
        rankings = []
        for model, data in report.get("models", {}).items():
            qpd = data.get("quality_per_dollar", 0)
            rankings.append({
                "model": model,
                "avg_score": data.get("avg_score", 0),
                "total_cost": data.get("total_cost_usd", 0),
                "quality_per_dollar": qpd if qpd != "free" else 999999,
                "evaluations": data.get("total_evaluations", 0),
            })
        rankings.sort(key=lambda x: x["quality_per_dollar"], reverse=True)
        return rankings
