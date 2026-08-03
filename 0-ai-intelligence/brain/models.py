"""Data models for the SpeedFlow Brain (hierarchical planner)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------- #
# Plan structure: Objective -> Phase -> Task -> Step
# --------------------------------------------------------------------------- #
@dataclass
class PlanStep:
    """A single executable unit of work with its resolved config + checks."""

    name: str
    action: str
    id: str = field(default_factory=lambda: _uid("step"))
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    verify: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "action": self.action,
            "description": self.description,
            "config": self.config,
            "verify": self.verify,
        }


@dataclass
class PlanTask:
    name: str
    id: str = field(default_factory=lambda: _uid("task"))
    description: str = ""
    steps: list[PlanStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class PlanPhase:
    name: str
    id: str = field(default_factory=lambda: _uid("phase"))
    description: str = ""
    tasks: list[PlanTask] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
        }


@dataclass
class HierarchicalPlan:
    objective: str
    id: str = field(default_factory=lambda: _uid("plan"))
    goal: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    phases: list[PlanPhase] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def iter_steps(self):
        """Yield (phase, task, step) tuples in execution order."""
        for phase in self.phases:
            for task in phase.tasks:
                for step in task.steps:
                    yield phase, task, step

    @property
    def step_count(self) -> int:
        return sum(len(t.steps) for p in self.phases for t in p.tasks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objective": self.objective,
            "goal": self.goal,
            "variables": self.variables,
            "phases": [p.to_dict() for p in self.phases],
            "metadata": self.metadata,
            "step_count": self.step_count,
        }


# --------------------------------------------------------------------------- #
# Verification + execution results
# --------------------------------------------------------------------------- #
@dataclass
class VerificationCheck:
    kind: str
    target: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass
class VerificationResult:
    passed: bool
    checks: list[VerificationCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"passed": self.passed, "checks": [c.to_dict() for c in self.checks]}


@dataclass
class StepResult:
    step_id: str
    step_name: str
    phase: str
    task: str
    action: str
    status: str  # "passed" | "failed" | "skipped"
    output: Any = None
    verification: VerificationResult | None = None
    error: str = ""
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "phase": self.phase,
            "task": self.task,
            "action": self.action,
            "status": self.status,
            "output": _safe(self.output),
            "verification": self.verification.to_dict() if self.verification else None,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class ExecutionReport:
    objective: str
    plan_id: str
    success: bool
    steps: list[StepResult] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)
    started_at: str = ""
    finished_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "plan_id": self.plan_id,
            "success": self.success,
            "summary": self.summary,
            "variables": self.variables,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "metadata": self.metadata,
            "steps": [s.to_dict() for s in self.steps],
        }


def _safe(value: Any) -> Any:
    """Best-effort JSON-safe rendering of a step output for API responses."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in list(value.items())[:50]}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in list(value)[:50]]
    return str(value)
