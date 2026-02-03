#!/usr/bin/env python3
"""Identity loading and routing utilities."""

import os
from typing import Dict

import yaml

from agents.utils import BASE_DIR

IDENTITY_PATH = os.getenv(
    "PERMANENCE_IDENTITY_PATH", os.path.join(BASE_DIR, "identity_config.yaml")
)


def load_identity() -> Dict:
    try:
        with open(IDENTITY_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


def internal_name() -> str:
    data = load_identity()
    return data.get("identity", {}).get("internal", {}).get("name", "Dax")


def internal_short() -> str:
    data = load_identity()
    return data.get("identity", {}).get("internal", {}).get("short", "Dax")


def public_name() -> str:
    data = load_identity()
    return data.get("identity", {}).get("public", {}).get("name", "Payton Hicks")


def public_legal_name() -> str:
    data = load_identity()
    return data.get("identity", {}).get("public", {}).get("legal_name", "Payton Hicks")


def select_identity_for_goal(goal: str) -> str:
    """
    Rough routing: public for outward-facing or binding actions, internal otherwise.
    """
    goal_lower = goal.lower()
    public_markers = [
        "publish",
        "post",
        "tweet",
        "announce",
        "email",
        "send",
        "newsletter",
        "press",
        "contract",
        "agreement",
        "invoice",
        "payment",
        "public",
    ]

    if any(marker in goal_lower for marker in public_markers):
        return public_name()

    return internal_name()
