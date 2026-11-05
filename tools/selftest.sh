#!/usr/bin/env bash
# One command that answers "is this still working?" — for cron, or before a demo.
#
#   bash tools/selftest.sh                      # unit suites only
#   bash tools/selftest.sh http://127.0.0.1:8080   # suites + three real runs
#
# Exit 0 all green, 1 something failed. Output is one line per check, so a log stays readable.
set -uo pipefail

BASE="${1:-}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HERE/.venv/bin/python"
[ -x "$PY" ] || PY=python3
FAILED=0

say() { printf '%-34s %s\n' "$1" "$2"; }

run_suite() {
  local name="$1" cmd="$2"
  local out
  out=$(cd "$HERE" && eval "$cmd" 2>&1 | tail -1)
  if echo "$out" | grep -qE '[0-9]+/[0-9]+ ok' && ! echo "$out" | grep -qE '^[0-9]+/([0-9]+) ok' ; then :; fi
  if echo "$out" | grep -qE '^([0-9]+)/\1 ok$'; then
    say "$name" "$out"
  else
    say "$name" "FAILED — $out"
    FAILED=1
  fi
}

echo "== unit suites"
run_suite "verdict"    "python3 tests/test_verdict.py"
run_suite "planner"    "python3 tests/test_planner.py"
run_suite "guard"      "python3 tests/test_guard.py"
run_suite "recovery"   "python3 tests/test_recovery.py"
run_suite "deps"       "python3 tests/test_deps.py"
run_suite "runtime"    "python3 tests/test_runtime.py"
run_suite "reputation" "python3 tests/test_reputation.py"
run_suite "sarif"      "python3 tests/test_sarif.py"
run_suite "sandbox"    "python3 tests/test_sandbox.py"
run_suite "batch"      "$PY tests/test_batch.py"
run_suite "api"        "$PY tests/test_api.py"

if [ -n "$BASE" ]; then
  echo
  echo "== three real runs against $BASE"
  if ! "$PY" "$HERE/tools/story.py" "$BASE"; then
    FAILED=1
  fi
fi

echo
if [ "$FAILED" -eq 0 ]; then echo "selftest: ok"; else echo "selftest: FAILED"; fi
exit "$FAILED"
