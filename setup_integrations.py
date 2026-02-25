#!/usr/bin/env python3
"""
PERMANENCE OS — CLAUDE INTEGRATIONS SETUP
Version: 0.3.1
Date: February 25, 2026
Authority: Payton Hicks

PURPOSE:
Install and wire all Claude integrations shown in the screenshot into
Permanence OS so agents can use Claude as their model backend.

INTEGRATIONS COVERED:
1. Claude Code CLI (terminal) — already present if Codex is running
2. Anthropic Python SDK — for agent LLM calls
3. Model Adapter Layer — governance-compliant Claude wrapper
4. .env configuration — API key and model routing config
5. Health check — verify everything is wired

CODEX INSTRUCTIONS:
Run this script. It installs, configures, and validates. 
Any step that fails is logged. System halts on HIGH risk actions.
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# CONSTANTS
# ============================================================

LOG_PATH = Path("logs/setup_integrations.jsonl")
ENV_PATH = Path(".env")

# Available Claude models (Feb 2026)
CLAUDE_MODELS = {
    "opus": "claude-opus-4-6",           # Canon interpretation, strategy, code
    "sonnet": "claude-sonnet-4-6",       # Research, planning, review (default)
    "haiku": "claude-haiku-4-5-20251001" # Classification, summarization, tagging
}

# What each integration does for Permanence OS
INTEGRATION_MAP = {
    "claude_code_cli": {
        "what": "Claude Code in your terminal — Codex IS this. Already installed.",
        "use_in_pos": "Codex session management, agentic task execution",
        "install_cmd": None,  # Already installed
        "verify_cmd": "claude --version"
    },
    "anthropic_sdk": {
        "what": "Python SDK — how agents make LLM calls",
        "use_in_pos": "models/claude.py adapter — all agent inference goes through here",
        "install_cmd": "pip install anthropic --break-system-packages",
        "verify_cmd": "python -c \"import anthropic; print('anthropic', anthropic.__version__)\""
    },
    "python_dotenv": {
        "what": "Load .env variables — API key management",
        "use_in_pos": "All agents load ANTHROPIC_API_KEY from .env on startup",
        "install_cmd": "pip install python-dotenv --break-system-packages",
        "verify_cmd": "python -c \"import dotenv; print('dotenv OK')\""
    }
}


# ============================================================
# LOGGING (APPEND-ONLY — CANON INVARIANT)
# ============================================================

def log(event: str, data: dict = None, risk: str = "LOW"):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "risk_tier": risk,
        "data": data or {}
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"[{risk}] {event}")


def run_cmd(cmd: str, description: str) -> tuple[bool, str]:
    """Run a shell command. Returns (success, output)."""
    log(f"EXECUTING: {description}", {"cmd": cmd})
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            log(f"SUCCESS: {description}", {"output": output[:200]})
            return True, output
        else:
            error = result.stderr.strip()
            log(f"FAILED: {description}", {"error": error[:200]}, risk="MEDIUM")
            return False, error
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT: {description}", risk="MEDIUM")
        return False, "Command timed out"
    except Exception as e:
        log(f"ERROR: {description}", {"exception": str(e)}, risk="MEDIUM")
        return False, str(e)


# ============================================================
# STEP 1: CHECK WHAT ALREADY EXISTS
# ============================================================

def check_existing_setup() -> dict:
    """Assess current state before installing anything."""
    print("\n=== STEP 1: CHECKING EXISTING SETUP ===\n")
    
    status = {}
    
    # Check Claude Code CLI
    if shutil.which("claude"):
        ok, version = run_cmd("claude --version", "Check Claude Code CLI version")
        status["claude_code_cli"] = {"installed": True, "version": version}
    else:
        status["claude_code_cli"] = {"installed": False, "note": "Claude Code CLI not found in PATH"}
        log("Claude Code CLI not found", risk="MEDIUM")
    
    # Check Python SDK
    ok, out = run_cmd(
        "python -c \"import anthropic; print(anthropic.__version__)\"",
        "Check Anthropic SDK"
    )
    status["anthropic_sdk"] = {"installed": ok, "version": out if ok else None}
    
    # Check dotenv
    ok, out = run_cmd(
        "python -c \"import dotenv; print('ok')\"",
        "Check python-dotenv"
    )
    status["python_dotenv"] = {"installed": ok}
    
    # Check API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and ENV_PATH.exists():
        # Try reading from .env
        with open(ENV_PATH) as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"')
    
    status["api_key"] = {
        "present": bool(api_key),
        "source": "env_var" if os.environ.get("ANTHROPIC_API_KEY") else (".env file" if api_key else "NOT FOUND")
    }
    
    # Check model adapter layer exists
    status["model_adapter"] = {
        "base_exists": Path("models/base.py").exists(),
        "claude_adapter_exists": Path("models/claude.py").exists(),
        "registry_exists": Path("models/registry.py").exists()
    }
    
    print(json.dumps(status, indent=2))
    return status


# ============================================================
# STEP 2: INSTALL DEPENDENCIES
# ============================================================

def install_dependencies(existing: dict) -> dict:
    """Install missing Python packages."""
    print("\n=== STEP 2: INSTALLING DEPENDENCIES ===\n")
    results = {}
    
    if not existing["anthropic_sdk"]["installed"]:
        ok, out = run_cmd(
            "pip install anthropic --break-system-packages",
            "Install Anthropic Python SDK"
        )
        results["anthropic_sdk"] = "installed" if ok else f"FAILED: {out}"
    else:
        print(f"Anthropic SDK already installed: {existing['anthropic_sdk']['version']}")
        results["anthropic_sdk"] = "already_installed"
    
    if not existing["python_dotenv"]["installed"]:
        ok, out = run_cmd(
            "pip install python-dotenv --break-system-packages",
            "Install python-dotenv"
        )
        results["python_dotenv"] = "installed" if ok else f"FAILED: {out}"
    else:
        print("python-dotenv already installed")
        results["python_dotenv"] = "already_installed"
    
    return results


# ============================================================
# STEP 3: CONFIGURE .env
# ============================================================

def configure_env(existing: dict):
    """Write .env file with required config if not present."""
    print("\n=== STEP 3: CONFIGURE .env ===\n")
    
    if not existing["api_key"]["present"]:
        print("""
