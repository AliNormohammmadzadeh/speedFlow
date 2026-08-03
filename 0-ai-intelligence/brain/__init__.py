"""SpeedFlow Brain — an agentic hierarchical planner.

The Brain turns a high-level objective into a hierarchy of
phases -> tasks -> steps, resolves the variables/configs each step needs, then
executes the plan step-by-step. After **every** step it runs a verifier that
examines the step's output and confirms it worked before the next step runs.

Public API:
    HierarchicalPlanner  - decompose an objective + resolve variables/configs
    StepVerifier         - examine a single step's result
    PlanExecutor         - run a plan step-by-step with per-step verification
    build_orchestrator_handlers - wire step actions to the live agent swarm
"""

from .executor import ExecutionContext, PlanExecutor
from .handlers import build_orchestrator_handlers
from .models import (
    ExecutionReport,
    HierarchicalPlan,
    PlanPhase,
    PlanStep,
    PlanTask,
    StepResult,
    VerificationCheck,
    VerificationResult,
)
from .planner import HierarchicalPlanner
from .verifier import StepVerifier

__all__ = [
    "HierarchicalPlanner",
    "StepVerifier",
    "PlanExecutor",
    "ExecutionContext",
    "build_orchestrator_handlers",
    "HierarchicalPlan",
    "PlanPhase",
    "PlanTask",
    "PlanStep",
    "StepResult",
    "ExecutionReport",
    "VerificationCheck",
    "VerificationResult",
]
