"""Tests for scripts/content_generator.py -- Content generation pipeline."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import content_generator as cg


# ---------------------------------------------------------------------------
# Voice compliance
# ---------------------------------------------------------------------------

class TestVoiceCompliance:
    def test_clean_text_passes(self):
        violations = cg.check_voice_compliance(
            "This works because governance prevents drift. "
            "The constraint is trust at scale."
        )
        assert violations == []

    def test_hype_language_flagged(self):
        violations = cg.check_voice_compliance(
            "This is an amazing and incredible product."
        )
        assert len(violations) >= 1
        rules = [v["rule"] for v in violations]
        assert "Hype language" in rules

    def test_multiple_exclamation_flagged(self):
        violations = cg.check_voice_compliance("This is great!!! So good!!!")
        rules = [v["rule"] for v in violations]
        assert "Multiple exclamation marks" in rules

    def test_hedging_flagged(self):
        violations = cg.check_voice_compliance(
            "I think maybe this could possibly be useful."
        )
        rules = [v["rule"] for v in violations]
        assert "Excessive hedging" in rules

    def test_cheerleading_flagged(self):
        violations = cg.check_voice_compliance("We are crushing it and killing it!")
        rules = [v["rule"] for v in violations]
        assert "Cheerleading" in rules

    def test_apologizing_flagged(self):
        violations = cg.check_voice_compliance(
            "Sorry but I need to say this is important."
        )
        rules = [v["rule"] for v in violations]
        assert "Apologizing for substance" in rules

    def test_preferred_constructions_pass(self):
        texts = [
            "This works because the architecture separates concerns.",
            "The constraint is latency under load.",
            "Pattern: failures cluster when governance is absent.",
            "Trade-off: gain speed, lose auditability.",
            "Failure mode: silent drift without checkpoints.",
            "Under these conditions, the system self-corrects.",
        ]
        for text in texts:
            assert cg.check_voice_compliance(text) == [], f"Failed: {text}"


# ---------------------------------------------------------------------------
# Thread generation
# ---------------------------------------------------------------------------

class TestThreadGeneration:
    def test_basic_thread_structure(self):
        result = cg.generate_thread(
            topic="AI Governance",
            points=["Point one.", "Point two.", "Point three."],
            hook="Why governance matters:",
        )
        assert result["platform"] == "x"
        assert result["content_type"] == "thread"
        assert result["segment_count"] >= 5  # hook + 3 points + CTA
        assert isinstance(result["segments"], list)
        assert "generated_at" in result

    def test_thread_segments_under_280(self):
        result = cg.generate_thread(
            topic="Test",
            points=["A" * 300, "B" * 250, "Short point."],
        )
        for seg in result["segments"]:
            assert len(seg) <= 280, f"Segment too long: {len(seg)} chars"

    def test_thread_with_custom_cta(self):
        result = cg.generate_thread(
            topic="Test",
            points=["Point."],
            cta="Follow for more.",
        )
        assert result["segments"][-1] == "Follow for more."

    def test_thread_voice_check_included(self):
        result = cg.generate_thread(
            topic="Test",
            points=["This works because it is governed."],
        )
        assert "voice_violations" in result
        assert "voice_compliant" in result

    def test_thread_source_urls(self):
        result = cg.generate_thread(
            topic="Test",
            points=["Point."],
            source_urls=["https://example.com"],
        )
        assert result["source_urls"] == ["https://example.com"]

    def test_empty_points_still_has_hook_and_cta(self):
        result = cg.generate_thread(topic="Test", points=[])
        assert result["segment_count"] >= 2  # hook + CTA


# ---------------------------------------------------------------------------
# Newsletter generation
# ---------------------------------------------------------------------------

class TestNewsletterGeneration:
    def test_basic_newsletter_structure(self):
        result = cg.generate_newsletter_issue(
            issue_number=1,
            title="Test Issue",
            sections=[
                {"heading": "Section 1", "body": "Content here.", "links": []},
                {"heading": "Section 2", "body": "More content.", "links": ["https://example.com"]},
            ],
        )
        assert result["platform"] == "newsletter"
        assert result["content_type"] == "newsletter_issue"
        assert result["issue_number"] == 1
        assert result["section_count"] == 2
        assert "Dark Horse Intelligence" in result["markdown"]
        assert "Section 1" in result["markdown"]
        assert result["word_count"] > 0

    def test_newsletter_with_intro_outro(self):
        result = cg.generate_newsletter_issue(
            issue_number=2,
            title="Custom",
            sections=[{"heading": "A", "body": "B"}],
            intro="Welcome to the briefing.",
            outro="Until next time.",
        )
        assert "Welcome to the briefing." in result["markdown"]
        assert "Until next time." in result["markdown"]

    def test_newsletter_default_outro(self):
        result = cg.generate_newsletter_issue(
            issue_number=3,
            title="Defaults",
            sections=[{"heading": "A", "body": "B"}],
        )
        assert "Kael Dax" in result["markdown"]


# ---------------------------------------------------------------------------
# LinkedIn post
# ---------------------------------------------------------------------------

class TestLinkedInPost:
    def test_basic_post(self):
        result = cg.generate_linkedin_post(
            topic="AI Governance",
            body="The constraint is trust. Every AI system needs it.",
        )
        assert result["platform"] == "linkedin"
        assert result["content_type"] == "post"
        assert result["char_count"] > 0
        assert result["char_count"] <= 1300

    def test_post_with_hashtags(self):
        result = cg.generate_linkedin_post(
            topic="Test",
            body="Short post.",
            hashtags=["AI", "Governance"],
        )
        assert "#AI" in result["content"]
        assert "#Governance" in result["content"]

    def test_long_post_trimmed(self):
        result = cg.generate_linkedin_post(
            topic="Test",
            body="A" * 1400,
        )
        assert result["char_count"] <= 1300


# ---------------------------------------------------------------------------
# Short-form script
# ---------------------------------------------------------------------------

class TestShortScript:
    def test_basic_script(self):
        result = cg.generate_short_script(
            topic="AI Trust",
            hook="Here is what nobody tells you about AI.",
            body="The systems that ask permission are the ones that scale.",
            cta="Follow for more.",
        )
        assert result["platform"] == "tiktok"
        assert result["content_type"] == "tiktok_script"
        assert result["word_count"] > 0
        assert result["est_duration_seconds"] > 0
        assert result["duration_target"] == 60

    def test_script_over_target_flagged(self):
        result = cg.generate_short_script(
            topic="Long",
            hook="Hook.",
            body=" ".join(["word"] * 200),  # ~200 words = ~80 seconds
            duration_target=60,
        )
        assert result["over_target"] is True

    def test_script_under_target_ok(self):
        result = cg.generate_short_script(
            topic="Short",
            hook="Quick hook.",
            body="Brief point.",
            duration_target=60,
        )
        assert result["over_target"] is False


# ---------------------------------------------------------------------------
# Theme extraction
# ---------------------------------------------------------------------------

class TestThemeExtraction:
    def test_governance_theme_detected(self):
        bookmarks = [
            {"title": "AI Governance Framework", "text": "governance and safety", "topics": []},
        ]
        themed = cg.extract_themes(bookmarks)
        assert "ai_governance" in themed
        assert len(themed["ai_governance"]) == 1

    def test_multiple_themes(self):
        bookmarks = [
            {"title": "Agent Swarm", "text": "multi-agent orchestration", "topics": []},
            {"title": "Trading Bot", "text": "backtest smc strategy", "topics": []},
        ]
        themed = cg.extract_themes(bookmarks)
        assert "agent_systems" in themed
        assert "trading_intelligence" in themed

    def test_no_match_returns_empty(self):
        bookmarks = [
            {"title": "Cooking Recipe", "text": "pasta carbonara", "topics": []},
        ]
        themed = cg.extract_themes(bookmarks)
        assert themed == {}

    def test_bookmark_matches_multiple_themes(self):
        bookmarks = [
            {"title": "Governed Agent Trading System", "text": "governance agent trading", "topics": []},
        ]
        themed = cg.extract_themes(bookmarks)
        assert len(themed) >= 2  # Should match governance + agents + trading


# ---------------------------------------------------------------------------
# Bookmark loading
# ---------------------------------------------------------------------------

class TestBookmarkLoading:
    def test_load_from_jsonl(self, tmp_path):
        intake = tmp_path / "intake.jsonl"
        entries = [
            {"title": "Entry 1", "url": "https://example.com/1"},
            {"title": "Entry 2", "url": "https://example.com/2"},
        ]
        with open(intake, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        import content_generator as cg2
        original = cg2.BOOKMARK_INTAKE
        try:
            cg2.BOOKMARK_INTAKE = intake
            loaded = cg2.load_bookmarks(limit=10)
            assert len(loaded) == 2
            assert loaded[0]["title"] == "Entry 1"
        finally:
            cg2.BOOKMARK_INTAKE = original

    def test_load_respects_limit(self, tmp_path):
        intake = tmp_path / "intake.jsonl"
        with open(intake, "w") as f:
            for i in range(20):
                f.write(json.dumps({"title": f"Entry {i}"}) + "\n")

        original = cg.BOOKMARK_INTAKE
        try:
            cg.BOOKMARK_INTAKE = intake
            loaded = cg.load_bookmarks(limit=5)
            assert len(loaded) == 5
        finally:
            cg.BOOKMARK_INTAKE = original

    def test_load_handles_missing_file(self):
        from pathlib import Path
        original = cg.BOOKMARK_INTAKE
        try:
            cg.BOOKMARK_INTAKE = Path("/nonexistent/path/bookmarks.jsonl")
            loaded = cg.load_bookmarks()
            assert loaded == []
        finally:
            cg.BOOKMARK_INTAKE = original


# ---------------------------------------------------------------------------
# Bookmark-to-content pipeline
# ---------------------------------------------------------------------------

class TestBookmarkPipeline:
    @pytest.fixture
    def populated_intake(self, tmp_path):
        """Create a populated bookmark intake file."""
        intake = tmp_path / "intake.jsonl"
        bookmarks = [
            {"title": "AI Governance Report", "text": "governance safety compliance", "url": "https://a.com", "signal_score": 8, "topics": ["governance"]},
            {"title": "Agent Orchestration", "text": "multi-agent swarm system", "url": "https://b.com", "signal_score": 7, "topics": ["agents"]},
            {"title": "Trading Strategy", "text": "smc ict order blocks backtest", "url": "https://c.com", "signal_score": 9, "topics": ["trading"]},
            {"title": "Open Source Tools", "text": "github framework deploy stack", "url": "https://d.com", "signal_score": 6, "topics": ["open_source"]},
            {"title": "Privacy Framework", "text": "local self-hosted data sovereignty", "url": "https://e.com", "signal_score": 7, "topics": ["privacy"]},
        ]
        with open(intake, "w") as f:
            for bm in bookmarks:
                f.write(json.dumps(bm) + "\n")

        original = cg.BOOKMARK_INTAKE
        cg.BOOKMARK_INTAKE = intake
        yield intake
        cg.BOOKMARK_INTAKE = original

    def test_bookmarks_to_threads(self, populated_intake):
        threads = cg.bookmarks_to_threads(limit=3)
        assert len(threads) > 0
        assert len(threads) <= 3
        for t in threads:
            assert t["platform"] == "x"
            assert t["content_type"] == "thread"
            assert t["segment_count"] >= 2
            assert "theme_id" in t

    def test_bookmarks_to_newsletter(self, populated_intake):
        result = cg.bookmarks_to_newsletter(issue_number=1)
        assert "error" not in result
        assert result["platform"] == "newsletter"
        assert result["section_count"] > 0
        assert "Dark Horse Intelligence" in result["markdown"]


# ---------------------------------------------------------------------------
# Draft queue integration
# ---------------------------------------------------------------------------

class TestDraftQueueIntegration:
    def test_submit_thread_to_queue(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        thread = cg.generate_thread(
            topic="Test",
            points=["Point one.", "Point two."],
        )
        result = cg.submit_to_draft_queue(thread, db_path=db_path)
        assert result.get("ok") is True
        assert result.get("id") is not None

    def test_submit_linkedin_to_queue(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        post = cg.generate_linkedin_post(
            topic="Test",
            body="The constraint is trust.",
        )
        result = cg.submit_to_draft_queue(post, db_path=db_path)
        assert result.get("ok") is True


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_returns_dict(self):
        stats = cg.get_stats()
        assert isinstance(stats, dict)
        assert "bookmarks_available" in stats
        assert "themes_detected" in stats
        assert "generations_logged" in stats

    def test_stats_with_log(self, tmp_path):
        log_path = tmp_path / "gen_log.jsonl"
        with open(log_path, "w") as f:
            f.write(json.dumps({"action": "test"}) + "\n")
            f.write(json.dumps({"action": "test2"}) + "\n")

        original = cg.CONTENT_LOG
        try:
            cg.CONTENT_LOG = log_path
            stats = cg.get_stats()
            assert stats["generations_logged"] == 2
        finally:
            cg.CONTENT_LOG = original


# ---------------------------------------------------------------------------
# Brand voice loader
# ---------------------------------------------------------------------------

class TestBrandVoiceLoader:
    def test_load_returns_structure(self):
        voice = cg.load_brand_voice()
        assert "principles" in voice
        assert "forbidden" in voice
        assert "preferred_constructions" in voice
        assert "identity_traits" in voice

    def test_forbidden_is_list(self):
        voice = cg.load_brand_voice()
        assert isinstance(voice["forbidden"], list)