╔══════════════════════════════════════════════════════════╗
║  ACTION REQUIRED — PAYTON MUST DO THIS MANUALLY          ║
║                                                          ║
║  ANTHROPIC_API_KEY not found.                            ║
║                                                          ║
║  1. Go to: https://console.anthropic.com/settings/keys   ║
║  2. Create an API key                                    ║
║  3. Add to .env file:                                    ║
║     ANTHROPIC_API_KEY=sk-ant-...                         ║
║                                                          ║
║  This is a HIGH RISK action — requires human.            ║
║  Codex cannot and should not store API keys.             ║
╚══════════════════════════════════════════════════════════╝
""")
        log("API KEY REQUIRED — HUMAN ACTION NEEDED", risk="HIGH")
        
        # Write .env template if it doesn't exist
        if not ENV_PATH.exists():
            env_template = """# PERMANENCE OS — ENVIRONMENT CONFIGURATION
# Generated: {timestamp}
# 
# REQUIRED: Add your Anthropic API key below
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE

# MODEL ROUTING (matches MODEL_ROUTING in codex_build_package.py)
PERMANENCE_MODEL_OPUS=claude-opus-4-6
PERMANENCE_MODEL_SONNET=claude-sonnet-4-6
PERMANENCE_MODEL_HAIKU=claude-haiku-4-5-20251001
PERMANENCE_DEFAULT_MODEL=claude-sonnet-4-6

# PATHS (override if needed)
PERMANENCE_CANON_PATH=canon
PERMANENCE_LOGS_PATH=logs
PERMANENCE_MEMORY_PATH=memory
PERMANENCE_SOURCES_PATH=sources
PERMANENCE_OUTPUT_PATH=output
PERMANENCE_KG_PATH=knowledge_graph/graph.json

