"""Tests for scripts/social_draft_queue.py — Social Media Draft Queue."""

import json
import os
import tempfile

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.social_draft_queue import (
    submit_draft,
    list_drafts,
    get_draft,
    approve_draft,
    reject_draft,
    mark_published,
    get_stats,
    VALID_PLATFORMS,
)


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_social.db")


class TestSubmitDraft:
    """Draft submission tests."""

    def test_submit_valid_draft(self, db_path):
        result = submit_draft(
            platform="x",
            content="Test tweet about AI agents",
            agent_id="social_agent",
            db_path=db_path,
        )
        assert result["ok"] is True
        assert result["id"] == 1
        assert result["platform"] == "x"
        assert result["status"] == "pending"

    def test_submit_invalid_platform(self, db_path):
        result = submit_draft(
            platform="myspace",
            content="This should fail",
            db_path=db_path,
        )
        assert result["ok"] is False
        assert "Invalid platform" in result["error"]

    def test_submit_with_metadata(self, db_path):
        result = submit_draft(
            platform="tiktok",
            content="60-second explainer on knowledge graphs",
            content_type="tiktok_script",
            media_notes="Use screen recording of dashboard",
            hashtags="#AI,#agents,#automation",
            agent_id="social_agent",
            metadata={"tone": "casual", "target_duration": 60},
            db_path=db_path,
        )
        assert result["ok"] is True
        draft = get_draft(result["id"], db_path=db_path)
        assert draft["content_type"] == "tiktok_script"
        assert draft["media_notes"] == "Use screen recording of dashboard"

    def test_submit_youtube_description(self, db_path):
        result = submit_draft(
            platform="youtube",
            content="Building an AI agent system from scratch — full walkthrough",
            content_type="youtube_description",
            hashtags="#AI,#coding,#agents",
            db_path=db_path,
        )
        assert result["ok"] is True


class TestListDrafts:
    """Draft listing and filtering tests."""

    def test_list_empty(self, db_path):
        drafts = list_drafts(db_path=db_path)
        assert drafts == []

    def test_list_returns_submitted(self, db_path):
        submit_draft(platform="x", content="Tweet 1", db_path=db_path)
        submit_draft(platform="tiktok", content="TikTok 1", db_path=db_path)
        drafts = list_drafts(db_path=db_path)
        assert len(drafts) == 2

    def test_filter_by_platform(self, db_path):
        submit_draft(platform="x", content="Tweet 1", db_path=db_path)
        submit_draft(platform="tiktok", content="TikTok 1", db_path=db_path)
        submit_draft(platform="x", content="Tweet 2", db_path=db_path)
        drafts = list_drafts(platform="x", db_path=db_path)
        assert len(drafts) == 2

    def test_filter_by_status(self, db_path):
        r1 = submit_draft(platform="x", content="Tweet 1", db_path=db_path)
        submit_draft(platform="x", content="Tweet 2", db_path=db_path)
        approve_draft(r1["id"], db_path=db_path)
        pending = list_drafts(status="pending", db_path=db_path)
        approved = list_drafts(status="approved", db_path=db_path)
        assert len(pending) == 1
        assert len(approved) == 1


class TestApproveReject:
    """Approval and rejection workflow tests."""

    def test_approve_pending_draft(self, db_path):
        r = submit_draft(platform="x", content="Test tweet", db_path=db_path)
        result = approve_draft(r["id"], reviewer_notes="Looks good", db_path=db_path)
        assert result["ok"] is True
        assert result["status"] == "approved"
        draft = get_draft(r["id"], db_path=db_path)
        assert draft["status"] == "approved"
        assert draft["reviewer_notes"] == "Looks good"

    def test_reject_pending_draft(self, db_path):
        r = submit_draft(platform="x", content="Test tweet", db_path=db_path)
        result = reject_draft(r["id"], reviewer_notes="Too long", db_path=db_path)
        assert result["ok"] is True
        assert result["status"] == "rejected"

    def test_cannot_approve_nonexistent(self, db_path):
        result = approve_draft(999, db_path=db_path)
        assert result["ok"] is False

    def test_cannot_approve_already_approved(self, db_path):
        r = submit_draft(platform="x", content="Test", db_path=db_path)
        approve_draft(r["id"], db_path=db_path)
        result = approve_draft(r["id"], db_path=db_path)
        assert result["ok"] is False
        assert "not pending" in result["error"]

    def test_cannot_reject_already_rejected(self, db_path):
        r = submit_draft(platform="x", content="Test", db_path=db_path)
        reject_draft(r["id"], db_path=db_path)
        result = reject_draft(r["id"], db_path=db_path)
        assert result["ok"] is False


class TestPublishWorkflow:
    """Full draft lifecycle: submit → approve → publish."""

    def test_full_lifecycle(self, db_path):
        # Submit
        r = submit_draft(platform="x", content="Ship it!", agent_id="social_agent", db_path=db_path)
        assert r["ok"] is True

        # Approve
        a = approve_draft(r["id"], reviewer_notes="Go", db_path=db_path)
        assert a["ok"] is True

        # Publish
        p = mark_published(r["id"], db_path=db_path)
        assert p["ok"] is True
        assert p["status"] == "published"

        draft = get_draft(r["id"], db_path=db_path)
        assert draft["status"] == "published"
        assert draft["published_at"] != ""

    def test_cannot_publish_unapproved(self, db_path):
        r = submit_draft(platform="x", content="Not yet", db_path=db_path)
        result = mark_published(r["id"], db_path=db_path)
        assert result["ok"] is False
        assert "not approved" in result["error"]


class TestStats:
    """Queue statistics tests."""

    def test_stats_empty(self, db_path):
        stats = get_stats(db_path=db_path)
        assert stats["pending"] == 0
        assert stats["approved"] == 0

    def test_stats_with_drafts(self, db_path):
        submit_draft(platform="x", content="T1", db_path=db_path)
        r2 = submit_draft(platform="tiktok", content="T2", db_path=db_path)
        approve_draft(r2["id"], db_path=db_path)
        stats = get_stats(db_path=db_path)
        assert stats["pending"] == 1
        assert stats["approved"] == 1
        assert stats["by_platform"]["x"] == 1
        assert stats["by_platform"]["tiktok"] == 1
