"""Tests for the SpeedFlow Brain (hierarchical planner + verifier + executor).

Runnable two ways:
    python3 tests/test_brain.py      # standalone (no pytest needed)
    pytest tests/test_brain.py       # if pytest is installed

The suite exercises the exact guarantee the Brain is built for: every step is
executed and then examined by the verifier before the plan proceeds.
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "0-ai-intelligence"))

from brain import (  # noqa: E402
    HierarchicalPlanner,
    PlanExecutor,
    StepVerifier,
)

# A self-contained objective template so tests never depend on YAML/services.
OBJECTIVES = {
    "demo": {
        "goal": "exercise the brain",
        "variables": {"plan": "starter", "max_pages": 25, "greeting": "hi"},
        "phases": [
            {
                "name": "Plan",
                "tasks": [
                    {
                        "name": "resolve",
                        "steps": [
                            {
                                "name": "resolve-vars",
                                "action": "echo",
                                "config": {"max_pages": "${max_pages}", "note": "pages=${max_pages}"},
                                "verify": [
                                    {"kind": "config_present", "target": "resolved"},
                                    {"kind": "range", "target": "resolved.max_pages", "min": 1, "max": 20},
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "name": "Act",
                "tasks": [
                    {
                        "name": "work",
                        "steps": [
                            {
                                "name": "do-work",
                                "action": "make_list",
                                "verify": [{"kind": "nonempty", "target": "items"}],
                            }
                        ],
                    }
                ],
            },
        ],
    }
}


def _planner() -> HierarchicalPlanner:
    return HierarchicalPlanner(objectives=OBJECTIVES)


# --------------------------------------------------------------------------- #
def test_variable_resolution_clamps_to_plan_limits():
    planner = _planner()
    variables = planner.resolve_variables("demo", {"plan": "starter"})
    # starter plan caps max_pages_per_job at 20, so 25 must clamp to 20.
    assert variables["max_pages"] == 20, variables
    assert variables["plan_limits"]["max_pages_per_job"] == 20


def test_variable_override_applied():
    planner = _planner()
    variables = planner.resolve_variables("demo", {"variables": {"greeting": "yo"}})
    assert variables["greeting"] == "yo"


def test_build_plan_structure_and_substitution():
    planner = _planner()
    plan = asyncio.run(planner.build_plan("demo", {"plan": "starter"}, use_llm=False))
    assert len(plan.phases) == 2
    assert plan.step_count == 2
    step = plan.phases[0].tasks[0].steps[0]
    # exact ${max_pages} keeps its native int type after clamping
    assert step.config["max_pages"] == 20
    # interpolated string is substituted
    assert step.config["note"] == "pages=20"


def test_unknown_objective_raises():
    planner = _planner()
    try:
        asyncio.run(planner.build_plan("nope", use_llm=False))
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown objective")


# --------------------------------------------------------------------------- #
def test_verifier_check_kinds():
    v = StepVerifier()
    out = {"status": "up", "items": [1, 2], "count": 5, "resolved": {"max_pages": 20}}
    specs = [
        {"kind": "status_up", "target": "status"},
        {"kind": "nonempty", "target": "items"},
        {"kind": "range", "target": "count", "min": 1, "max": 10},
        {"kind": "range", "target": "resolved.max_pages", "min": 1, "max": 20},
        {"kind": "equals", "target": "count", "value": 5},
    ]
    result = v.verify(specs, out, config={}, context={})
    assert result.passed, result.to_dict()
    assert len(result.checks) == 5


def test_verifier_detects_failure():
    v = StepVerifier()
    out = {"status": "down", "items": []}
    result = v.verify(
        [{"kind": "status_up", "target": "status"}, {"kind": "nonempty", "target": "items"}],
        out, config={}, context={},
    )
    assert not result.passed
    assert all(not c.passed for c in result.checks)


# --------------------------------------------------------------------------- #
def _executor() -> PlanExecutor:
    def echo(ctx, step):
        return {"status": "ok", "resolved": dict(step.config)}

    def make_list(ctx, step):
        return {"items": ["a", "b", "c"]}

    return PlanExecutor(handlers={"echo": echo, "make_list": make_list})


def test_executor_runs_and_verifies_every_step():
    plan = asyncio.run(_planner().build_plan("demo", {"plan": "starter"}, use_llm=False))
    report = asyncio.run(_executor().execute(plan))
    assert report.success, report.to_dict()
    assert report.summary["total"] == 2
    assert report.summary["passed"] == 2
    # every step carries a verification result
    assert all(s.verification is not None for s in report.steps)
    assert report.summary["checks"] == report.summary["checks_passed"]


def test_executor_stop_on_failure_skips_remaining():
    def boom(ctx, step):
        raise RuntimeError("kaboom")

    def ok(ctx, step):
        return {"items": [1]}

    planner = HierarchicalPlanner(
        objectives={
            "chain": {
                "goal": "",
                "variables": {},
                "phases": [
                    {"name": "P", "tasks": [{"name": "t", "steps": [
                        {"name": "s1", "action": "boom", "verify": []},
                        {"name": "s2", "action": "ok", "verify": [{"kind": "nonempty", "target": "items"}]},
                    ]}]},
                ],
            }
        }
    )
    plan = asyncio.run(planner.build_plan("chain", use_llm=False))
    report = asyncio.run(
        PlanExecutor(handlers={"boom": boom, "ok": ok}).execute(plan, stop_on_failure=True)
    )
    assert not report.success
    assert report.summary["failed"] == 1
    assert report.summary["skipped"] == 1
    assert report.steps[0].status == "failed"
    assert "kaboom" in report.steps[0].error
    assert report.steps[1].status == "skipped"


def test_executor_missing_handler_is_failure():
    planner = HierarchicalPlanner(
        objectives={"x": {"goal": "", "variables": {}, "phases": [
            {"name": "P", "tasks": [{"name": "t", "steps": [
                {"name": "s", "action": "does_not_exist", "verify": []},
            ]}]},
        ]}}
    )
    plan = asyncio.run(planner.build_plan("x", use_llm=False))
    report = asyncio.run(PlanExecutor(handlers={}).execute(plan))
    assert not report.success
    assert "no handler" in report.steps[0].error


# --------------------------------------------------------------------------- #
def _all_tests():
    return [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]


def main() -> int:
    passed = 0
    failed = 0
    for fn in _all_tests():
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {type(exc).__name__}: {exc}")
        else:
            passed += 1
            print(f"PASS {fn.__name__}")
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
