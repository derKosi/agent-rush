#!/usr/bin/env python3
"""Batch endpoint tests.  .venv/bin/python tests/test_batch.py"""

import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

os.environ["AR_RUNS_DIR"] = tempfile.mkdtemp(prefix="ar-batch-")
os.environ["AR_SANDBOX_CMD"] = str(REPO / "tests" / "stub_sandbox.sh")
os.environ["AR_TIMEOUT_S"] = "20"
os.environ["AR_RATE_PER_HOUR"] = "100"
os.environ["AR_MAX_CONCURRENT"] = "4"
os.environ.pop("AR_VULTR_KEY", None)

from fastapi.testclient import TestClient  # noqa: E402
from api.main import app  # noqa: E402

client = TestClient(app)
results = []


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, exc))
        print(f"  FAIL  {name}: {exc}")


def _wait(batch_id, seconds=20):
    deadline = time.time() + seconds
    while time.time() < deadline:
        r = client.get(f"/batches/{batch_id}")
        assert r.status_code == 200, r.text
        if r.json()["state"] in ("done", "failed"):
            return r.json()
        time.sleep(0.2)
    raise AssertionError("batch did not finish")


def test_batch_runs_all_packages():
    r = client.post("/batch", json={"packages": ["fixtures/sample_pkg-0.1.0.tar.gz",
                                                 "fixtures/sample_pkg_injected-0.1.0.tar.gz"]})
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["packages"] == 2
    rec = _wait(body["id"])
    assert rec["state"] == "done", rec
    assert len(rec["results"]) == 2, rec["results"]
    for item in rec["results"]:
        assert item["run"] and item["state"] == "done", item


def test_report_fails_on_proxy_denials():
    r = client.post("/batch", json={"packages": ["fixtures/sample_pkg-0.1.0.tar.gz"],
                                    "egress_mode": "proxy", "fail_on": "high"})
    _wait(r.json()["id"])
    report = client.get(f"/batches/{r.json()['id']}/report").json()
    assert report["worst"] == "high", report
    assert report["failed"] is True, report


def test_report_passes_when_threshold_is_higher():
    r = client.post("/batch", json={"packages": ["fixtures/sample_pkg-0.1.0.tar.gz"],
                                    "egress_mode": "none", "fail_on": "high"})
    _wait(r.json()["id"])
    report = client.get(f"/batches/{r.json()['id']}/report").json()
    assert report["worst"] in ("low", "medium"), report
    assert report["failed"] is False, report


def test_fail_on_none_never_fails():
    r = client.post("/batch", json={"packages": ["fixtures/sample_pkg-0.1.0.tar.gz"],
                                    "egress_mode": "proxy", "fail_on": "none"})
    _wait(r.json()["id"])
    report = client.get(f"/batches/{r.json()['id']}/report").json()
    assert report["failed"] is False, report


def test_batch_rejects_path_outside_roots():
    r = client.post("/batch", json={"packages": ["../README.md"]})
    assert r.status_code == 400, r.text


def test_unknown_batch_is_404():
    assert client.get("/batches/nope").status_code == 404
    assert client.get("/batches/nope/report").status_code == 404


def main() -> int:
    print("batch")
    check("runs all packages", test_batch_runs_all_packages)
    check("report fails on high", test_report_fails_on_proxy_denials)
    check("report passes below threshold", test_report_passes_when_threshold_is_higher)
    check("fail-on none", test_fail_on_none_never_fails)
    check("path outside roots rejected", test_batch_rejects_path_outside_roots)
    check("unknown batch 404", test_unknown_batch_is_404)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
