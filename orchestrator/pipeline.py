"""Pipeline: one run, start to verdict. The only place that knows the order.

Kept separate from the API so the whole thing can be exercised from a script
(tests/test_pipeline.py) without starting a web server.
"""

from __future__ import annotations

import time
from pathlib import Path

from . import planner
from . import sandbox
from .verdict import egress_summary, verdict, _read_json


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _source_excerpt(package_path, limit=1500):
    """First part of setup.py, as a human triager would read it.

    This is attacker-controlled text and it goes into the evidence on purpose: the
    interesting case is a package that writes instructions for whoever reads it.
    """
    import tarfile
    try:
        with tarfile.open(package_path, "r:*") as tf:
            for member in tf.getmembers():
                if not member.isfile() or not member.name.endswith("setup.py"):
                    continue
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                body = fh.read().decode("utf-8", "replace")
                if len(body) <= limit:
                    return body
                # Head and tail: payloads hide at the end, and a triager reads both.
                half = limit // 2
                return (body[:half]
                        + "\n...[{} chars omitted]...\n".format(len(body) - limit)
                        + body[-half:])
    except (tarfile.TarError, OSError):
        return ""
    return ""


def collect_evidence(run_dir, result, package_path=None) -> dict:
    """Assemble the evidence object. Every field is read from disk or the result."""
    run_dir = Path(run_dir)
    art = run_dir / "artifacts"

    egress_path = art / "egress.jsonl"
    if not egress_path.is_file():
        egress_path = run_dir / "egress.jsonl"

    # The build log is attacker-controlled text. It goes into the evidence because a
    # triager has to read what the package printed -- and because excluding it would
    # hide the most interesting case: instructions aimed at the model itself.
    log_tail = ""
    log_path = art / "pip.log"
    if log_path.is_file():
        log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]

    excerpt = _source_excerpt(package_path) if package_path else ""

    return {
        "build_log_tail": log_tail,
        "package_source_excerpt": excerpt,
        "exec": _read_json(art / "exec.json"),
        "egress": egress_summary(egress_path),
        "probe": _read_json(art / "probe.json"),
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

    # Plan first: the model picks the probes, the sandbox runs only those.
    try:
        plan_result = planner.plan(package_path, question=question, chat=chat, model=model)
    except Exception as exc:  # noqa: BLE001
        plan_result = {"probes": list(planner.ALL_PROBES), "source": "default",
                       "reason": f"planner failed: {type(exc).__name__}: {exc}", "rejected": []}
    store.update(run_id, plan=plan_result)

    try:
        result = sandbox.run_package(
            Path(package_path),
            store.dir_for(run_id),
            task_id=run_id,
            timeout_s=timeout_s,
            egress_mode=egress_mode,
            probes=planner.probes_env(plan_result),
        )
    except Exception as exc:  # noqa: BLE001 - store it, show it, do not swallow it
        return store.update(run_id, state="failed", finished=_now(),
                            error=f"{type(exc).__name__}: {exc}")

    evidence = collect_evidence(store.dir_for(run_id), result, Path(package_path))

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
