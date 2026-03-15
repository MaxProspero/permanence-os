#!/usr/bin/env python3
"""Tests for Social Draft Queue API endpoints in dashboard_api.py.

Uses Flask's test client with a temporary SQLite database to verify the
seven social draft CRUD/lifecycle endpoints.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    import dashboard_api  # noqa: E402
    from scripts import social_draft_queue  # noqa: E402

    HAS_FLASK = True
except Exception:
    HAS_FLASK = False


pytestmark = pytest.mark.skipif(not HAS_FLASK, reason="dashboard_api / flask not available")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Yield a Flask test client with an isolated temp database."""
    db_path = str(tmp_path / "test_social.db")
    monkeypatch.setattr(social_draft_queue, "DEFAULT_DB_PATH", db_path)
    dashboard_api.app.config["TESTING"] = True
    with dashboard_api.app.test_client() as c:
        yield c


# ── List / Submit ──────────────────────────────────────────────────────


def test_list_empty(client):
    resp = client.get("/api/social/drafts")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] == 0
    assert data["drafts"] == []


def test_submit_and_list(client):
    resp = client.post("/api/social/drafts", json={
        "platform": "x",
        "content": "Test tweet from agent",
        "agent_id": "test_agent",
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["ok"] is True
    assert "id" in body

    resp = client.get("/api/social/drafts")
    data = resp.get_json()
    assert data["count"] == 1
    assert data["drafts"][0]["platform"] == "x"


def test_submit_invalid_platform_returns_400(client):
    resp = client.post("/api/social/drafts", json={
        "platform": "myspace",
        "content": "This should fail",
    })
    assert resp.status_code == 400
    body = resp.get_json()
    assert body["ok"] is False


# ── Get single ─────────────────────────────────────────────────────────


def test_get_single_draft(client):
    resp = client.post("/api/social/drafts", json={
        "platform": "x",
        "content": "Fetch me by ID",
    })
    draft_id = resp.get_json()["id"]

    resp = client.get(f"/api/social/drafts/{draft_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["content"] == "Fetch me by ID"
    assert data["status"] == "pending"


def test_get_nonexistent_returns_404(client):
    resp = client.get("/api/social/drafts/999")
    assert resp.status_code == 404


# ── Approve / Reject / Publish lifecycle ───────────────────────────────


def test_approve_draft(client):
    resp = client.post("/api/social/drafts", json={
        "platform": "x",
        "content": "Approve me",
    })
    draft_id = resp.get_json()["id"]

    resp = client.patch(f"/api/social/drafts/{draft_id}/approve", json={
        "notes": "Looks good",
    })
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


def test_reject_draft(client):
    resp = client.post("/api/social/drafts", json={
        "platform": "tiktok",
        "content": "Reject me",
    })
    draft_id = resp.get_json()["id"]

    resp = client.patch(f"/api/social/drafts/{draft_id}/reject", json={
        "notes": "Too long, rewrite",
    })
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True


def test_full_lifecycle_submit_approve_publish(client):
    # Submit
    resp = client.post("/api/social/drafts", json={
        "platform": "youtube",
        "content": "Video description draft",
        "content_type": "youtube_description",
    })
    draft_id = resp.get_json()["id"]

    # Approve
    resp = client.patch(f"/api/social/drafts/{draft_id}/approve", json={})
    assert resp.status_code == 200

    # Publish
    resp = client.patch(f"/api/social/drafts/{draft_id}/published", json={})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True


# ── Stats ──────────────────────────────────────────────────────────────


def test_stats_endpoint(client):
    client.post("/api/social/drafts", json={"platform": "x", "content": "T1"})
    client.post("/api/social/drafts", json={"platform": "tiktok", "content": "T2"})

    resp = client.get("/api/social/stats")
    assert resp.status_code == 200
    stats = resp.get_json()
    assert stats.get("total", stats.get("pending", 0)) >= 2


# ── Filters ────────────────────────────────────────────────────────────


def test_filter_by_platform(client):
    client.post("/api/social/drafts", json={"platform": "x", "content": "X post"})
    client.post("/api/social/drafts", json={"platform": "tiktok", "content": "TikTok script"})

    resp = client.get("/api/social/drafts?platform=x")
    data = resp.get_json()
    assert data["count"] == 1
    assert data["drafts"][0]["platform"] == "x"


def test_filter_by_status(client):
    resp = client.post("/api/social/drafts", json={"platform": "x", "content": "To approve"})
    draft_id = resp.get_json()["id"]
    client.patch(f"/api/social/drafts/{draft_id}/approve", json={})

    client.post("/api/social/drafts", json={"platform": "x", "content": "Still pending"})

    resp = client.get("/api/social/drafts?status=approved")
    data = resp.get_json()
    assert data["count"] == 1
    assert data["drafts"][0]["status"] == "approved"
