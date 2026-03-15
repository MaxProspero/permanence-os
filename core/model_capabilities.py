from __future__ import annotations

from typing import Any, Dict


DEFAULT_MODEL_CAPABILITIES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "anthropic": {
        "claude-opus-4-6": {
            "tier": "opus",
            "strengths": ["architecture", "code", "review", "strategy"],
            "privacy": "hosted",
            "cost": "high",
        },
        "claude-sonnet-4-6": {
            "tier": "sonnet",
            "strengths": ["implementation", "editing", "planning", "research"],
            "privacy": "hosted",
            "cost": "medium",
        },
        "claude-haiku-4-5-20251001": {
            "tier": "haiku",
            "strengths": ["classification", "summarization", "formatting"],
            "privacy": "hosted",
            "cost": "low",
        },
    },
    "openai": {
        "gpt-4.1": {
            "tier": "opus",
            "strengths": ["coding", "reasoning", "transformation"],
            "privacy": "hosted",
            "cost": "high",
        },
        "gpt-4o": {
            "tier": "sonnet",
            "strengths": ["general", "multimodal", "planning"],
            "privacy": "hosted",
            "cost": "medium",
        },
        "gpt-4o-mini": {
            "tier": "haiku",
            "strengths": ["utility", "formatting", "classification"],
            "privacy": "hosted",
            "cost": "low",
        },
    },
    "xai": {
        "grok-3-latest": {
            "tier": "opus",
            "strengths": ["strategy", "reasoning", "research"],
            "privacy": "hosted",
            "cost": "high",
        },
        "grok-3-mini": {
            "tier": "sonnet",
            "strengths": ["research", "planning", "general"],
            "privacy": "hosted",
            "cost": "medium",
        },
        "grok-2-mini": {
            "tier": "haiku",
            "strengths": ["classification", "utility"],
            "privacy": "hosted",
            "cost": "low",
        },
    },
    "ollama": {
        "qwen2.5:7b": {
            "tier": "sonnet",
            "strengths": ["routine", "local_privacy", "drafting", "coding_first_pass"],
            "privacy": "local",
            "cost": "free",
        },
        "qwen2.5:3b": {
            "tier": "haiku",
            "strengths": ["classification", "summarization", "local_privacy"],
            "privacy": "local",
            "cost": "free",
        },
        "qwen3:8b": {
            "tier": "opus",
            "strengths": ["local_reasoning", "local_code", "local_privacy"],
            "privacy": "local",
            "cost": "free",
        },
        "qwen3:4b": {
            "tier": "sonnet",
            "strengths": ["local_routine", "local_planning", "local_privacy"],
            "privacy": "local",
            "cost": "free",
        },
    },
}
