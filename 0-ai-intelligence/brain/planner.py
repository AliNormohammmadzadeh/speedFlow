"""HierarchicalPlanner — the SpeedFlow "Brain".

Given a named objective, the planner:
  1. loads the objective template (config/brain/objectives.yaml),
  2. resolves the variables/configs the objective needs — clamping them to the
     tenant's subscription plan limits and applying caller overrides
     ("decide variable and configs in there"), then
  3. decomposes the objective into a hierarchy of phases -> tasks -> steps with
     the resolved variables substituted into every step's config.

The planner is pure/deterministic (no side effects); execution + per-step
verification happens in ``PlanExecutor``. An optional LLM pass adds a
human-readable rationale but never changes the plan structure.
"""

from __future__ import annotations

import copy
import logging
import re
from typing import Any, Callable

from shared.utils import llm_complete, load_yaml

from .models import HierarchicalPlan, PlanPhase, PlanStep, PlanTask

logger = logging.getLogger(__name__)

_VAR_RE = re.compile(r"\$\{([a-zA-Z0-9_.]+)\}")


class PlannerError(ValueError):
    """Raised when an objective is unknown or a template is malformed."""


class HierarchicalPlanner:
    name = "brain"

    def __init__(
        self,
        objectives: dict | None = None,
        loader: Callable[[str], dict] = load_yaml,
    ):
        self._loader = loader
        self._objectives_override = objectives

    # ------------------------------------------------------------------ #
    def _objectives(self) -> dict[str, Any]:
        if self._objectives_override is not None:
            return self._objectives_override
        data = self._loader("brain/objectives.yaml") or {}
        return data.get("objectives", {})

    def list_objectives(self) -> list[dict[str, Any]]:
        out = []
        for key, tpl in self._objectives().items():
            out.append(
                {
                    "objective": key,
                    "goal": tpl.get("goal", ""),
                    "phase_count": len(tpl.get("phases", [])),
                    "step_count": sum(
                        len(t.get("steps", []))
                        for p in tpl.get("phases", [])
                        for t in p.get("tasks", [])
                    ),
                    "variables": tpl.get("variables", {}),
                }
            )
        return out

    # ------------------------------------------------------------------ #
    def resolve_variables(self, objective: str, context: dict | None = None) -> dict[str, Any]:
        """Merge template defaults, plan-derived limits, and caller overrides."""
        context = context or {}
        template = self._get_template(objective)
        variables: dict[str, Any] = dict(template.get("variables", {}))

        # Caller may override the plan or any variable directly.
        overrides = dict(context.get("variables", {}))
        plan = context.get("plan") or overrides.get("plan") or variables.get("plan")
        if plan:
            variables["plan"] = plan
        if context.get("vertical"):
            variables["vertical"] = context["vertical"]

        variables.update(overrides)

        # Plan-aware clamping: never let a step exceed the tenant plan's limits.
        limits = self._plan_limits(variables.get("plan"))
        if limits:
            variables["plan_limits"] = limits
            if "max_pages" in variables:
                variables["max_pages"] = min(
                    int(variables["max_pages"]), int(limits.get("max_pages_per_job", variables["max_pages"]))
                )
            if "max_concurrency" in variables:
                variables["max_concurrency"] = min(
                    int(variables["max_concurrency"]),
                    int(limits.get("max_concurrency", variables["max_concurrency"])),
                )
        return variables

    def _plan_limits(self, plan: str | None) -> dict[str, Any]:
        if not plan:
            return {}
        plans = (self._loader("subscriptions/plans.yaml") or {}).get("plans", {})
        return dict(plans.get(plan, {}).get("limits", {}))

    # ------------------------------------------------------------------ #
    async def build_plan(
        self,
        objective: str,
        context: dict | None = None,
        use_llm: bool = True,
    ) -> HierarchicalPlan:
        template = self._get_template(objective)
        variables = self.resolve_variables(objective, context)

        phases: list[PlanPhase] = []
        for p in template.get("phases", []):
            tasks: list[PlanTask] = []
            for t in p.get("tasks", []):
                steps: list[PlanStep] = []
                for s in t.get("steps", []):
                    steps.append(
                        PlanStep(
                            name=s["name"],
                            action=s.get("action", "noop"),
                            description=s.get("description", ""),
                            config=_substitute(copy.deepcopy(s.get("config", {})), variables),
                            verify=_substitute(copy.deepcopy(s.get("verify", [])), variables),
                        )
                    )
                tasks.append(PlanTask(name=t["name"], description=t.get("description", ""), steps=steps))
            phases.append(PlanPhase(name=p["name"], description=p.get("description", ""), tasks=tasks))

        plan = HierarchicalPlan(
            objective=objective,
            goal=template.get("goal", ""),
            variables=variables,
            phases=phases,
            metadata={"resolved_from": "config/brain/objectives.yaml"},
        )

        if use_llm:
            plan.metadata["rationale"] = await self._rationale(plan)

        logger.info(
            "Brain planned objective=%s phases=%d steps=%d",
            objective, len(plan.phases), plan.step_count,
        )
        return plan

    async def _rationale(self, plan: HierarchicalPlan) -> str:
        outline = " | ".join(
            f"{p.name}: {', '.join(t.name for t in p.tasks)}" for p in plan.phases
        )
        prompt = (
            f"Objective: {plan.objective}\nGoal: {plan.goal}\n"
            f"Resolved variables: {plan.variables}\nPlan outline: {outline}\n"
            "In 2-3 sentences, explain why this hierarchical plan achieves the goal."
        )
        try:
            return await llm_complete(prompt, system="You are the planning brain of a data platform.")
        except Exception as exc:  # rationale is best-effort
            logger.warning("brain rationale failed: %s", exc)
            return f"[rule-based] Executes {plan.step_count} verified steps across {len(plan.phases)} phases."

    # ------------------------------------------------------------------ #
    def _get_template(self, objective: str) -> dict[str, Any]:
        objectives = self._objectives()
        if objective not in objectives:
            raise PlannerError(
                f"Unknown objective '{objective}'. Available: {sorted(objectives)}"
            )
        return objectives[objective]


def _substitute(value: Any, variables: dict[str, Any]) -> Any:
    """Recursively substitute ${var} references using resolved variables.

    A string that is exactly ``${name}`` yields the variable's native type
    (e.g. an int stays an int); interpolated strings return substituted text.
    """
    if isinstance(value, dict):
        return {k: _substitute(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, variables) for v in value]
    if isinstance(value, str):
        exact = _VAR_RE.fullmatch(value.strip())
        if exact:
            return _lookup(exact.group(1), variables, default=value)
        return _VAR_RE.sub(lambda m: str(_lookup(m.group(1), variables, default=m.group(0))), value)
    return value


def _lookup(dotted: str, variables: dict[str, Any], default: Any = None) -> Any:
    cur: Any = variables
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur
