"""Tests for the Model Judge system."""

import json
import os
import tempfile
import pytest
from core.model_judge import ModelJudge, _heuristic_score


# ── Heuristic Scorer Tests ────────────────────────────────────────────────

class TestHeuristicScore:
    """Test the fast heuristic scoring function."""

    def test_basic_good_output(self):
        result = _heuristic_score(
            task_type="research_synthesis",
            prompt="Summarize the key findings of the AI safety paper.",
            output="## Key Findings\n\n- The paper identifies three main risks...\n- Mitigation strategies include...\n- The authors recommend a phased approach to deployment.\n\nOverall, the paper provides a comprehensive framework for evaluating AI safety in production systems.",
            model="claude-sonnet-4-6",
        )
        assert "scores" in result
        assert "total" in result
        assert result["total"] >= 50  # should be decent
        assert result["method"] == "heuristic"

    def test_empty_output_scores_low(self):
        result = _heuristic_score(
            task_type="planning",
            prompt="Create a project plan for the new feature.",
            output="",
            model="claude-sonnet-4-6",
        )
        assert result["total"] < 40  # empty output should score poorly

    def test_very_short_output_penalized(self):
        result = _heuristic_score(
            task_type="research_synthesis",
            prompt="Analyze the market opportunity for this product.",
            output="OK",
            model="claude-haiku-4-5-20251001",
        )
        assert result["scores"]["coherence"] < 50
        assert result["scores"]["completeness"] < 30

    def test_repetitive_output_penalized(self):
        repeated = "This is the same sentence repeated. " * 20
        result = _heuristic_score(
            task_type="planning",
            prompt="Create a detailed plan.",
            output=repeated,
            model="qwen2.5:7b",
        )
        assert result["scores"]["coherence"] < 60

    def test_failure_patterns_lower_relevance(self):
        result = _heuristic_score(
            task_type="execution",
            prompt="Generate the report.",
            output="I apologize, but I cannot help with that. As an AI, I'm unable to access the database.",
            model="gpt-4o",
        )
        assert result["scores"]["relevance"] < 50

    def test_secret_leak_lowers_canon_score(self):
        result = _heuristic_score(
            task_type="execution",
            prompt="Show the configuration.",
            output="Here's the config: api_key=sk-abc123 and password=secret123",
            model="claude-sonnet-4-6",
        )
        assert result["scores"]["canon_compliance"] < 50

    def test_classification_penalizes_verbose(self):
        """Verbose classification output should be penalized on completeness."""
        verbose = _heuristic_score(
            task_type="classification",
            prompt="Classify this ticket: 'My login doesn't work'",
            output="Category: Authentication\nPriority: High\n\n" + "Additional analysis padding text here. " * 30,
            model="claude-haiku-4-5-20251001",
        )
        # Verbose classification should get a completeness penalty
        assert verbose["scores"]["completeness"] < 80

    def test_all_dimensions_present(self):
        result = _heuristic_score(
            task_type="default",
            prompt="Hello",
            output="Hello! How can I help you today?",
            model="claude-sonnet-4-6",
        )
        for dim in ["coherence", "completeness", "relevance", "conciseness", "canon_compliance"]:
            assert dim in result["scores"]
            assert 0 <= result["scores"][dim] <= 100

    def test_total_is_weighted_average(self):
        result = _heuristic_score(
            task_type="default",
            prompt="Test prompt for scoring",
            output="A reasonably complete and coherent response to the test prompt.",
            model="claude-sonnet-4-6",
        )
        # Verify total is between 0 and 100
        assert 0 <= result["total"] <= 100


# ── ModelJudge Class Tests ────────────────────────────────────────────────

