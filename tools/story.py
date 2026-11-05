#!/usr/bin/env python3
"""The three-act demo, as a check: clean, outdated, vulnerable.

Each case runs for real against a live instance and asserts the risk level, so this
doubles as a smoke test for the whole chain (container, proxy, registry, OSV).
"""

import json
import sys
import time
import urllib.request

CASES = [
    ("clean dependency", "fixtures/sample_pkg_deps-0.1.0.tar.gz", "low"),
    ("outdated dependency", "fixtures/sample_pkg_stale-0.1.0.tar.gz", "low"),
    ("known vulnerability", "fixtures/sample_pkg_vuln-0.1.0.tar.gz", "high"),
]


def submit(base, payload, attempts=8):
    """Submit, but respect the concurrency cap: one run at a time is the policy, so a
    429 right after the previous run finished is expected, not an error."""
    import urllib.error
    for attempt in range(attempts):
        try:
            return post(base, "/tasks", payload)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == attempts - 1:
                raise
            time.sleep(5)
    raise RuntimeError("unreachable")


def post(base, path, payload):
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as resp:
        return json.load(resp)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
    failures = 0
    for label, package, expected in CASES:
        try:
            run_id = submit(base, {"package": package, "egress_mode": "proxy"})["id"]
        except Exception as exc:  # noqa: BLE001
            print(f"  {label:22} FAILED to submit: {exc}")
            failures += 1
            continue
        deadline = time.time() + 300
        record = {}
        while time.time() < deadline:
            record = get(base, f"/runs/{run_id}")
            if record.get("state") in ("done", "failed"):
                break
            time.sleep(2)
        verdict = record.get("verdict") or {}
        risk = verdict.get("risk")
        ok = risk == expected and record.get("state") == "done"
        print(f"  {label:22} risk={str(risk):7} expected={expected:7} {'ok' if ok else 'MISMATCH'}")
        failures += 0 if ok else 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
