#!/bin/bash
# End-to-end check for the SpeedFlow Brain (hierarchical planner).
#   1. Unit suite (planner / verifier / executor) — no services needed.
#   2. Live orchestrator: execute every objective and assert success + that
#      every step was verified.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ORCH="${AI_ORCHESTRATOR_URL:-http://127.0.0.1:8000}"

echo "==> Unit tests (brain planner/verifier/executor)..."
python3 "$ROOT/tests/test_brain.py"

echo ""
echo "==> Live objectives via $ORCH/brain/execute ..."
OBJECTIVES=$(curl -sf "$ORCH/brain/objectives" \
  | python3 -c "import sys,json; print(' '.join(o['objective'] for o in json.load(sys.stdin)['objectives']))")

FAIL=0
for obj in $OBJECTIVES; do
  RESULT=$(curl -sf -X POST "$ORCH/brain/execute" \
    -H 'Content-Type: application/json' \
    -d "{\"objective\":\"$obj\"}")
  echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)['report']
s = d['summary']
ok = d['success'] and s['failed'] == 0 and s['checks'] == s['checks_passed']
print(f\"    {'OK ' if ok else 'FAIL'} {d['objective']}: {s['passed']}/{s['total']} steps, {s['checks_passed']}/{s['checks']} checks\")
sys.exit(0 if ok else 1)
" || FAIL=1
done

echo ""
if [ "$FAIL" -ne 0 ]; then
  echo "Brain E2E FAILED"
  exit 1
fi
echo "Brain E2E OK: all objectives planned, executed, and verified."
