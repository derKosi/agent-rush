#!/bin/sh
# Runs inside the container. Single job: execute the build hook of the package at
# /work/pkg.tar.gz and leave a machine-readable record in /work/out/exec.json.
#
# Deliberately does NOT try to detect anything. Detection would put the observer
# inside the observed. Evidence comes from the proxy log and the host-side fsdiff.

set -eu

export HOME=/tmp/home
mkdir -p "$HOME" /work/out

STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
T0=$(date +%s)

# --no-deps:            the dependency graph is not what we are testing
# --no-build-isolation: the hook must run in this environment, not a network-fetched one
# --no-build-isolation also means the package's setup.py imports happen here, on purpose.
# Mode "script": run a short Python inspection script written by the model. Same
# sandbox, same limits -- model-authored code is still untrusted code.
if [ "${AR_MODE:-pip}" = "script" ]; then
  set +e
  python3 /work/script.py /work/pkg.tar.gz > /work/out/script.log 2>&1
  SCRIPT_EXIT=$?
  set -e
  cat /work/out/script.log
  cat > /work/out/exec.json <<EOF
{
  "started": "$STARTED",
  "finished": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_s": $(( $(date +%s) - T0 )),
  "mode": "script",
  "script_exit": $SCRIPT_EXIT
}
EOF
  exit 0
fi

# Redirect to a file rather than piping through tee: a detached child that inherits
# the pipe would otherwise keep the reader open and hang the run until the timeout.
set +e
pip install \
  --no-deps \
  --no-build-isolation \
  --no-cache-dir \
  --disable-pip-version-check \
  --root-user-action=ignore \
  /work/pkg.tar.gz > /work/out/pip.log 2>&1
PIP_EXIT=$?
set -e

cat /work/out/pip.log

T1=$(date +%s)
FINISHED=$(date -u +%Y-%m-%dT%H:%M:%SZ)

cat > /work/out/exec.json <<EOF
{
  "started": "$STARTED",
  "finished": "$FINISHED",
  "duration_s": $((T1 - T0)),
  "pip_exit": $PIP_EXIT,
  "artifact": "pip.log"
}
EOF

# Exit 0 even when pip fails: a failing install is a finding, not an infrastructure
# error. The orchestrator distinguishes the two by reading pip_exit from exec.json.
exit 0
