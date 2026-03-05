#!/usr/bin/env python3
"""
Run lightweight offline simulations for Ophtxn memory and habit behavior.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts import telegram_control as tg


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_retrieval_trials(rng: random.Random, trials: int = 120) -> dict[str, Any]:
    notes = [
        {"text": "Prioritize deep work blocks from 8am to 11am.", "source": "manual", "timestamp": _now_iso()},
        {"text": "Use concise checklists for launch prep.", "source": "manual", "timestamp": _now_iso()},
        {"text": "When stressed, reduce scope and keep shipping.", "source": "manual", "timestamp": _now_iso()},
        {"text": "Best outreach tone is direct and respectful.", "source": "manual", "timestamp": _now_iso()},
        {"text": "Avoid context switching during revenue sprints.", "source": "manual", "timestamp": _now_iso()},
        {"text": "Night routine: review wins and set top 3 for tomorrow.", "source": "manual", "timestamp": _now_iso()},
    ]
    queries = [
        ("deep focus morning plan", "deep work blocks"),
        ("how should i do outreach today", "outreach tone"),
        ("i keep switching tasks", "context switching"),
        ("what to do under stress", "reduce scope"),
        ("how do i close day", "night routine"),
        ("how do i prep launch", "launch prep"),
    ]
    top1_hits = 0
    top3_hits = 0
    for _ in range(max(1, int(trials))):
        query, expected = rng.choice(queries)
        selected = tg._select_memory_notes(notes, query=query, limit=3)
        texts = [str(row.get("text") or "").lower() for row in selected]
        if texts and expected in texts[0]:
            top1_hits += 1
        if any(expected in row for row in texts[:3]):
            top3_hits += 1
    count = max(1, int(trials))
    return {
        "trials": count,
        "top1_hit_rate": round(float(top1_hits) / float(count), 4),
        "top3_hit_rate": round(float(top3_hits) / float(count), 4),
    }


def _habit_streak_trials(rng: random.Random, days: int = 60) -> dict[str, Any]:
    store = {"profiles": {}, "updated_at": ""}
    key = "user:simulation"
    profile = tg._memory_profile(store, key)
    ok, _msg = tg._habit_add(profile, "daily planning")
    if not ok:
        raise RuntimeError("failed to initialize habit simulation")
    # Simulate adherence with controlled misses to validate non-zero streak behavior.
    performed_days = 0
    miss_days = 0
    current_streak = 0
    best_streak = 0
    start_ordinal = datetime(2026, 1, 1, tzinfo=timezone.utc).date().toordinal()
    for day_idx in range(max(1, int(days))):
        did = rng.random() < 0.78
        if not did:
            miss_days += 1
            current_streak = 0
            continue
        current_date = datetime.fromordinal(start_ordinal + day_idx).date().isoformat()
        changed, _summary = tg._habit_mark_done(profile, "daily planning", today_iso=current_date)
        if changed:
            performed_days += 1
        current_streak += 1
        best_streak = max(best_streak, current_streak)
    habits = tg._memory_habits(profile)
    status = habits[0] if habits else {}
    return {
        "days": max(1, int(days)),
        "performed_days": performed_days,
        "miss_days": miss_days,
        "expected_best_streak": best_streak,
        "tracked_streak": int(status.get("streak") or 0),
        "tracked_best_streak": int(status.get("best_streak") or 0),
        "tracked_total_checkins": int(status.get("total_checkins") or 0),
    }


def _profile_history_conflict_trials() -> dict[str, Any]:
    store = {"profiles": {}, "updated_at": ""}
    key = "user:profile-simulation"
    profile = tg._memory_profile(store, key)
    tg._profile_set_field(profile, field_alias="goals", value="Ship daily")
    tg._profile_set_field(profile, field_alias="goals", value="Ship weekly")
    tg._profile_set_field(profile, field_alias="work-style", value="Focused deep blocks")
    tg._profile_set_field(profile, field_alias="work-style", value="Fast sprints")
    history = tg._profile_history_rows(profile)
    conflicts = tg._profile_conflict_rows(profile)
    open_conflicts = [
        row for row in conflicts
        if str(row.get("status") or "").strip().lower() != "resolved"
    ]
    return {
        "history_rows": len(history),
        "conflict_rows": len(conflicts),
        "open_conflicts": len(open_conflicts),
    }


def _habit_nudge_trials() -> dict[str, Any]:
    store = {"profiles": {}, "updated_at": ""}
    key = "user:nudge-simulation"
    profile = tg._memory_profile(store, key)
    tg._habit_add(profile, "daily planning | cue: after coffee | plan: If it is 8am, set top 3 tasks.")
    tg._habit_add(profile, "evening review | cue: after dinner | plan: If it is 9pm, close loop.")
    tg._habit_mark_done(profile, "daily planning", today_iso="2026-03-04")
    nudge_text = tg._habit_nudge_text(profile, prefix="/")
    return {
        "contains_cue": "cue=" in nudge_text,
        "contains_next_action": "next=" in nudge_text,
        "line_count": len([line for line in nudge_text.splitlines() if line.strip().startswith("- ")]),
    }


def _write_report(payload: dict[str, Any]) -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    out_dir = base_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"ophtxn_simulation_{stamp}.md"
    lines = [
        "# Ophtxn Simulation",
        "",
        f"Generated (UTC): {payload.get('generated_at')}",
        "",
        "## Memory Retrieval",
        f"- Trials: {payload['memory_retrieval']['trials']}",
        f"- Top1 hit rate: {payload['memory_retrieval']['top1_hit_rate']}",
        f"- Top3 hit rate: {payload['memory_retrieval']['top3_hit_rate']}",
        "",
        "## Habit Simulation",
        f"- Days simulated: {payload['habit_simulation']['days']}",
        f"- Performed days: {payload['habit_simulation']['performed_days']}",
        f"- Miss days: {payload['habit_simulation']['miss_days']}",
        f"- Expected best streak (sim model): {payload['habit_simulation']['expected_best_streak']}",
        f"- Tracked streak (engine): {payload['habit_simulation']['tracked_streak']}",
        f"- Tracked best streak (engine): {payload['habit_simulation']['tracked_best_streak']}",
        f"- Tracked total checkins: {payload['habit_simulation']['tracked_total_checkins']}",
        "",
        "## Profile Consistency",
        f"- Profile history rows: {payload['profile_consistency']['history_rows']}",
        f"- Profile conflict rows: {payload['profile_consistency']['conflict_rows']}",
        f"- Open profile conflicts: {payload['profile_consistency']['open_conflicts']}",
        "",
        "## Habit Nudges",
        f"- Contains cue hints: {payload['habit_nudges']['contains_cue']}",
        f"- Contains next-action hints: {payload['habit_nudges']['contains_next_action']}",
        f"- Nudge line count: {payload['habit_nudges']['line_count']}",
        "",
        "## Notes",
        "- This simulation is deterministic with the provided seed and intended as a regression signal.",
        "- Use alongside unit tests, not as a substitute for live conversation evaluations.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    latest = out_dir / "ophtxn_simulation_latest.md"
    latest.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Ophtxn offline simulations.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for reproducibility")
    parser.add_argument("--memory-trials", type=int, default=120, help="Number of memory retrieval trials")
    parser.add_argument("--habit-days", type=int, default=60, help="Number of simulated habit days")
    args = parser.parse_args(argv)

    rng = random.Random(int(args.seed))
    payload = {
        "generated_at": _now_iso(),
        "seed": int(args.seed),
        "memory_retrieval": _memory_retrieval_trials(rng, trials=max(1, int(args.memory_trials))),
        "habit_simulation": _habit_streak_trials(rng, days=max(1, int(args.habit_days))),
        "profile_consistency": _profile_history_conflict_trials(),
        "habit_nudges": _habit_nudge_trials(),
    }
    report_path = _write_report(payload)
    print(f"Ophtxn simulation report: {report_path}")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
