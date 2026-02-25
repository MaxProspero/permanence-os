"""
models/claude.py — Claude Adapter
CANON: This is the ONLY file that imports anthropic.
CANON: Low temperature, bounded tokens, metadata preserved.
CANON: Logs every call for audit trail.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timezone
from models.base import BaseModel, ModelResponse

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


CALL_LOG = Path("logs/model_calls.jsonl")


class ClaudeModel(BaseModel):
    
    MODELS = {
        "opus": "claude-opus-4-6",
        "sonnet": "claude-sonnet-4-6",
        "haiku": "claude-haiku-4-5-20251001"
    }
    
    def __init__(self, tier: str = "sonnet"):
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("anthropic package not installed. Run: pip install anthropic --break-system-packages")
        
        self.tier = tier
        self.model_id = self.MODELS.get(tier, self.MODELS["sonnet"])
        self.name = f"claude_{tier}"
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key == "sk-ant-YOUR_KEY_HERE":
            raise RuntimeError("ANTHROPIC_API_KEY not set. Add to .env file.")
        
        self.client = anthropic.Anthropic(api_key=api_key)
        CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    def generate(self, prompt: str, system: str = None) -> ModelResponse:
        """
        Generate a response. Logs every call.
        system: Optional Canon-aligned system prompt
        """
        # Default system prompt if none provided
        if not system:
            system = (
                "You are an agent inside Permanence OS, a governed personal intelligence system. "
                "Follow instructions precisely. Source all claims. "
                "Refuse requests that violate: no unsourced claims, no scope creep, "
                "no irreversible actions without human approval."
            )
        
        start = datetime.now(timezone.utc)
        
        message = self.client.messages.create(
            model=self.model_id,
            max_tokens=1024,
            temperature=0.2,  # Low — precision over creativity
            system=system,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        end = datetime.now(timezone.utc)
        elapsed_ms = int((end - start).total_seconds() * 1000)
        
        text = message.content[0].text
        
        # Audit log — append only, never overwrite
        log_entry = {
            "timestamp": start.isoformat(),
            "model": self.model_id,
            "tier": self.tier,
            "prompt_preview": prompt[:100],
            "response_preview": text[:100],
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
            "elapsed_ms": elapsed_ms,
            "stop_reason": message.stop_reason
        }
        
        with open(CALL_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        return ModelResponse(
            text=text,
            metadata={
                "model": self.model_id,
                "tier": self.tier,
                "provider": "anthropic",
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
                "elapsed_ms": elapsed_ms
            }
        )
    
    def is_available(self) -> bool:
        """Check API connectivity."""
        try:
            api_key = os.getenv("ANTHROPIC_API_KEY", "")
            return bool(api_key and api_key != "sk-ant-YOUR_KEY_HERE" and ANTHROPIC_AVAILABLE)
        except Exception:
            return False
