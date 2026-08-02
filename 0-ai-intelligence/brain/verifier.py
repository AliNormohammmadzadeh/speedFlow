"""Step verifier — examines a single step's result before the plan proceeds.

Each plan step carries a list of declarative ``verify`` specs. After a step
runs, the executor asks the verifier to examine the step's output against those
specs. A step is only considered successful when every check passes, which is
how the Brain guarantees "check every step after each step is working well".

Supported check kinds (all config-driven):
    config_present   target key resolves to a non-None value
    nonempty         target resolves to a non-empty list/dict/str
    truthy           bool(target) is True
    equals           target == value
    range            min <= number(target) <= max
    status_up        target (default "status") is one of the healthy values
    type_is          type(target).__name__ == value
"""

from __future__ import annotations

from typing import Any

from .models import VerificationCheck, VerificationResult

_HEALTHY = {"up", "ok", "healthy", "ready", "passed", "true", "registered", "queued"}
_MISSING = object()


class StepVerifier:
    def verify(self, verify_specs: list[dict], output: Any, config: dict, context: dict | None = None) -> VerificationResult:
        context = context or {}
        checks: list[VerificationCheck] = []
        for spec in verify_specs or []:
            checks.append(self._run_check(spec, output, config, context))
        passed = all(c.passed for c in checks)
        return VerificationResult(passed=passed, checks=checks)

    # ------------------------------------------------------------------ #
    def _run_check(self, spec: dict, output: Any, config: dict, context: dict) -> VerificationCheck:
        kind = str(spec.get("kind", "truthy"))
        target = str(spec.get("target", ""))
        value = self._resolve(target, output, config, context)

        try:
            if kind == "config_present":
                ok = value is not _MISSING and value is not None
                detail = "present" if ok else "missing"
            elif kind == "nonempty":
                ok = value not in (_MISSING, None) and len(value) > 0  # type: ignore[arg-type]
                detail = f"len={0 if value in (_MISSING, None) else _safe_len(value)}"
            elif kind == "truthy":
                ok = bool(value) and value is not _MISSING
                detail = f"value={_short(value)}"
            elif kind == "equals":
                expected = spec.get("value")
                ok = value == expected
                detail = f"{_short(value)} == {_short(expected)}"
            elif kind == "range":
                num = _to_float(value)
                lo = _to_float(spec.get("min", float("-inf")))
                hi = _to_float(spec.get("max", float("inf")))
                ok = num is not None and lo <= num <= hi
                detail = f"{num} in [{spec.get('min', '-inf')}, {spec.get('max', 'inf')}]"
            elif kind == "status_up":
                sval = value if target else _resolve_status(output)
                sval_str = str(sval).lower()
                ok = sval_str in _HEALTHY
                detail = f"status={sval_str}"
            elif kind == "type_is":
                ok = type(value).__name__ == spec.get("value")
                detail = f"type={type(value).__name__}"
            else:
                ok = False
                detail = f"unknown check kind '{kind}'"
        except Exception as exc:  # never let a bad spec crash a run
            ok = False
            detail = f"check error: {exc}"

        return VerificationCheck(kind=kind, target=target or "status", passed=bool(ok), detail=detail)

    # ------------------------------------------------------------------ #
    def _resolve(self, target: str, output: Any, config: dict, context: dict):
        """Resolve a dotted target from output (default), config.*, or context.*."""
        if not target:
            return output
        root: Any
        path = target
        if target.startswith("output."):
            root, path = output, target[len("output."):]
        elif target.startswith("config."):
            root, path = config, target[len("config."):]
        elif target.startswith("context."):
            root, path = context, target[len("context."):]
        else:
            root = output
        cur = root
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            elif isinstance(cur, (list, tuple)) and part.isdigit() and int(part) < len(cur):
                cur = cur[int(part)]
            else:
                return _MISSING
        return cur


def _resolve_status(output: Any):
    if isinstance(output, dict):
        for key in ("status", "state", "health"):
            if key in output:
                return output[key]
    return output


def _safe_len(value: Any) -> int:
    try:
        return len(value)
    except TypeError:
        return 0


def _to_float(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _short(value: Any) -> str:
    s = str(value)
    return s if len(s) <= 40 else s[:37] + "..."