# GOVERNANCE
PERMANENCE_MAX_STEPS=12
PERMANENCE_MAX_TOOL_CALLS=5
PERMANENCE_AUTO_ESCALATE_HIGH_RISK=true
""".format(timestamp=datetime.now(timezone.utc).isoformat())
            
            with open(ENV_PATH, "w") as f:
                f.write(env_template)
            
            log("Written .env template — human must add API key", risk="HIGH")
            print(f".env template written to {ENV_PATH.absolute()}")
    else:
        print(f"API key found via: {existing['api_key']['source']}")
        
        # Ensure all model vars are in .env
        with open(ENV_PATH, "r") as f:
            content = f.read()
        
        additions = []
        if "PERMANENCE_MODEL_OPUS" not in content:
            additions.append(f"PERMANENCE_MODEL_OPUS={CLAUDE_MODELS['opus']}")
        if "PERMANENCE_MODEL_SONNET" not in content:
            additions.append(f"PERMANENCE_MODEL_SONNET={CLAUDE_MODELS['sonnet']}")
        if "PERMANENCE_MODEL_HAIKU" not in content:
            additions.append(f"PERMANENCE_MODEL_HAIKU={CLAUDE_MODELS['haiku']}")
        
        if additions:
            with open(ENV_PATH, "a") as f:
                f.write("\n# Added by setup_integrations.py\n")
                for line in additions:
                    f.write(line + "\n")
            log(f"Added {len(additions)} model vars to .env")


# ============================================================
# STEP 4: BUILD MODEL ADAPTER LAYER
# ============================================================

def build_model_adapter_layer(existing: dict):
    """
    Creates the governance-compliant Claude wrapper.
    CRITICAL: This is the ONLY place that imports the Anthropic SDK.
    No agent ever imports anthropic directly — all go through this layer.
    """
    print("\n=== STEP 4: BUILD MODEL ADAPTER LAYER ===\n")
    
    models_dir = Path("models")
    models_dir.mkdir(exist_ok=True)
    
    # base.py — abstract interface
    base_content = '''"""
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
'''
    
    # claude.py — the actual adapter
    claude_content = '''"""
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
            f.write(json.dumps(log_entry) + "\\n")
        
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
'''
    
    # registry.py — model selection
    registry_content = f'''"""
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
    
    ROUTING = {{
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
    }}
    
    def __init__(self):
        self._adapters = {{}}
    
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
        routing = {{
            "canon_interpretation": "opus", "strategy": "opus", "code_generation": "opus",
            "research_synthesis": "sonnet", "planning": "sonnet", "review": "sonnet",
            "execution": "sonnet", "classification": "haiku", "summarization": "haiku"
        }}
        return routing.get(task_type, "sonnet")


# Singleton — import this in agents
registry = ModelRegistry()
'''
    
    # Write files (only if they don't exist or are stubs)
    files_written = []
    
    for filename, content in [
        ("models/base.py", base_content),
        ("models/claude.py", claude_content),
        ("models/registry.py", registry_content)
    ]:
        p = Path(filename)
        
        # Check if existing file is a full implementation or a stub
        if p.exists():
            with open(p) as f:
                existing = f.read()
            # If it has real content (not just comments or <50 lines), skip
            if len(existing.strip().splitlines()) > 30:
                print(f"  {filename} already has implementation — skipping")
                continue
        
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
        files_written.append(filename)
        log(f"Written {filename}")
        print(f"  Written: {filename}")
    
    # Write __init__.py
    init_path = Path("models/__init__.py")
    if not init_path.exists():
        with open(init_path, "w") as f:
            f.write('"""models/ — Model Adapter Layer. Canon-compliant provider wrappers."""\n')
        files_written.append("models/__init__.py")
    
    return files_written


# ============================================================
# STEP 5: WIRE AGENTS TO USE MODEL REGISTRY
# ============================================================

def generate_agent_model_patch() -> str:
    """
    Returns the code pattern that Codex should add to each agent.
    Codex: Add this to the top of each agent file.
    """
    return '''
# --- ADD TO EACH AGENT (planner.py, researcher.py, executor.py, reviewer.py) ---

from models.registry import registry

class PlannerAgent:  # (or ResearcherAgent, ExecutorAgent, ReviewerAgent)
    
    def run(self, state):
        """Example: how an agent calls Claude through the governed layer."""
        
        # Get the right model for this agent's task type
        model = registry.get("planning")  # or "research_synthesis", "execution", "review"
        
        # Build a Canon-aligned prompt
        prompt = f"""
TASK: {state.task_goal}
CANON VALUES: Agency Preservation, Truth Over Comfort, Compounding Intelligence
CONSTRAINT: Source all claims. No speculation beyond sources. No scope creep.

Your role: [PLANNER/RESEARCHER/EXECUTOR/REVIEWER]
Your boundary: [specific boundary for this agent]

Produce output in this format:
- finding: [concrete claim]
- source: [where it came from]  
- confidence: [HIGH/MEDIUM/LOW]
- limitations: [what this doesn't tell us]
"""
        
        response = model.generate(prompt)
        
        # Response goes to reviewer before delivery — never directly to output
        state.working_memory["draft"] = response.text
        state.logs.append(f"[{self.__class__.__name__}] Generated draft: {response.metadata}")
        
        return state
