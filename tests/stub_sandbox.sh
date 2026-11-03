#!/usr/bin/env bash
# Test double for sandbox/run.sh.
#
# Only reachable through AR_SANDBOX_CMD. Nothing in the application sets that
# variable; it exists so the orchestrator can be tested on a machine without Docker.
# If this file ever shows up in a demo run, that run is invalid.
set -euo pipefail

PKG="${1:?usage: stub_sandbox.sh <package> [task-id]}"
TASK_ID="${2:-stub}"
OUT="${AR_WORKDIR:?AR_WORKDIR not set}/out"
mkdir -p "$OUT"

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf 'stub: would run %s as task %s\n' "$PKG" "$TASK_ID" >&2

cat > "$OUT/exec.json" <<EOF
{
  "started": "$NOW",
  "finished": "$NOW",
  "duration_s": 0,
  "pip_exit": 1,
  "artifact": "pip.log",
  "stub": true
}
EOF

printf 'Stub pip output for %s\nERROR: build hook exited 1 (expected for the fixture)\n' "$PKG" > "$OUT/pip.log"

if [ "${AR_EGRESS_MODE:-none}" = "proxy" ]; then
  LOG="${AR_PROXY_LOG:-$OUT/egress.jsonl}"
  mkdir -p "$(dirname "$LOG")"
  cat > "$LOG" <<EOF
{"ts": "$NOW", "task_id": "$TASK_ID", "kind": "connect", "host": "collector.invalid", "port": 80, "decision": "deny", "method": "POST"}
EOF
fi

exit 0
