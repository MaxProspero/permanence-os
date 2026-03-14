"""
models/openai_model.py - OpenAI adapter
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
DEFAULT_BASE_URL = "https://api.openai.com/v1"


def _string_content(content: Any) -> str:
    if isinstance(content, str):
        return content
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
    return ""


class OpenAIModel(BaseModel):
    MODELS = {
        "opus": "gpt-4.1",
        "sonnet": "gpt-4o",
        "haiku": "gpt-4o-mini",
    }

    ENV_BY_TIER = {
        "opus": "PERMANENCE_OPENAI_MODEL_OPUS",
        "sonnet": "PERMANENCE_OPENAI_MODEL_SONNET",
        "haiku": "PERMANENCE_OPENAI_MODEL_HAIKU",
    }

    def __init__(self, tier: str = "sonnet", model_id: str | None = None):
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests package not installed. Run: pip install requests")

        self.tier = str(tier or "sonnet").strip().lower() or "sonnet"
        tier_env = os.getenv(self.ENV_BY_TIER.get(self.tier, ""), "").strip()
        selected_model = str(model_id or "").strip() or tier_env
        self.model_id = selected_model or self.MODELS.get(self.tier, self.MODELS["sonnet"])
        self.name = f"openai_{self.tier}"
        self.base_url = str(os.getenv("PERMANENCE_OPENAI_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")

        api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
        if not api_key or api_key in {"your_key_here", "YOUR_KEY_HERE"}:
            raise RuntimeError("OPENAI_API_KEY not set. Add to .env file.")
        self.api_key = api_key
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
            "temperature": 0.2,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=45,
        )
        if response.status_code >= 400:
            detail = response.text.strip()
            if len(detail) > 400:
                detail = detail[:397].rstrip() + "..."
            raise RuntimeError(f"OpenAI API error {response.status_code}: {detail}")

        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(f"OpenAI API returned invalid JSON: {exc}") from exc

        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("OpenAI API returned no choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else {}
        text = _string_content((message or {}).get("content"))
        if not text:
            raise RuntimeError("OpenAI API returned empty response text")

        usage = body.get("usage") if isinstance(body, dict) else {}
        input_tokens = int((usage or {}).get("prompt_tokens") or 0)
        output_tokens = int((usage or {}).get("completion_tokens") or 0)
        stop_reason = str(first.get("finish_reason") or "unknown")
        elapsed_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        log_entry = {
            "timestamp": start.isoformat(),
            "model": self.model_id,
            "tier": self.tier,
            "provider": "openai",
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
                "provider": "openai",
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
        api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
        return bool(REQUESTS_AVAILABLE and api_key and api_key not in {"your_key_here", "YOUR_KEY_HERE"})
