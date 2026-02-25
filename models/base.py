"""
models/base.py — Abstract Model Interface
CANON: Models are replaceable engines. Governance never depends on which one is used.
No agent imports a provider SDK. All inference goes through this layer.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime, timezone


class ModelResponse:
    def __init__(self, text: str, metadata: Dict[str, Any] = None):
        self.text = text
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()


class BaseModel(ABC):
    name: str
    
    @abstractmethod
    def generate(self, prompt: str, system: str = None) -> ModelResponse:
        """Generate a response. Returns ModelResponse."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this model is accessible."""
        pass
