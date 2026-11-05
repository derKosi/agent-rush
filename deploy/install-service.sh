#!/usr/bin/env bash
# Installs the systemd unit and the reverse proxy config on the VM.
# Run as root (or with sudo) after the repo is cloned to /opt/agent-rush.
#
#   sudo bash deploy/install-service.sh
#
# Does NOT start the app: api/ does not exist yet on day 1. It enables the unit so
# `systemctl start agent-rush` works the moment the first endpoint is written.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/agent-rush}"

[ "$(id -u)" -eq 0 ] || { echo "run as root: sudo bash $0" >&2; exit 2; }
[ -d "$REPO_DIR" ] || { echo "missing $REPO_DIR -- clone the repo there first" >&2; exit 2; }

echo "== user and dirs"
id -u arrush >/dev/null 2>&1 || useradd -m -s /bin/bash arrush
usermod -aG docker arrush
install -d -o arrush -g arrush -m 0755 "$REPO_DIR" "$REPO_DIR/work"
# rsync from a laptop leaves files owned by whoever ran it. Without this the
# service starts, cannot read api/main.py, and systemd loops on exit-code 1.
chown -R arrush:arrush "$REPO_DIR"
chmod -R u+rwX,go+rX "$REPO_DIR"
[ -f "$REPO_DIR/.env" ] && chmod 600 "$REPO_DIR/.env"

echo "== systemd unit"
install -m 0644 "$REPO_DIR/deploy/agent-rush.service" /etc/systemd/system/agent-rush.service
systemctl daemon-reload
systemctl enable agent-rush.service

echo "== caddy"
install -m 0644 "$REPO_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
install -d -o caddy -g caddy -m 0755 /var/log/caddy
caddy validate --config /etc/caddy/Caddyfile
systemctl enable caddy
systemctl reload-or-restart caddy

echo "== venv (deps are installed during the event, when api/ exists)"
if [ ! -x "$REPO_DIR/.venv/bin/python" ]; then
  python3 -m venv "$REPO_DIR/.venv"
  "$REPO_DIR/.venv/bin/pip" install -q --upgrade pip
fi
chown -R arrush:arrush "$REPO_DIR/.venv" 2>/dev/null || true

echo
echo "done. next:"
echo "  sudo -u arrush cp $REPO_DIR/.env.example $REPO_DIR/.env && chmod 600 $REPO_DIR/.env"
echo "  sudo -u arrush bash $REPO_DIR/deploy/build_and_push.sh"
echo "  systemctl status agent-rush   # fails until api/main.py exists -- expected"
