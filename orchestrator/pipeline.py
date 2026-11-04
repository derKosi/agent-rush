"""Pipeline: one run, start to verdict. The only place that knows the order.

Kept separate from the API so the whole thing can be exercised from a script
(tests/test_pipeline.py) without starting a web server.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import sandbox
from .verdict import egress_summary, verdict, _read_json


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def collect_evidence(run_dir, result) -> dict:
    """Assemble the evidence object. Every field is read from disk or the result."""
    run_dir = Path(run_dir)
    art = run_dir / "artifacts"

    egress_path = art / "egress.jsonl"
    if not egress_path.is_file():
        egress_path = run_dir / "egress.jsonl"

    return {
        "exec": _read_json(art / "exec.json"),
        "egress": egress_summary(egress_path),
        "fsdiff": _read_json(art / "fsdiff.json"),
        "artifacts": result.get("artifacts") or {},
        "sandbox": {
            "exit_code": result.get("exit_code"),
            "timed_out": result.get("timed_out"),
            "duration_s": result.get("duration_s"),
        },
    }


def execute(store, run_id, package_path, question=None, *, egress_mode="none",
            timeout_s=180, chat=None, model=None):
    """Run one task. Never raises: a failure is a stored state, not a crash."""
    store.update(run_id, state="running", started=_now())
    try:
        result = sandbox.run_package(
            Path(package_path),
            store.dir_for(run_id),
            task_id=run_id,
            timeout_s=timeout_s,
            egress_mode=egress_mode,
        )
    except Exception as exc:  # noqa: BLE001 - store it, show it, do not swallow it
        return store.update(run_id, state="failed", finished=_now(),
                            error=f"{type(exc).__name__}: {exc}")

    evidence = collect_evidence(store.dir_for(run_id), result)

    try:
        v = verdict(evidence, question=question, chat=chat, model=model)
    except Exception as exc:  # noqa: BLE001
        v = {"risk": "unknown", "findings": [], "rejected_claims": [],
             "summary": None, "model_used": False,
             "notes": [f"verdict failed: {type(exc).__name__}: {exc}"]}

    return store.update(
        run_id, state="done", finished=_now(),
        evidence=evidence, verdict=v,
        sandbox=evidence["sandbox"],
    )
