"""
models/ollama.py - Ollama local adapter
CANON: Provider-specific SDK/API calls stay inside model adapters.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models.base import BaseModel, ModelResponse

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


CALL_LOG = Path("logs/model_calls.jsonl")
DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def _string_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"output_text", "text"}:
                    text = str(item.get("text") or "").strip()
                    if text:
                        chunks.append(text)
            elif isinstance(item, str):
                text = item.strip()
                if text:
                    chunks.append(text)
        return "\n".join(chunks).strip()
    if isinstance(content, dict):
        message = content.get("message")
        if isinstance(message, dict):
            text = str(message.get("content") or "").strip()
            if text:
                return text
        text = str(content.get("response") or "").strip()
        if text:
            return text
    return ""


class OllamaModel(BaseModel):
    MODELS = {
        "opus": "qwen3:8b",
        "sonnet": "qwen3:4b",
        "haiku": "qwen2.5:3b",
    }

    ENV_BY_TIER = {
        "opus": "PERMANENCE_OLLAMA_MODEL_OPUS",
        "sonnet": "PERMANENCE_OLLAMA_MODEL_SONNET",
        "haiku": "PERMANENCE_OLLAMA_MODEL_HAIKU",
    }

    def __init__(self, tier: str = "sonnet", model_id: str | None = None):
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests package not installed. Run: pip install requests")

        self.tier = str(tier or "sonnet").strip().lower() or "sonnet"
        tier_env = os.getenv(self.ENV_BY_TIER.get(self.tier, ""), "").strip()
        selected_model = str(model_id or "").strip() or tier_env
        self.model_id = selected_model or self.MODELS.get(self.tier, self.MODELS["sonnet"])
        self.name = f"ollama_{self.tier}"
        self.base_url = str(os.getenv("PERMANENCE_OLLAMA_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        CALL_LOG.parent.mkdir(parents=True, exist_ok=True)

    def generate(self, prompt: str, system: str = None) -> ModelResponse:
        if not system:
            system = (
                "You are an agent inside Permanence OS, a governed personal intelligence system. "
                "Follow instructions precisely. Source all claims. "
                "Refuse requests that violate: no unsourced claims, no scope creep, "
                "no irreversible actions without human approval."
            )

        start = datetime.now(timezone.utc)
        payload = {
            "model": self.model_id,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": 0.2,
            },
        }
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        if response.status_code >= 400:
            detail = response.text.strip()
            if len(detail) > 400:
                detail = detail[:397].rstrip() + "..."
            raise RuntimeError(f"Ollama API error {response.status_code}: {detail}")

        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Ollama API returned invalid JSON: {exc}") from exc

        text = _string_content(body)
        if not text:
            raise RuntimeError("Ollama API returned empty response text")

        input_tokens = int(body.get("prompt_eval_count") or 0)
        output_tokens = int(body.get("eval_count") or 0)
        stop_reason = "stop"
        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        log_entry = {
            "timestamp": start.isoformat(),
            "model": self.model_id,
            "tier": self.tier,
            "provider": "ollama",
            "prompt_preview": prompt[:100],
            "response_preview": text[:100],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "elapsed_ms": elapsed_ms,
            "stop_reason": stop_reason,
        }
        with open(CALL_LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(log_entry) + "\n")

        resp = ModelResponse(
            text=text,
            metadata={
                "model": self.model_id,
                "tier": self.tier,
                "provider": "ollama",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "elapsed_ms": elapsed_ms,
                "stop_reason": stop_reason,
            },
        )

        # Cost tracking (non-blocking — never break inference)
        try:
            from core.cost_tracker import _ensure_tracker
            _ensure_tracker().record(resp.metadata)
        except Exception:
            pass

        return resp

    def is_available(self) -> bool:
        if not REQUESTS_AVAILABLE:
            return False
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return response.status_code == 200
        except Exception:
            return False
