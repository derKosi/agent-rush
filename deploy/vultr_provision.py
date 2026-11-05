#!/usr/bin/env python3
"""Provision the demo instance through the Vultr API v2.

    set -a; . ./.env; set +a
    python3 deploy/vultr_provision.py            # create
    python3 deploy/vultr_provision.py --list     # what exists?
    python3 deploy/vultr_provision.py --destroy <id>

Idempotent enough for a hackathon: uploads the SSH key only if it is missing, and
refuses to create a second instance with the same label.
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = "https://api.vultr.com/v2"
REGION = os.environ.get("AR_REGION", "fra")
PLAN = os.environ.get("AR_PLAN", "vc2-1c-2gb")
OS_ID = int(os.environ.get("AR_OS_ID", "2284"))          # Ubuntu 24.04 LTS x64
LABEL = os.environ.get("AR_LABEL", "agent-rush-demo")


def _key():
    k = os.environ.get("AR_VULTR_API_KEY", "").strip()
    if not k:
        sys.exit("AR_VULTR_API_KEY is not set (see .env)")
    return k


def api(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as exc:
        sys.exit(f"{method} {path} -> HTTP {exc.code}: {exc.read().decode()[:400]}")


def ensure_ssh_key():
    pub_path = Path.home() / ".ssh" / "id_ed25519.pub"
    if not pub_path.is_file():
        sys.exit(f"no public key at {pub_path}")
    pub = pub_path.read_text().strip()
    for k in api("/ssh-keys").get("ssh_keys", []):
        if k.get("ssh_key", "").strip() == pub:
            print(f"ssh key already registered: {k['id']}")
            return k["id"]
    created = api("/ssh-keys", "POST", {"name": "agent-rush", "ssh_key": pub})
    print(f"ssh key uploaded: {created['ssh_key']['id']}")
    return created["ssh_key"]["id"]


def instance_by_label():
    for i in api("/instances?per_page=200").get("instances", []):
        if i.get("label") == LABEL:
            return i
    return None


def create():
    existing = instance_by_label()
    if existing:
        print(f"already exists: {existing['id']} {existing.get('main_ip')}")
        return existing

    key_id = ensure_ssh_key()
    userdata = base64.b64encode((REPO / "deploy" / "cloud-init.yaml").read_bytes()).decode()
    payload = {
        "region": REGION,
        "plan": PLAN,
        "os_id": OS_ID,
        "label": LABEL,
        "hostname": "agent-rush",
        "sshkey_id": [key_id],
        "userdata": userdata,
        "enable_ipv6": False,
        "backups": "disabled",
        "ddos_protection": False,
    }
    created = api("/instances", "POST", payload)["instance"]
    print(f"created {created['id']} plan={PLAN} region={REGION} os={OS_ID}")

    for _ in range(60):
        time.sleep(5)
        cur = api(f"/instances/{created['id']}")["instance"]
        status, power, ip = cur.get("status"), cur.get("power_status"), cur.get("main_ip")
        print(f"  status={status} power={power} ip={ip}")
        if status == "active" and power == "running" and ip and ip != "0.0.0.0":
            print(f"\nIP={ip}")
            return cur
    sys.exit("instance did not become active in 5 minutes")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        for i in api("/instances?per_page=200").get("instances", []):
            print(f"{i['id']}  {i.get('label'):20} {i.get('main_ip'):16} "
                  f"{i.get('status'):8} {i.get('plan')} {i.get('region')}")
        return
    if len(sys.argv) > 2 and sys.argv[1] == "--destroy":
        api(f"/instances/{sys.argv[2]}", "DELETE")
        print(f"destroyed {sys.argv[2]}")
        return
    create()


if __name__ == "__main__":
    main()