class TestModelJudge:
    """Test the ModelJudge class."""

    @pytest.fixture
    def judge(self, tmp_path):
        return ModelJudge(
            log_path=str(tmp_path / "judge_scores.jsonl"),
            summary_path=str(tmp_path / "judge_summary.json"),
        )

    def test_evaluate_returns_entry(self, judge):
        entry = judge.evaluate(
            task_type="research_synthesis",
            prompt="Summarize the paper.",
            output="## Summary\n\nThe paper covers three main areas...",
            model="claude-sonnet-4-6",
            provider="anthropic",
            cost_usd=0.003,
        )
        assert entry["model"] == "claude-sonnet-4-6"
        assert entry["task_type"] == "research_synthesis"
        assert "total_score" in entry
        assert "quality_per_dollar" in entry
        assert entry["cost_usd"] == 0.003

    def test_evaluate_logs_to_file(self, judge):
        judge.evaluate(
            task_type="planning",
            prompt="Create a plan.",
            output="## Plan\n\n1. First step\n2. Second step",
            model="claude-sonnet-4-6",
        )
        assert judge.log_path.exists()
        with open(judge.log_path) as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["model"] == "claude-sonnet-4-6"

    def test_get_scores_empty(self, judge):
        scores = judge.get_scores()
        assert scores == []

    def test_get_scores_with_data(self, judge):
        for i in range(5):
            judge.evaluate(
                task_type="execution",
                prompt=f"Task {i}",
                output=f"Result for task {i} with enough content to score well.",
                model="claude-sonnet-4-6",
                cost_usd=0.002,
            )
        scores = judge.get_scores()
        assert len(scores) == 5

    def test_get_scores_filter_by_model(self, judge):
        judge.evaluate(task_type="planning", prompt="p", output="output a with content", model="model-a")
        judge.evaluate(task_type="planning", prompt="p", output="output b with content", model="model-b")
        judge.evaluate(task_type="planning", prompt="p", output="output c with content", model="model-a")

        scores_a = judge.get_scores(model="model-a")
        assert len(scores_a) == 2

    def test_get_scores_filter_by_task(self, judge):
        judge.evaluate(task_type="planning", prompt="p", output="output planning", model="m")
        judge.evaluate(task_type="execution", prompt="p", output="output execution", model="m")

        scores = judge.get_scores(task_type="planning")
        assert len(scores) == 1

    def test_performance_report_empty(self, judge):
        report = judge.get_performance_report()
        assert report["total_evaluations"] == 0

    def test_performance_report_with_data(self, judge):
        models = ["claude-sonnet-4-6", "qwen2.5:7b"]
        tasks = ["planning", "execution", "classification"]
        for model in models:
            for task in tasks:
                for i in range(4):
                    judge.evaluate(
                        task_type=task,
                        prompt=f"Do {task} number {i}",
                        output=f"## Result\n\nHere is the {task} result number {i} with enough detail to score well on the heuristic evaluation system.",
                        model=model,
                        cost_usd=0.003 if "claude" in model else 0.0,
                    )
        report = judge.get_performance_report()
        assert report["total_evaluations"] == 24
        assert "claude-sonnet-4-6" in report["models"]
        assert "qwen2.5:7b" in report["models"]
        assert "planning" in report["task_types"]

    def test_performance_report_saves_summary(self, judge):
        judge.evaluate(task_type="planning", prompt="p", output="good output with content", model="m", cost_usd=0.001)
        judge.get_performance_report()
        assert judge.summary_path.exists()

    def test_recommend_model_no_data(self, judge):
        rec = judge.recommend_model(task_type="planning")
        assert rec["recommendation"] is None
        assert rec["confidence"] == "none"

    def test_recommend_model_with_data(self, judge):
        # Add enough evaluations
        for i in range(5):
            judge.evaluate(
                task_type="planning",
                prompt=f"Plan task {i} with reasonable detail",
                output=f"## Plan\n\n1. Step one for task {i}\n2. Step two\n3. Step three with good detail and reasoning.",
                model="good-model",
                cost_usd=0.005,
            )
            judge.evaluate(
                task_type="planning",
                prompt=f"Plan task {i}",
                output="ok",  # bad output
                model="bad-model",
                cost_usd=0.01,
            )
        rec = judge.recommend_model(task_type="planning", min_evaluations=3)
        assert rec["recommendation"] == "good-model"

    def test_quality_per_dollar_free_model(self, judge):
        entry = judge.evaluate(
            task_type="classification",
            prompt="Classify this",
            output="Category: Tech\nPriority: Medium",
            model="qwen2.5:3b",
            cost_usd=0.0,
        )
        assert entry["quality_per_dollar"] == "free"

    def test_get_model_ranking(self, judge):
        for i in range(5):
            judge.evaluate(
                task_type="execution",
                prompt=f"Execute task {i} with detailed requirements",
                output=f"## Execution Result {i}\n\nCompleted with detailed output and proper formatting. The task involved multiple steps.",
                model="expensive-model",
                cost_usd=0.05,
            )
            judge.evaluate(
                task_type="execution",
                prompt=f"Execute task {i} with detailed requirements",
                output=f"## Execution Result {i}\n\nCompleted with similar quality output and proper formatting. Multiple steps handled well.",
                model="cheap-model",
                cost_usd=0.001,
            )
        rankings = judge.get_model_ranking()
        assert len(rankings) == 2
        # Cheap model should rank higher on quality-per-dollar
        assert rankings[0]["model"] == "cheap-model"
