"""
models/registry.py — Model Registry
CANON: Agents request a model tier. Registry returns the right adapter.
CANON: Swapping providers means updating this file only. Agents don't change.
"""

import os
from models.base import BaseModel


class ModelRegistry:
    """
    Central registry for all model adapters.
    Agents call registry.get(tier) — never import provider SDKs directly.
    """
    
    ROUTING = {
        # HIGH complexity — Opus
        "canon_interpretation": "opus",
        "strategy": "opus",
        "code_generation": "opus",
        "adversarial_review": "opus",
        
        # MEDIUM complexity — Sonnet (default)
        "research_synthesis": "sonnet",
        "planning": "sonnet",
        "review": "sonnet",
        "execution": "sonnet",
        "conciliation": "sonnet",
        
        # LOW complexity — Haiku
        "classification": "haiku",
        "summarization": "haiku",
        "tagging": "haiku",
        "formatting": "haiku",
    }
    
    def __init__(self):
        self._adapters = {}
    
    def get(self, task_type: str = "execution") -> BaseModel:
        """
        Get the appropriate model for a task type.
        Returns cached adapter to avoid re-initializing clients.
        """
        tier = self.ROUTING.get(task_type, "sonnet")
        
        if tier not in self._adapters:
            from models.claude import ClaudeModel
            self._adapters[tier] = ClaudeModel(tier=tier)
        
        return self._adapters[tier]
    
    def get_by_tier(self, tier: str) -> BaseModel:
        """Get model directly by tier (opus/sonnet/haiku)."""
        if tier not in self._adapters:
            from models.claude import ClaudeModel
            self._adapters[tier] = ClaudeModel(tier=tier)
        return self._adapters[tier]
    
    def available_tiers(self) -> list:
        return ["opus", "sonnet", "haiku"]
    
    @staticmethod
    def route_for(task_type: str) -> str:
        """Return the tier string without instantiating a model."""
        routing = {
            "canon_interpretation": "opus", "strategy": "opus", "code_generation": "opus",
            "research_synthesis": "sonnet", "planning": "sonnet", "review": "sonnet",
            "execution": "sonnet", "classification": "haiku", "summarization": "haiku"
        }
        return routing.get(task_type, "sonnet")


# Singleton — import this in agents
registry = ModelRegistry()
