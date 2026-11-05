#!/usr/bin/env python3
"""Tests for the HTTP layer, end to end through the stub sandbox.

    .venv/bin/python tests/test_api.py

Needs fastapi + httpx (see docs/runbook.md step 6). Runs no container.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Configure before importing the app: the store path is read at import time.
RUNS = tempfile.mkdtemp(prefix="ar-api-runs-")
os.environ["AR_RUNS_DIR"] = RUNS
os.environ["AR_SANDBOX_CMD"] = str(REPO / "tests" / "stub_sandbox.sh")
os.environ["AR_TIMEOUT_S"] = "20"
os.environ["AR_RATE_PER_HOUR"] = "500"
os.environ["AR_MAX_CONCURRENT"] = "4"
os.environ["AR_API_TOKEN"] = ""
os.environ.pop("AR_VULTR_KEY", None)
os.environ.pop("AR_MODEL", None)

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


def _wait(run_id, seconds=15):
    deadline = time.time() + seconds
    while time.time() < deadline:
        r = client.get(f"/runs/{run_id}")
        assert r.status_code == 200, r.text
        data = r.json()
        if data["state"] in ("done", "failed"):
            return data
        time.sleep(0.1)
    raise AssertionError(f"run {run_id} did not finish in {seconds}s")


def test_health():
    r = client.get("/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["sandbox_override"] is True, body
    assert body["model_configured"] is False, body


def test_task_runs_to_done():
    r = client.post("/tasks", json={"package": "fixtures/sample_pkg-0.1.0.tar.gz",
                                    "question": "safe to install?"})
    assert r.status_code == 202, r.text
    run_id = r.json()["id"]
    data = _wait(run_id)
    assert data["state"] == "done", data
    assert data["verdict"]["risk"] in ("low", "medium", "high"), data["verdict"]
    assert data["verdict"]["model_used"] is False
    assert data["evidence"]["exec"]["pip_exit"] == 1, data["evidence"]
    assert "exec.json" in data["evidence"]["artifacts"]


def test_proxy_mode_records_a_denial():
    r = client.post("/tasks", json={"package": "fixtures/sample_pkg-0.1.0.tar.gz",
                                    "egress_mode": "proxy"})
    assert r.status_code == 202, r.text
    data = _wait(r.json()["id"])
    egress = data["evidence"]["egress"]
    assert egress["collected"] is True, egress
    assert egress["denied"] == 1, egress
    assert data["verdict"]["risk"] == "high", data["verdict"]


def test_artifact_download():
    r = client.post("/tasks", json={"package": "fixtures/sample_pkg-0.1.0.tar.gz"})
    run_id = r.json()["id"]
    _wait(run_id)
    a = client.get(f"/runs/{run_id}/artifacts/exec.json")
    assert a.status_code == 200, a.text
    assert "pip_exit" in a.text


def test_path_outside_roots_is_rejected():
    for bad in ("../README.md", "/etc/passwd", "deploy/Caddyfile"):
        r = client.post("/tasks", json={"package": bad})
        assert r.status_code == 400, (bad, r.status_code, r.text)


def test_artifact_traversal_is_rejected():
    r = client.post("/tasks", json={"package": "fixtures/sample_pkg-0.1.0.tar.gz"})
    run_id = r.json()["id"]
    _wait(run_id)
    for bad in ("..%2F..%2Frun.json", "run.json", "../run.json"):
        a = client.get(f"/runs/{run_id}/artifacts/{bad}")
        assert a.status_code == 404, (bad, a.status_code)


def test_unknown_run_is_404():
    assert client.get("/runs/nope-nope").status_code == 404
    assert client.get("/runs/../../etc/passwd").status_code in (404, 400)


def test_index_is_served():
    r = client.get("/")
    assert r.status_code == 200, r.text
    assert "Agent Rush" in r.text


def main() -> int:
    print(f"runs dir: {RUNS}")
    check("health", test_health)
    check("task runs to done", test_task_runs_to_done)
    check("proxy mode records denial", test_proxy_mode_records_a_denial)
    check("artifact download", test_artifact_download)
    check("path outside roots rejected", test_path_outside_roots_is_rejected)
    check("artifact traversal rejected", test_artifact_traversal_is_rejected)
    check("unknown run is 404", test_unknown_run_is_404)
    check("index served", test_index_is_served)

    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
