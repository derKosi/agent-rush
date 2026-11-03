#!/usr/bin/env python3
"""Tests for the orchestrator foundation that need no VM and no Docker.

Run:  python3 tests/test_sandbox.py

Not pytest, on purpose: the VM has python3 and nothing else until the venv exists,
and a test suite that needs an install is a test suite that does not run.
"""

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator.run_store import RunStore, RunStoreError  # noqa: E402
from orchestrator.sandbox import run_package, SandboxError  # noqa: E402

STUB = REPO / "tests" / "stub_sandbox.sh"
FIXTURE = REPO / "fixtures" / "sample_pkg-0.1.0.tar.gz"

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, exc))
        print(f"  FAIL  {name}: {exc}")
        traceback.print_exc(limit=2)


def test_store_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        rid = store.new_id()
        rec = store.create(rid, {"task": "triage"})
        assert rec["state"] == "queued", rec
        store.update(rid, state="running")
        store.update(rid, state="done", verdict="high")
        final = store.read(rid)
        assert final["state"] == "done" and final["verdict"] == "high", final
        assert len(store.list()) == 1
        try:
            store.update(rid, state="nonsense")
        except RunStoreError:
            pass
        else:
            raise AssertionError("invalid state was accepted")


def test_store_rejects_traversal():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        rid = store.new_id()
        store.create(rid)
        for bad in ("../../etc/passwd", "..", "", "a/b"):
            try:
                store.artifact_path(rid, bad)
            except RunStoreError:
                continue
            raise AssertionError(f"traversal accepted: {bad!r}")


def test_store_rejects_bad_id():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        for bad in ("../x", "a b", "short", ""):
            try:
                store.dir_for(bad)
            except RunStoreError:
                continue
            raise AssertionError(f"bad id accepted: {bad!r}")


def _run_stub(egress_mode="none"):
    tmp = tempfile.mkdtemp(prefix="ar-test-")
    store = RunStore(Path(tmp) / "runs")
    rid = store.new_id()
    store.create(rid)
    run_dir = store.dir_for(rid)
    pkg = FIXTURE if FIXTURE.exists() else _dummy_package(Path(tmp))
    os.environ["AR_SANDBOX_CMD"] = str(STUB)
    try:
        result = run_package(pkg, run_dir, task_id=rid, egress_mode=egress_mode,
                             timeout_s=10)
    finally:
        os.environ.pop("AR_SANDBOX_CMD", None)
    return result, run_dir


def _dummy_package(tmp: Path) -> Path:
    p = tmp / "dummy.tar.gz"
    p.write_bytes(b"not really a package")
    return p


def test_run_collects_artifacts():
    result, run_dir = _run_stub()
    names = set(result["artifacts"])
    assert {"exec.json", "pip.log"} <= names, names
    assert result["exit_code"] == 0, result
    assert result["timed_out"] is False
    assert result["evidence"]["pip_exit"] == 1, result["evidence"]
    for name, meta in result["artifacts"].items():
        assert meta["bytes"] > 0, (name, meta)
        assert len(meta["sha256"]) == 64, (name, meta)
    assert (run_dir / "artifacts" / "exec.json").is_file()


def test_run_in_proxy_mode_collects_egress():
    result, run_dir = _run_stub(egress_mode="proxy")
    assert "egress.jsonl" in result["artifacts"], result["artifacts"]
    log = run_dir / "artifacts" / "egress.jsonl"
    entries = [json.loads(line) for line in log.read_text().splitlines() if line.strip()]
    assert entries, "egress log is empty"
    assert entries[0]["decision"] == "deny", entries[0]
    assert entries[0]["host"] == "collector.invalid", entries[0]


def test_missing_package_is_an_error():
    with tempfile.TemporaryDirectory() as tmp:
        store = RunStore(tmp)
        rid = store.new_id()
        store.create(rid)
        try:
            run_package(Path(tmp) / "nope.tar.gz", store.dir_for(rid), task_id=rid)
        except SandboxError:
            return
        raise AssertionError("missing package did not raise")


def test_result_is_json_serialisable():
    result, _ = _run_stub()
    json.dumps(result)  # raises if anything non-primitive slipped in


def main() -> int:
    print(f"repo: {REPO}")
    if not STUB.exists():
        print(f"stub missing: {STUB}", file=sys.stderr)
        return 2
    print("run store")
    check("lifecycle", test_store_lifecycle)
    check("traversal rejected", test_store_rejects_traversal)
    check("bad id rejected", test_store_rejects_bad_id)
    print("sandbox wrapper")
    check("artifacts collected", test_run_collects_artifacts)
    check("egress collected", test_run_in_proxy_mode_collects_egress)
    check("missing package raises", test_missing_package_is_an_error)
    check("json serialisable", test_result_is_json_serialisable)

    failed = [n for n, e in results if e]
    print()
    print(f"{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
