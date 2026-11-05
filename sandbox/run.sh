#!/usr/bin/env bash
# The containment policy as executable flags. If a claim in the README is not
# visible in this file, treat the claim as unproven.
#
# usage:  bash sandbox/run.sh fixtures/sample_pkg-0.1.0.tar.gz [task-id]
#         bash sandbox/run.sh --dry-run fixtures/sample_pkg-0.1.0.tar.gz
#
# Modes (AR_EGRESS_MODE):
#   none   --network none. Tightest. Attempts surface as socket errors.      (default)
#   proxy  internal network + dual-homed deny proxy. Attempts surface as
#          403 lines in the proxy log, with the attempted URL. Preferred for
#          the demo because the evidence is legible. Unverified until the VM exists.

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then DRY_RUN=1; shift; fi

PKG="${1:?usage: run.sh [--dry-run] <package.tar.gz> [task-id]}"
TASK_ID="${2:-$(date -u +%Y%m%dT%H%M%SZ)}"
IMAGE="${AR_IMAGE:-ar-sandbox:0.1}"
MODE="${AR_EGRESS_MODE:-none}"
MEM="${AR_MEM:-512m}"
CPUS="${AR_CPUS:-1}"
PIDS="${AR_PIDS:-64}"
TMPFS_MB="${AR_TMPFS_MB:-64}"
TIMEOUT_S="${AR_TIMEOUT_S:-120}"

[ -f "$PKG" ] || { echo "no such package: $PKG" >&2; exit 2; }

WORK="${AR_WORKDIR:-$(mktemp -d -t ar-sandbox-XXXXXX)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$WORK/out"
cp "$PKG" "$WORK/pkg.tar.gz"
chmod 0777 "$WORK" "$WORK/out"   # container runs as uid 10001

# Default: no network. The resolve phase is the single exception, and it is a
# different container with a different job -- see docs/architecture.md.
if [ "${AR_NET:-none}" = "bridge" ]; then
  NET_ARGS=(--network bridge)
else
  NET_ARGS=(--network none)
fi
EXTRA_HOSTS=()
ENV_ARGS=()

if [ "$MODE" = "proxy" ]; then
  NET_NAME="ar-net-${TASK_ID:0:12}"
  PROXY_NAME="ar-proxy-${TASK_ID:0:12}"
  NET_ARGS=(--network "$NET_NAME")
  EXTRA_HOSTS=(--add-host "proxy:${AR_PROXY_IP:-172.30.99.2}")
  ENV_ARGS=(-e "HTTP_PROXY=http://proxy:8899" -e "HTTPS_PROXY=http://proxy:8899" -e "http_proxy=http://proxy:8899" -e "https_proxy=http://proxy:8899")
  SETUP_CMDS=(
    "docker network create --internal --subnet 172.30.99.0/24 $NET_NAME"
    "docker run -d --rm --name $PROXY_NAME --network $NET_NAME --ip ${AR_PROXY_IP:-172.30.99.2} -v \"$HERE/../proxy:/proxy:ro\" -e AR_ALLOW=\"${AR_ALLOW:-}\" -e AR_TASK_ID=$TASK_ID python:3.12-slim python /proxy/deny_proxy.py"
  )
else
  SETUP_CMDS=()
fi

# bash 3.2 (macOS) errors on "${empty[@]}" under set -u, hence the +"..." idiom.
RUN_CMD=(docker run --rm
  --name "ar-task-${TASK_ID:0:12}"
  "${NET_ARGS[@]}"
  ${EXTRA_HOSTS[@]+"${EXTRA_HOSTS[@]}"}
  ${ENV_ARGS[@]+"${ENV_ARGS[@]}"}
  --read-only
  --tmpfs "/tmp:rw,noexec,nosuid,size=${TMPFS_MB}m"
  --user 10001:10001
  # The planner's choice has to reach the process under test, or the plan is decoration.
  -e "AR_PROBES=${AR_PROBES:-}"
  -e "AR_MODE=${AR_MODE:-pip}"
  -e "AR_NET=${AR_NET:-none}"
  --cap-drop ALL
  --security-opt no-new-privileges
  --pids-limit "$PIDS"
  --memory "$MEM" --memory-swap "$MEM"
  --cpus "$CPUS"
  -v "$WORK:/work:rw"
  "$IMAGE")

echo "task=$TASK_ID mode=$MODE work=$WORK" >&2

if [ "$DRY_RUN" = "1" ] || ! command -v docker >/dev/null 2>&1; then
  [ "$DRY_RUN" = "1" ] || echo "docker not found -- falling back to dry run" >&2
  for c in ${SETUP_CMDS[@]+"${SETUP_CMDS[@]}"}; do [ -n "$c" ] && echo "+ $c"; done
  printf '+ '; printf '%q ' "${RUN_CMD[@]}"; printf '\n'
  echo "work dir prepared: $(ls -1 "$WORK")" >&2
  exit 0
fi

for c in ${SETUP_CMDS[@]+"${SETUP_CMDS[@]}"}; do [ -n "$c" ] && bash -c "$c"; done

if [ "$MODE" = "proxy" ]; then
  # Give the proxy a moment to bind before the sandbox starts knocking.
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    docker logs "$PROXY_NAME" 2>&1 | grep -q listening && break
    sleep 0.5
  done
fi

set +e
if command -v timeout >/dev/null 2>&1; then
  timeout --signal=KILL "$TIMEOUT_S" "${RUN_CMD[@]}"
else
  "${RUN_CMD[@]}"
fi
RC=$?
set -e

if [ "$MODE" = "proxy" ]; then
  # The proxy logs to stdout inside its own container. Grab it before the container
  # disappears (--rm), otherwise the only evidence of the attempt is gone.
  LOG_PATH="${AR_PROXY_LOG:-$WORK/egress.jsonl}"
  mkdir -p "$(dirname "$LOG_PATH")"
  docker logs "$PROXY_NAME" > "$LOG_PATH" 2>/dev/null || true
  grep -v '^\[deny-proxy\]' "$LOG_PATH" > "$LOG_PATH.clean" 2>/dev/null || true
  if [ -s "$LOG_PATH.clean" ]; then mv "$LOG_PATH.clean" "$LOG_PATH"; else rm -f "$LOG_PATH.clean"; fi
  docker stop "$PROXY_NAME" >/dev/null 2>&1 || true
  docker network rm "$NET_NAME" >/dev/null 2>&1 || true
  echo "proxy log: $LOG_PATH ($(wc -l < "$LOG_PATH" 2>/dev/null | tr -d ' ') lines)" >&2
fi

echo "--- evidence ---" >&2
for f in exec.json pip.log fsdiff.json; do
  [ -f "$WORK/out/$f" ] && echo "  out/$f ($(wc -c <"$WORK/out/$f") bytes)" >&2
done
[ -f "${AR_PROXY_LOG:-}" ] && echo "  proxy log: $AR_PROXY_LOG" >&2

exit "$RC"
