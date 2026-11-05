#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu 24.04 VM by hand, over SSH.
#
#   ssh root@<ip> 'bash -s' < deploy/vm-bootstrap.sh
#
# Same end state as deploy/cloud-init.yaml, but does not depend on the provider
# delivering user data. Idempotent: safe to run twice.
set -euo pipefail

echo "== packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq docker.io git python3-venv python3-pip caddy ufw curl coreutils >/dev/null

echo "== services"
systemctl enable --now docker >/dev/null 2>&1
systemctl enable --now caddy >/dev/null 2>&1

echo "== firewall (allow 22 BEFORE enabling, or we lock ourselves out)"
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ufw status | head -5

echo "== user and dirs"
id -u arrush >/dev/null 2>&1 || useradd -m -s /bin/bash arrush
usermod -aG docker arrush
install -d -o arrush -g arrush -m 0755 /opt/agent-rush /opt/agent-rush/work

echo "== ssh hardening"
cat > /etc/ssh/sshd_config.d/99-agent-rush.conf <<'CONF'
PasswordAuthentication no
PermitRootLogin prohibit-password
X11Forwarding no
CONF
systemctl reload ssh

echo "== done"
echo "bootstrap ok $(date -u +%FT%TZ)" | tee /var/log/agent-rush-bootstrap.log
