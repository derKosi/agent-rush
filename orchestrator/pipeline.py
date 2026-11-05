"""Pipeline: one run, start to verdict. The only place that knows the order.

Kept separate from the API so the whole thing can be exercised from a script
(tests/test_pipeline.py) without starting a web server.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import deps as deps_mod
from . import planner
from . import runtime as runtime_mod
from . import reputation
from . import recovery
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


def _parse_import_result(log_tail):
    """Pull the AR_IMPORT_RESULT line out of the import log."""
    for line in reversed(log_tail.splitlines()):
        if line.startswith("AR_IMPORT_RESULT "):
            try:
                return json.loads(line[len("AR_IMPORT_RESULT "):])
            except json.JSONDecodeError:
                return None
    return None


def _parse_inspection(inspection):
    """The script's JSON, if it produced any. Absence is recorded, not hidden."""
    if not inspection:
        return None
    out = inspection.get("output") or ""
    start, end = out.find("{"), out.rfind("}")
    parsed = None
    if start != -1 and end > start:
        try:
            parsed = json.loads(out[start:end + 1])
        except json.JSONDecodeError:
            parsed = None
    return {"exit_code": inspection.get("exit_code"),
            "parsed": parsed,
            "raw_tail": out[-1200:] if parsed is None else ""}


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

    work_bytes = 0
    work_dir = Path(run_dir) / "work"
    if work_dir.is_dir():
        for path in work_dir.rglob("*"):
            try:
                if path.is_file():
                    work_bytes += path.stat().st_size
            except OSError:
                continue

    collected = result.get("artifacts") or {}
    # Anything else in the artifacts dir (script.log, script.py from the inspection
    # pass) belongs in the evidence too. Listing the directory beats guessing names.
    for path in sorted(art.iterdir()) if art.is_dir() else []:
        if path.is_file() and path.name not in collected:
            import hashlib
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            collected[path.name] = {"bytes": path.stat().st_size, "sha256": digest}

    return {
        "work_bytes": work_bytes,
        "build_log_tail": log_tail,
        "package_source_excerpt": excerpt,
        "exec": _read_json(art / "exec.json"),
        "egress": egress_summary(egress_path),
        "probe": _read_json(art / "probe.json"),
        "fsdiff": _read_json(art / "fsdiff.json"),
        "artifacts": collected,
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
    # The model also writes an inspection script, which runs in the same sandbox
    # before anything executes. Pattern A in the challenge playbook, taken literally.
    script_result = {"code": None, "reason": "not attempted"}
    inspection = None
    if chat is not None:
        script_result = planner.write_script(package_path, question=question, chat=chat, model=model)
    plan_result["script"] = {"written": bool(script_result.get("code")),
                             "reason": script_result.get("reason")}
    store.update(run_id, plan=plan_result)

    if script_result.get("code"):
        try:
            inspection = sandbox.run_script(
                Path(package_path), store.dir_for(run_id), script_result["code"],
                task_id=run_id, timeout_s=60)
            store.update(run_id, inspection=inspection)
        except Exception as exc:  # noqa: BLE001
            inspection = {"exit_code": None, "output": "", "error": str(exc)}

    runtime = runtime_mod.detect(package_path)
    store.update(run_id, runtime=runtime)

    attempts = []
    current_timeout = timeout_s
    while True:
        try:
            result = sandbox.run_package(
                Path(package_path),
                store.dir_for(run_id),
                task_id=run_id,
                timeout_s=current_timeout,
                egress_mode=egress_mode,
                probes=planner.probes_env(plan_result),
                runtime=runtime,
            )
        except Exception as exc:  # noqa: BLE001 - store it, show it, do not swallow it
            return store.update(run_id, state="failed", finished=_now(),
                                error=f"{type(exc).__name__}: {exc}")

        evidence = collect_evidence(store.dir_for(run_id), result, Path(package_path))
        evidence["inspection"] = _parse_inspection(inspection)

        diagnosis = recovery.diagnose(result, evidence)
        attempts.append({
            "attempt": len(attempts) + 1,
            "timeout_s": current_timeout,
            "exit_code": result.get("exit_code"),
            "timed_out": bool(result.get("timed_out")),
            "diagnosis": diagnosis,
        })

        # One retry, and only when the failure was our limit rather than the package.
        if diagnosis and diagnosis["retryable"] and len(attempts) == 1:
            bumped = recovery.next_timeout(current_timeout)
            if bumped:
                current_timeout = bumped
                store.update(run_id, attempts=attempts)
                continue
        break

    # Second pass: what happens when the package is actually imported. A payload that
    # waits for first use is invisible to the build run, and that is the common case.
    if os.environ.get("AR_IMPORT_PASS", "on").lower() != "off":
        try:
            imported = sandbox.run_import(
                Path(package_path), store.dir_for(run_id), task_id=run_id,
                timeout_s=max(60, current_timeout // 2),
                probes=planner.probes_env(plan_result),
                runtime=runtime,
            )
            evidence["import_pass"] = {
                "exit_code": imported.get("exit_code"),
                "duration_s": imported.get("duration_s"),
                "result": _parse_import_result(imported.get("log_tail") or ""),
                "probe": _read_json(store.dir_for(run_id) / "artifacts" / "import_probe.json"),
                "log_tail": (imported.get("log_tail") or "")[-1500:],
            }
        except Exception as exc:  # noqa: BLE001
            evidence["import_pass"] = {"error": f"{type(exc).__name__}: {exc}"}

    # Phase 3: make the dependency tree visible. Network on, package code untouched.
    declared = deps_mod.declared_dependencies(package_path)
    # No declared dependencies means no container: spinning one up to fetch nothing is
    # a wasted run and makes the test suite depend on Docker for no reason.
    if not declared:
        evidence["dependencies"] = {"declared": [], "resolved": [],
                                    "skipped": "no declared dependencies"}
    elif os.environ.get("AR_DEPS_PASS", "on").lower() != "off":
        try:
            resolved = sandbox.run_resolve(
                Path(package_path), store.dir_for(run_id), declared,
                task_id=run_id, timeout_s=max(120, current_timeout),
            )
            vulns = reputation.check(resolved.get("resolved") or [])
            behind = reputation.outdated(resolved.get("resolved") or [])
            evidence["dependencies"] = {
                "declared": declared,
                "resolved": resolved.get("resolved") or [],
                "vulnerabilities": vulns,
                "outdated": behind,
                "exit_code": resolved.get("exit_code"),
                "duration_s": resolved.get("duration_s"),
                "log_tail": (resolved.get("log_tail") or "")[-1200:],
            }
        except Exception as exc:  # noqa: BLE001
            evidence["dependencies"] = {"declared": declared, "error": f"{type(exc).__name__}: {exc}"}
    else:
        evidence["dependencies"] = {"declared": declared, "resolved": [], "skipped": True}

    model_name = (model or os.environ.get("AR_MODEL") or "").strip() or None

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
        model=model_name,
        attempts=attempts,
        outcome=(attempts[-1]["diagnosis"] or {}).get("kind") if attempts else None,
    )
