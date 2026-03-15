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

    SUPPORTED_PROVIDERS = ("anthropic", "openai", "xai", "openclaw", "ollama")
    PROVIDER_ALIASES = {
        "anthropic": "anthropic",
        "claude": "anthropic",
        "openai": "openai",
        "gpt": "openai",
        "xai": "xai",
        "grok": "xai",
        "openclaw": "openclaw",
        "open_claw": "openclaw",
        "claw": "openclaw",
        "ollama": "ollama",
        "local": "ollama",
        "qwen": "ollama",
    }
    DEFAULT_PROVIDER = "anthropic"
    DEFAULT_FALLBACKS = "anthropic,openai,xai,openclaw,ollama"

    def __init__(self):
        self._adapters = {}

    @classmethod
    def _normalize_provider(cls, value: str) -> str:
        token = str(value or "").strip().lower()
        return cls.PROVIDER_ALIASES.get(token, token)

    def _infer_provider_from_model_name(self, model_name: str) -> str:
        token = str(model_name or "").strip().lower()
        if not token:
            return ""
        if token.startswith("claude") or "anthropic" in token:
            return "anthropic"
        if token.startswith("grok") or token.startswith("xai"):
            return "xai"
        if token.startswith("openclaw") or token.startswith("claw"):
            return "openclaw"
        if token.startswith("gpt") or token.startswith("o1") or token.startswith("o3") or token.startswith("o4"):
            return "openai"
        if token.startswith("qwen") or token.startswith("llama") or token.startswith("gemma") or "ollama" in token:
            return "ollama"
        return ""

    def _provider_candidates(self, provider: str = "", model_name: str = "") -> list[str]:
        configured = self._normalize_provider(os.getenv("PERMANENCE_MODEL_PROVIDER", self.DEFAULT_PROVIDER))
        fallback_raw = os.getenv("PERMANENCE_MODEL_PROVIDER_FALLBACKS", self.DEFAULT_FALLBACKS)
        inferred = self._normalize_provider(self._infer_provider_from_model_name(model_name))
        explicit = self._normalize_provider(provider)

        ordered = []
        for token in (explicit, inferred, configured):
            if token and token in self.SUPPORTED_PROVIDERS and token not in ordered:
                ordered.append(token)

        for raw in str(fallback_raw or "").split(","):
            token = self._normalize_provider(raw)
            if token and token in self.SUPPORTED_PROVIDERS and token not in ordered:
                ordered.append(token)

        if not ordered:
            ordered.append(self.DEFAULT_PROVIDER)
        return ordered

    @staticmethod
    def _provider_class(provider: str):
        normalized = str(provider or "").strip().lower()
        if normalized == "anthropic":
            from models.claude import ClaudeModel

            return ClaudeModel
        if normalized == "openai":
            from models.openai_model import OpenAIModel

            return OpenAIModel
        if normalized == "xai":
            from models.xai import XAIModel

            return XAIModel
        if normalized == "openclaw":
            from models.openclaw import OpenClawModel

            return OpenClawModel
        if normalized == "ollama":
            from models.ollama import OllamaModel

            return OllamaModel
        raise ValueError(f"Unsupported model provider: {provider}")

    @staticmethod
    def _cache_key(provider: str, tier: str, model_name: str) -> str:
        return f"{provider}:{tier}:{model_name or ''}"

    def get(self, task_type: str = "execution", model_name: str = "", provider: str = "") -> BaseModel:
        """
        Get the appropriate model for a task type.
        Returns cached adapter to avoid re-initializing clients.
        """
        tier = self.ROUTING.get(task_type, "sonnet")
        return self.get_by_tier(tier=tier, model_name=model_name, provider=provider)

    def get_by_tier(self, tier: str, model_name: str = "", provider: str = "") -> BaseModel:
        """Get model directly by tier (opus/sonnet/haiku) with provider fallback."""
        normalized_tier = str(tier or "sonnet").strip().lower() or "sonnet"
        candidates = self._provider_candidates(provider=provider, model_name=model_name)
        errors: list[str] = []

        for provider_name in candidates:
            cache_key = self._cache_key(provider_name, normalized_tier, model_name)
            cached = self._adapters.get(cache_key)
            if cached is not None:
                return cached
            try:
                adapter_cls = self._provider_class(provider_name)
                adapter = adapter_cls(tier=normalized_tier, model_id=(model_name or None))
                self._adapters[cache_key] = adapter
                return adapter
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{provider_name}:{exc.__class__.__name__}")
                continue

        detail = ", ".join(errors) if errors else "no providers attempted"
        raise RuntimeError(f"No model provider available for tier='{normalized_tier}': {detail}")

    def available_tiers(self) -> list:
        return ["opus", "sonnet", "haiku"]

    @staticmethod
    def route_for(task_type: str) -> str:
        """Return the tier string without instantiating a model."""
        routing = {
            "canon_interpretation": "opus", "strategy": "opus", "code_generation": "opus",
            "research_synthesis": "sonnet", "planning": "sonnet", "review": "sonnet",
            "execution": "sonnet", "conciliation": "sonnet",
            "classification": "haiku", "summarization": "haiku", "tagging": "haiku", "formatting": "haiku",
        }
        return routing.get(task_type, "sonnet")


# Singleton — import this in agents
registry = ModelRegistry()
