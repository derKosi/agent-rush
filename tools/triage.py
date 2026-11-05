#!/usr/bin/env python3
"""Command-line front door, meant for a pipeline step.

    python3 tools/triage.py fixtures/*.tar.gz --fail-on high
    python3 tools/triage.py pkg.tar.gz --base http://45.77.143.94 --json

Exit codes: 0 clean enough, 1 threshold hit, 2 request/config error.
Nothing here is a workflow file; it is the thing a workflow would call.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

RISK_ORDER = {"none": -1, "low": 0, "medium": 1, "high": 2}


def post(base, path, payload):
    req = urllib.request.Request(base + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def get(base, path):
    with urllib.request.urlopen(base + path, timeout=30) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("packages", nargs="+")
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--fail-on", default="high",
                    choices=["none", "low", "medium", "high"])
    ap.add_argument("--question", default="Is this safe to install on a developer machine?")
    ap.add_argument("--egress-mode", default="proxy", choices=["none", "proxy"])
    ap.add_argument("--json", action="store_true", help="print the raw report")
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    try:
        started = post(args.base, "/batch", {
            "packages": args.packages,
            "question": args.question,
            "egress_mode": args.egress_mode,
            "fail_on": args.fail_on,
        })
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 2

    batch_id = started["id"]
    deadline = time.time() + args.timeout
    record = {}
    while time.time() < deadline:
        record = get(args.base, f"/batches/{batch_id}")
        if record.get("state") in ("done", "failed"):
            break
        time.sleep(2)

    report = get(args.base, f"/batches/{batch_id}/report")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"batch {batch_id}  worst={report['worst']}  fail_on={report['fail_on']}")
        print(f"{'package':34} {'risk':7} findings")
        for item in report["packages"]:
            print(f"{item['package']:34} {str(item['risk']):7} {item['findings']}")
        print("FAILED" if report["failed"] else "passed")

    if report["state"] != "done":
        return 2
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
