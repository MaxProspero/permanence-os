#!/usr/bin/env python3
"""
PLANNER AGENT
Converts human goals into structured, bounded task specifications
"""

from dataclasses import dataclass
from typing import Any, List, Dict, Optional
from datetime import datetime, timezone
import json
import os
import re

from agents.utils import log

try:
    from core.model_router import ModelRouter
except Exception:  # pragma: no cover - keep planner import-safe in minimal environments
    ModelRouter = None


@dataclass
class TaskSpecification:
    """Structured task plan"""
    task_id: str
    goal: str
    success_criteria: List[str]
    deliverables: List[str]
    constraints: List[str]
    required_resources: List[str]
    estimated_steps: int
    estimated_tool_calls: int
    falsifiable: bool  # Can we tell if this succeeded/failed?
    created_at: str


class PlannerAgent:
    """
    ROLE: Convert human goals into structured, bounded task specifications

    INPUTS:
    - User request
    - Canon constraints
    - Available resources

    OUTPUTS:
    - Task specification
    - Success criteria
    - Resource requirements
    - Risk assessment

    CONSTRAINTS:
    - Cannot execute plans
    - Cannot gather external data
    - Must specify concrete deliverables
    - Plans must be falsifiable
    """

    def __init__(self, canon: Dict, model_router: Optional["ModelRouter"] = None):
        self.canon = canon
        self.model_router = model_router or (ModelRouter() if ModelRouter else None)
        self.enable_model_assist = os.getenv("PERMANENCE_ENABLE_MODEL_ASSIST", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def create_plan(self, goal: str, context: Optional[Dict] = None) -> TaskSpecification:
        """
        Generate structured task specification
        """

        # Parse goal and extract key elements
        deliverables = self._identify_deliverables(goal)
        success_criteria = self._define_success_criteria(goal, deliverables)
        constraints = self._extract_constraints(goal, context)
        resources = self._identify_required_resources(goal)

        # Estimate resource needs
        estimated_steps = self._estimate_steps(goal, deliverables)
        estimated_tool_calls = self._estimate_tool_calls(goal, resources)

        # Check if falsifiable
        falsifiable = self._check_falsifiability(success_criteria)

        # Optional model-assisted planning (off by default, deterministic fallback preserved).
        if self.enable_model_assist:
            assisted = self._model_assisted_fields(goal=goal, context=context)
            if assisted:
                if assisted.get("deliverables"):
                    deliverables = assisted["deliverables"]
                if assisted.get("success_criteria"):
                    success_criteria = assisted["success_criteria"]
                if assisted.get("constraints"):
                    constraints = self._merge_unique(constraints, assisted["constraints"])
                if assisted.get("required_resources"):
                    resources = self._merge_unique(resources, assisted["required_resources"])
                if isinstance(assisted.get("estimated_steps"), int):
                    estimated_steps = max(1, min(12, assisted["estimated_steps"]))
                if isinstance(assisted.get("estimated_tool_calls"), int):
                    estimated_tool_calls = max(1, min(5, assisted["estimated_tool_calls"]))
                if isinstance(assisted.get("falsifiable"), bool):
                    falsifiable = assisted["falsifiable"]

        task_spec = TaskSpecification(
            task_id=f"SPEC-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            goal=goal,
            success_criteria=success_criteria,
            deliverables=deliverables,
            constraints=constraints,
            required_resources=resources,
            estimated_steps=estimated_steps,
            estimated_tool_calls=estimated_tool_calls,
            falsifiable=falsifiable,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        return task_spec

    def _identify_deliverables(self, goal: str) -> List[str]:
        """Extract concrete deliverables from goal"""
        deliverables = []

        if "summary" in goal.lower() or "research" in goal.lower():
            deliverables.append("Research summary document with citations")

        if "create" in goal.lower() or "generate" in goal.lower():
            deliverables.append("Generated content artifact")

        if "code" in goal.lower() or "script" in goal.lower():
            deliverables.append("Executable code with documentation")

        if "analyze" in goal.lower():
            deliverables.append("Analysis document with findings")

        if not deliverables:
            deliverables.append("Structured response to query")

        return deliverables

    def _define_success_criteria(self, goal: str, deliverables: List[str]) -> List[str]:
        """Define how we'll know if task succeeded"""
        criteria = []

        # Canon fidelity
        criteria.append("Output aligns with Canon values and constraints")

        # Deliverable-specific
        if any("research" in d.lower() for d in deliverables):
            criteria.append("All claims supported by cited sources")
            criteria.append("Sources are from trusted, verifiable origins")

        if any("code" in d.lower() for d in deliverables):
            criteria.append("Code executes without errors")
            criteria.append("Documentation explains purpose and usage")

        # Universal
        criteria.append("Goal statement fully addressed")
        criteria.append("No hallucinations or unsupported claims")

        return criteria

    def _extract_constraints(self, goal: str, context: Optional[Dict]) -> List[str]:
        """Identify constraints from Canon and context"""
        constraints = [
            "Must respect all Canon invariants",
            "No actions requiring human approval without escalation",
            "All external information must be sourced",
        ]

        # Add budget constraints
        constraints.append("Maximum 12 execution steps")
        constraints.append("Maximum 5 tool calls")

        # Context-specific constraints
        if context and "time_limit" in context:
            constraints.append(f"Must complete within {context['time_limit']}")

        return constraints

    def _identify_required_resources(self, goal: str) -> List[str]:
        """Determine what resources/tools are needed"""
        resources = []

        if "research" in goal.lower() or "find" in goal.lower():
            resources.append("project_knowledge_search")
            resources.append("web_search")

        if "code" in goal.lower() or "script" in goal.lower():
            resources.append("bash_tool")
            resources.append("create_file")

        if "document" in goal.lower() or "write" in goal.lower():
            resources.append("create_file")

        return resources

    def _estimate_steps(self, goal: str, deliverables: List[str]) -> int:
        """Estimate execution steps needed"""
        base_steps = 3  # planning, execution, review

        # Add steps for complexity
        if "research" in goal.lower():
            base_steps += 2  # search + source review

        if "code" in goal.lower():
            base_steps += 2  # write + test

        if len(deliverables) > 1:
            base_steps += len(deliverables)

        return min(base_steps, 12)  # Cap at budget

    def _estimate_tool_calls(self, goal: str, resources: List[str]) -> int:
        """Estimate tool usage"""
        # Minimum 1 tool call per resource type
        estimated = len(set(resources))

        # Add buffer for complex tasks
        if "comprehensive" in goal.lower() or "detailed" in goal.lower():
            estimated += 2

        return min(estimated, 5)  # Cap at budget

    def _check_falsifiability(self, success_criteria: List[str]) -> bool:
        """Verify criteria are measurable/falsifiable"""
        # Check if criteria are concrete
        vague_terms = ["good", "better", "quality", "nice", "appropriate"]

        for criterion in success_criteria:
            if any(vague in criterion.lower() for vague in vague_terms):
                return False

        # All criteria should be specific
        return len(success_criteria) > 0

    def _model_assisted_fields(self, goal: str, context: Optional[Dict]) -> Optional[Dict[str, Any]]:
        if not self.model_router:
            return None
        model = self.model_router.get_model("planning")
        if not model:
            return None

        prompt = "\n".join(
            [
                "Create a bounded task plan as strict JSON only.",
                "Do not include markdown code fences.",
                "Use this JSON schema:",
                '{"deliverables":[str], "success_criteria":[str], "constraints":[str], '
                '"required_resources":[str], "estimated_steps":int, '
                '"estimated_tool_calls":int, "falsifiable":bool}',
                "",
                f"Goal: {goal}",
                f"Context: {json.dumps(context or {}, ensure_ascii=True)}",
            ]
        )
        try:
            response = model.generate(prompt=prompt)
        except Exception as exc:
            log(f"Planner model assist unavailable: {exc}", level="WARNING")
            return None

        parsed = self._extract_json_dict(response.text)
        if not parsed:
            return None
        return {
            "deliverables": self._coerce_str_list(parsed.get("deliverables")),
            "success_criteria": self._coerce_str_list(parsed.get("success_criteria")),
            "constraints": self._coerce_str_list(parsed.get("constraints")),
            "required_resources": self._coerce_str_list(parsed.get("required_resources")),
            "estimated_steps": self._coerce_int(parsed.get("estimated_steps")),
            "estimated_tool_calls": self._coerce_int(parsed.get("estimated_tool_calls")),
            "falsifiable": parsed.get("falsifiable") if isinstance(parsed.get("falsifiable"), bool) else None,
        }

    def _extract_json_dict(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
        candidate = match.group(1) if match else text.strip()
        if not match:
            obj_match = re.search(r"(\{.*\})", candidate, re.DOTALL)
            candidate = obj_match.group(1) if obj_match else candidate
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    def _coerce_str_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _coerce_int(self, value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _merge_unique(self, base: List[str], extra: List[str]) -> List[str]:
        seen = set()
        merged: List[str] = []
        for item in [*base, *extra]:
            if item in seen:
                continue
            seen.add(item)
            merged.append(item)
        return merged


# Example usage
if __name__ == "__main__":
    # Load canon
    import yaml

    with open("canon/base_canon.yaml", "r") as f:
        canon = yaml.safe_load(f)

    planner = PlannerAgent(canon)

    # Test plan creation
    goal = "Research recent AI governance frameworks and create a comprehensive summary"

    spec = planner.create_plan(goal)

    print("📋 TASK SPECIFICATION")
    print("=" * 60)
    print(f"Goal: {spec.goal}")
    print("\nDeliverables:")
    for d in spec.deliverables:
        print(f"  - {d}")
    print("\nSuccess Criteria:")
    for c in spec.success_criteria:
        print(f"  - {c}")
    print("\nEstimates:")
    print(f"  Steps: {spec.estimated_steps}")
    print(f"  Tool Calls: {spec.estimated_tool_calls}")
    print(f"  Falsifiable: {spec.falsifiable}")
