#!/usr/bin/env bash
# One command from your laptop: fresh VM -> first real container run.
#
#   bash deploy/remote-setup.sh root@203.0.113.10
#
# Assumes the instance exists and cloud-init finished (docs/runbook.md step 1).
# Stops at the first failed gate instead of continuing into a broken state.
set -euo pipefail

TARGET="${1:?usage: remote-setup.sh root@<ip>}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_DIR="/opt/agent-rush"

say() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

say "1/5  sync repo to $TARGET:$REMOTE_DIR"
# No --delete: a stale file on the VM is harmless, a deleted .env is not.
rsync -az \
  --exclude '.git' --exclude '.venv' --exclude 'work' \
  --exclude '*.tar.gz' --exclude '.env' \
  "$REPO/" "$TARGET:$REMOTE_DIR/"
echo "ok"

say "2/5  verify the bootstrap"
if ! ssh "$TARGET" 'bash /opt/agent-rush/deploy/check-vm.sh'; then
  echo
  echo "check-vm failed. Fix the FAIL lines above, then rerun this script." >&2
  echo "The messages name the exact command for each failure." >&2
  exit 1
fi

say "3/5  install service and reverse proxy"
ssh "$TARGET" 'bash /opt/agent-rush/deploy/install-service.sh'

say "4/5  build the sandbox image"
ssh "$TARGET" 'bash /opt/agent-rush/deploy/build_and_push.sh'

say "5/5  first real run (this is the milestone)"
ssh "$TARGET" 'cd /opt/agent-rush && bash fixtures/make_fixture.sh >/dev/null && \
  bash sandbox/run.sh fixtures/sample_pkg-0.1.0.tar.gz firstrun'

say "evidence"
ssh "$TARGET" 'cd /opt/agent-rush && \
  echo "--- docker ps ---" && docker ps -a --filter name=ar-task --format "{{.Names}} {{.Status}}" ; \
  echo "--- container left over? (empty is correct) ---" ; \
  find /tmp -maxdepth 1 -name "ar-sandbox-*" -type d 2>/dev/null | head -3 ; \
  echo "--- last run artifacts ---" ; \
  ls -la $(ls -dt /tmp/ar-sandbox-* 2>/dev/null | head -1)/out 2>/dev/null || echo "(no work dir found)"'

echo
echo "done. If the run above printed \"evidence\" with exec.json, the sandbox works."
echo "next: put AR_VULTR_KEY into $REMOTE_DIR/.env, then models/smoke_test.py --list"