'''


# ============================================================
# STEP 6: VERIFICATION
# ============================================================

def verify_full_stack(existing: dict) -> dict:
    """Run end-to-end verification that everything is wired correctly."""
    print("\n=== STEP 6: VERIFICATION ===\n")
    
    results = {}
    
    # 1. SDK importable
    ok, out = run_cmd(
        "python -c \"import anthropic; print('SDK:', anthropic.__version__)\"",
        "Verify Anthropic SDK import"
    )
    results["sdk_import"] = "PASS" if ok else f"FAIL: {out}"
    
    # 2. Model adapter layer importable
    ok, out = run_cmd(
        "python -c \"from models.base import BaseModel; from models.registry import ModelRegistry; print('Model layer OK')\"",
        "Verify model adapter layer"
    )
    results["model_layer"] = "PASS" if ok else f"FAIL: {out}"
    
    # 3. API key present
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key and ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"')
    
    key_set = bool(api_key and api_key != "sk-ant-YOUR_KEY_HERE")
    results["api_key"] = "PASS" if key_set else "FAIL — key not set (human must add to .env)"
    
    # 4. Live API test (only if key is set)
    if key_set:
        ok, out = run_cmd(
            "python -c \""
            "import os; from dotenv import load_dotenv; load_dotenv(); "
            "import anthropic; "
            "c = anthropic.Anthropic(); "
            "r = c.messages.create(model='claude-haiku-4-5-20251001', max_tokens=10, messages=[{'role':'user','content':'say OK'}]); "
            "print('API call:', r.content[0].text)"
            "\"",
            "Live API test with Haiku"
        )
        results["live_api_test"] = "PASS" if ok else f"FAIL: {out}"
    else:
        results["live_api_test"] = "SKIPPED — API key not set"
    
    # 5. Claude Code CLI
    if shutil.which("claude"):
        results["claude_code_cli"] = "PASS — already installed (you're using it)"
    else:
        results["claude_code_cli"] = "NOT IN PATH — install from https://claude.ai/download"
    
    print("\n--- VERIFICATION RESULTS ---")
    for check, status in results.items():
        icon = "✓" if "PASS" in status else ("⚠" if "SKIP" in status else "✗")
        print(f"  {icon}  {check}: {status}")
    
    all_pass = all("PASS" in v or "SKIP" in v for v in results.values())
    print(f"\n{'✓ ALL CHECKS PASS' if all_pass else '✗ SOME CHECKS FAILED — see above'}")
    
    return results


# ============================================================
# STEP 7: CLAUDE CODE INTEGRATIONS (VS Code, JetBrains, Slack)
# ============================================================

def print_external_integration_instructions():
    """
    The non-terminal integrations (VS Code extension, Slack, Excel, etc.)
    cannot be installed via script — they require GUI actions.
    This prints exact steps for Payton to follow.
    """
    print("""
=== STEP 7: EXTERNAL INTEGRATIONS (MANUAL STEPS FOR PAYTON) ===

These are shown in the screenshot. Codex cannot install GUI extensions.
Payton does these manually. Takes ~10 minutes total.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. CLAUDE CODE — VS CODE EXTENSION
   Why: Write code in VS Code, Claude reviews/edits inline
   Steps:
   a. Open VS Code
   b. Press Cmd+Shift+X (Extensions)
   c. Search "Claude" → install Anthropic's official extension
   d. OR terminal: code --install-extension anthropic.claude-code

   Permanence OS use: Codex uses VS Code for file editing during builds

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2. CLAUDE CODE — JETBRAINS (if you use PyCharm/IntelliJ)
   Why: Same as VS Code but in JetBrains IDEs
   Steps:
   a. Open PyCharm → Plugins → Marketplace
   b. Search "Claude" → install
   d. Sign in with claude.ai account

   Permanence OS use: Optional — only if you code in PyCharm

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3. CLAUDE — SLACK INTEGRATION
   Why: Permanence OS can send briefings/alerts to a private Slack channel
   Steps:
   a. Go to: https://claude.ai/download → click Slack → Install
   b. Authorize for your workspace
   c. Create a private channel: #permanence-briefings
   d. Add Claude to that channel

   Permanence OS use: Daily briefings → Slack DM or private channel
   (Codex will build the Slack webhook in the briefing pipeline)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4. CLAUDE — iOS / ANDROID APP
   Why: Mobile access to Permanence OS briefings
   Steps:
   a. iOS: App Store → search "Claude" → download Anthropic's app
   b. Android: Google Play → same
   c. Sign in with same claude.ai account

   Permanence OS use: Read daily briefings on mobile
   (Advanced: wire to webhook so briefings auto-appear in Claude app)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5. CLAUDE — CHROME EXTENSION
   Why: Horizon Agent can monitor web pages, capture bookmarks
   Steps:
   a. Go to: https://claude.ai/download → click Chrome → Install
   b. Pin the extension
   c. When browsing, click it to ask Claude about the current page

   Permanence OS use: Bookmark capture → Knowledge Graph ingestion
   (The X bookmarks pipeline we built feeds from this)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

6. CLAUDE IN EXCEL / POWERPOINT (if needed)
   Why: Produce formatted reports from Permanence OS outputs
   Steps:
   a. Go to: https://claude.ai/download → click Excel or PowerPoint
   b. Install the Office add-in
   c. Authorize with claude.ai account

   Permanence OS use: Low priority. Use only for investor/family presentations.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

7. COWORK (Desktop App — Mac/Windows)
   Why: Claude works in your files and browser tabs autonomously
   Status: Available for Pro and Max plans only, desktop only
   Steps:
   a. Go to: https://claude.ai/download → click Cowork → Open
   b. If you're on Pro/Max, it opens directly
   c. It can clean folders, make shopping lists, create expense reports

   Permanence OS use: EVALUATE — could handle file organization tasks
   that would otherwise need a custom agent

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PRIORITY ORDER FOR PAYTON:
1. Chrome Extension (feeds bookmark pipeline — do first)
2. iOS/Android app (daily briefings — do second)
3. Slack integration (briefing delivery — do third)
4. VS Code extension (coding workflow — already probably done)
5. Cowork (evaluate when stable)
6. Excel/PowerPoint (low priority)

""")


# ============================================================
# MAIN
# ============================================================

def main():
    print("\n" + "="*60)
    print("PERMANENCE OS — CLAUDE INTEGRATIONS SETUP")
    print("="*60)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("Canon invariant: No execution without evaluation")
    print("Risk tier: LOW-MEDIUM (all reversible except API key)\n")
    
    log("Setup integrations started")
    
    # Step 1: Assess
    existing = check_existing_setup()
    
    # Step 2: Install
    install_results = install_dependencies(existing)
    
    # Step 3: Configure .env
    configure_env(existing)
    
    # Step 4: Build model adapter layer
    files_written = build_model_adapter_layer(existing)
    
    # Step 5: Print agent wiring pattern
    print("\n=== STEP 5: AGENT WIRING PATTERN ===")
    print("Add this pattern to each agent file:")
    print(generate_agent_model_patch())
    
    # Step 6: Verify
    verify_results = verify_full_stack(existing)
    
    # Step 7: External integrations
    print_external_integration_instructions()
    
    # Final session log
    session = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "files_written": files_written,
        "install_results": install_results,
        "verify_results": verify_results,
        "next_actions": [
            "1. Add ANTHROPIC_API_KEY to .env (Payton — manual)",
            "2. Install Chrome Extension (Payton — manual)",
            "3. Install iOS/Android app (Payton — manual)",
            "4. Wire registry.get() into each agent's run() method (Codex)",
            "5. Run: python -c \"from models.registry import registry; m=registry.get('planning'); print(m.is_available())\"",
            "6. Run the eval harness again: python codex_build_package.py"
        ]
    }
    
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"event": "SETUP_COMPLETE", **session}) + "\n")
    
    print("\n=== SETUP COMPLETE ===")
    print(f"Log: {LOG_PATH.absolute()}")
    print("\nNext actions:")
    for action in session["next_actions"]:
        print(f"  {action}")


if __name__ == "__main__":
    main()
