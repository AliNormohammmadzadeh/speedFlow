"""PlanExecutor — runs a hierarchical plan step-by-step with verification.

The executor walks the plan in phase -> task -> step order. For every step it:
  1. looks up a handler for the step's ``action``,
  2. runs the handler (sync or async), passing the resolved config + a shared
     context that accumulates prior step outputs,
  3. asks the ``StepVerifier`` to examine the output against the step's checks,
  4. records a ``StepResult`` (passed / failed) with timing + verification.

If ``stop_on_failure`` is set, the first failing step short-circuits the run and
all remaining steps are marked ``skipped``. The final ``ExecutionReport`` makes
it easy to confirm every part ran and every step was verified.
"""

from __future__ import annotations

import inspect
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .models import ExecutionReport, HierarchicalPlan, StepResult, VerificationResult
from .verifier import StepVerifier

logger = logging.getLogger(__name__)

Handler = Callable[["ExecutionContext", Any], Any]


@dataclass
class ExecutionContext:
    """Shared state threaded through every step of a single plan run."""

    variables: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    deps: dict[str, Any] = field(default_factory=dict)

    def record(self, step: Any, output: Any) -> None:
        self.results[step.id] = output
        self.results[step.name] = output


class PlanExecutor:
    def __init__(
        self,
        handlers: dict[str, Handler] | None = None,
        verifier: StepVerifier | None = None,
    ):
        self.handlers = handlers or {}
        self.verifier = verifier or StepVerifier()

    async def execute(
        self,
        plan: HierarchicalPlan,
        deps: dict[str, Any] | None = None,
        stop_on_failure: bool = False,
    ) -> ExecutionReport:
        ctx = ExecutionContext(variables=dict(plan.variables), deps=deps or {})
        report = ExecutionReport(
            objective=plan.objective,
            plan_id=plan.id,
            success=True,
            variables=ctx.variables,
            started_at=_now(),
            metadata=dict(plan.metadata),
        )

        aborted = False
        for phase, task, step in plan.iter_steps():
            if aborted:
                report.steps.append(
                    StepResult(
                        step_id=step.id, step_name=step.name, phase=phase.name,
                        task=task.name, action=step.action, status="skipped",
                    )
                )
                continue

            result = await self._run_step(phase.name, task.name, step, ctx)
            report.steps.append(result)
            if result.status != "passed":
                report.success = False
                if stop_on_failure:
                    aborted = True

        report.finished_at = _now()
        report.summary = _summarize(report.steps)
        logger.info(
            "Brain executed objective=%s success=%s summary=%s",
            plan.objective, report.success, report.summary,
        )
        return report

    # ------------------------------------------------------------------ #
    async def _run_step(self, phase: str, task: str, step: Any, ctx: ExecutionContext) -> StepResult:
        started = time.perf_counter()
        result = StepResult(
            step_id=step.id, step_name=step.name, phase=phase,
            task=task, action=step.action, status="failed",
        )

        handler = self.handlers.get(step.action)
        if handler is None:
            result.error = f"no handler registered for action '{step.action}'"
            result.duration_ms = (time.perf_counter() - started) * 1000
            return result

        try:
            output = handler(ctx, step)
            if inspect.isawaitable(output):
                output = await output
            result.output = output
            ctx.record(step, output)
        except Exception as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            result.duration_ms = (time.perf_counter() - started) * 1000
            logger.warning("Brain step '%s' raised: %s", step.name, exc)
            return result

        verification: VerificationResult = self.verifier.verify(
            step.verify, output, step.config, ctx.results
        )
        result.verification = verification
        result.status = "passed" if verification.passed else "failed"
        if not verification.passed:
            failed = [c.target for c in verification.checks if not c.passed]
            result.error = f"verification failed: {', '.join(failed)}"
        result.duration_ms = (time.perf_counter() - started) * 1000
        return result


def _summarize(steps: list[StepResult]) -> dict[str, int]:
    summary = {"total": len(steps), "passed": 0, "failed": 0, "skipped": 0, "checks": 0, "checks_passed": 0}
    for s in steps:
        summary[s.status] = summary.get(s.status, 0) + 1
        if s.verification:
            summary["checks"] += len(s.verification.checks)
            summary["checks_passed"] += sum(1 for c in s.verification.checks if c.passed)
    return summary


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
