#!/usr/bin/env bash
# One-shot verification of a freshly bootstrapped VM.
#
#   ssh root@<ip> 'bash -s' < deploy/check-vm.sh
#   # or, with the repo already cloned:
#   sudo bash deploy/check-vm.sh
#
# Prints PASS/FAIL per check and exits non-zero if anything failed. Runs no
# destructive command; hello-world is the only container it starts.
set -u

PASS=0; FAIL=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS+1)); }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL+1)); }
info() { printf '        %s\n' "$1"; }

echo "== system"
. /etc/os-release 2>/dev/null || true
info "${PRETTY_NAME:-unknown}  kernel $(uname -r)"
info "memory $(free -h 2>/dev/null | awk '/^Mem:/{print $2}')  disk $(df -h / | awk 'NR==2{print $4" frei"}')"

echo "== docker"
if command -v docker >/dev/null 2>&1; then
  ok "docker installed ($(docker --version | cut -d, -f1))"
  if docker run --rm hello-world >/dev/null 2>&1; then
    ok "docker can start a container"
  else
    bad "docker run hello-world failed"
    info "try: systemctl status docker; journalctl -u docker -n 20"
  fi
  if docker info 2>/dev/null | grep -qi 'no-new-privileges'; then
    ok "daemon has no-new-privileges"
  else
    info "daemon.json no-new-privileges not active (not fatal, run.sh sets it per container)"
  fi
else
  bad "docker missing"
  info "apt-get install -y docker.io && systemctl enable --now docker"
fi

echo "== sandbox prerequisites"
for pkg in git python3 curl ufw; do
  command -v "$pkg" >/dev/null 2>&1 && ok "$pkg present" || bad "$pkg missing"
done
if [ -c /dev/fuse ]; then ok "/dev/fuse present (gVisor/runsc possible)"; else info "/dev/fuse absent (Docker only)"; fi

echo "== users and groups"
if id arrush >/dev/null 2>&1; then
  ok "user arrush exists"
  if id -nG arrush 2>/dev/null | tr ' ' '\n' | grep -qx docker; then
    ok "arrush is in the docker group"
  else
    bad "arrush is NOT in the docker group"
    info "usermod -aG docker arrush  (then re-login)"
  fi
else
  bad "user arrush missing"
fi

echo "== firewall"
if ufw status 2>/dev/null | grep -q 'Status: active'; then
  ok "ufw active"
  for port in 22 80 443; do
    ufw status | grep -qE "^${port}(/tcp)?[[:space:]]+ALLOW" && ok "port $port allowed" \
      || bad "port $port not allowed"
  done
  if ufw status | grep -qE '^(8080|8899)[/ ]'; then
    bad "8080/8899 is open to the world -- close it"
  else
    ok "app and proxy ports not exposed"
  fi
else
  bad "ufw not active"
  info "ufw allow 22/tcp 80/tcp 443/tcp && ufw --force enable"
fi

echo "== caddy"
if command -v caddy >/dev/null 2>&1; then
  ok "caddy installed"
  if [ -f /etc/caddy/Caddyfile ]; then
    if caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
      ok "Caddyfile valid"
    else
      bad "Caddyfile invalid"
      info "caddy validate --config /etc/caddy/Caddyfile"
    fi
  else
    info "no Caddyfile yet (deploy/install-service.sh installs it)"
  fi
  systemctl is-active --quiet caddy && ok "caddy running" || bad "caddy not running"
else
  bad "caddy missing"
fi

echo
echo "----"
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
