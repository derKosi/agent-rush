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
# Mode "import" for node: install, then require each installed top-level package.
if [ "${AR_MODE:-pip}" = "import" ] && [ "${AR_RUNTIME:-python}" = "node" ]; then
  export npm_config_cache=/tmp/npm-cache
  set +e
  npm install --prefix /work/app --no-audit --no-fund --loglevel=warn \
    /work/pkg.tar.gz > /work/out/pip.log 2>&1
  INSTALL_EXIT=$?
  node /usr/local/bin/import_pass.js > /work/out/import.log 2>&1 || true
  set -e
  cat /work/out/pip.log /work/out/import.log
  cat > /work/out/exec.json <<EOF
{
  "started": "$STARTED",
  "finished": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_s": $(( $(date +%s) - T0 )),
  "mode": "import",
  "runtime": "node",
  "install_exit": $INSTALL_EXIT,
  "artifact": "import.log"
}
EOF
  exit 0
fi

# Mode "import": install the package, then import it. A payload that only fires on
# first use never shows up in the build log; this pass is where it shows up.
if [ "${AR_MODE:-pip}" = "import" ]; then
  set +e
  pip install \
    --no-deps --no-build-isolation --no-cache-dir \
    --disable-pip-version-check --root-user-action=ignore \
    /work/pkg.tar.gz > /work/out/pip.log 2>&1
  PIP_EXIT=$?
  python3 /usr/local/bin/import_pass.py > /work/out/import.log 2>&1
  IMPORT_EXIT=$?
  set -e
  cat /work/out/pip.log /work/out/import.log

  cat > /work/out/exec.json <<EOF
{
  "started": "$STARTED",
  "finished": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_s": $(( $(date +%s) - T0 )),
  "mode": "import",
  "pip_exit": $PIP_EXIT,
  "import_exit": $IMPORT_EXIT,
  "artifact": "import.log"
}
EOF
  exit 0
fi

# Mode "resolve": make the dependency tree visible without running any of it.
# Network is on here and only here; pip is told to accept wheels only, because
# resolving an sdist runs its build backend -- which is the thing we are trying to
# avoid. Nothing from the package is imported in this phase.
if [ "${AR_MODE:-pip}" = "resolve" ]; then
  set +e
  if [ -s /work/reqs.txt ]; then
    pip download --only-binary=:all: --no-cache-dir --disable-pip-version-check \
      --dest /work/out/deps --requirement /work/reqs.txt > /work/out/resolve.log 2>&1
    RESOLVE_EXIT=$?
  else
    echo "no declared dependencies" > /work/out/resolve.log
    RESOLVE_EXIT=0
  fi
  set -e
  cat /work/out/resolve.log

  cat > /work/out/exec.json <<EOF
{
  "started": "$STARTED",
  "finished": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_s": $(( $(date +%s) - T0 )),
  "mode": "resolve",
  "resolve_exit": $RESOLVE_EXIT
}
EOF
  exit 0
fi

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

# Node packages run their hook on `npm install`, exactly like setup.py on pip. Same
# container, same limits, same probes -- only the command differs.
if [ "${AR_RUNTIME:-python}" = "node" ]; then
  export npm_config_cache=/tmp/npm-cache
  export npm_config_audit=false
  export npm_config_fund=false
  set +e
  npm install --prefix /work/app --no-audit --no-fund --loglevel=warn \
    /work/pkg.tar.gz > /work/out/install.log 2>&1
  INSTALL_EXIT=$?
  set -e
  cat /work/out/install.log
  cat > /work/out/exec.json <<EOF
{
  "started": "$STARTED",
  "finished": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_s": $(( $(date +%s) - T0 )),
  "mode": "install",
  "runtime": "node",
  "install_exit": $INSTALL_EXIT,
  "artifact": "install.log"
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
