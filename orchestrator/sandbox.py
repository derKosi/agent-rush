"""Invoke the sandbox runner and collect its evidence.

The contract with sandbox/run.sh is deliberately narrow: give it a package path and
a task id, set AR_WORKDIR, and it leaves artifacts in $AR_WORKDIR/out. Everything
this module reports is read from disk afterwards -- it never parses the runner's
chatter to decide whether something worked.

AR_SANDBOX_CMD overrides the runner. That exists for tests only (tests/stub_sandbox.sh);
production never sets it, and nothing in the UI can toggle it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "sandbox" / "run.sh"
ARTIFACT_NAMES = ("exec.json", "pip.log", "probe.json", "script.log", "fsdiff.json", "egress.jsonl")


class SandboxError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def run_package(package_path, run_dir, *, task_id, timeout_s=180,
                egress_mode="none", allow="", probes="") -> dict:
    """Execute one package in the sandbox. Returns a plain dict, JSON-serialisable."""
    package_path = Path(package_path).resolve()
    if not package_path.is_file():
        raise SandboxError(f"package not found: {package_path}")

    run_dir = Path(run_dir).resolve()
    work = run_dir / "work"
    artifacts_dir = run_dir / "artifacts"
    work.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.update({
        "AR_WORKDIR": str(work),
        "AR_TASK_ID": task_id,
        "AR_EGRESS_MODE": egress_mode,
        "AR_ALLOW": allow,
        "AR_PROXY_LOG": str(run_dir / "egress.jsonl"),
        "AR_TIMEOUT_S": str(timeout_s),
        "AR_PROBES": probes or "",
    })

    override = os.environ.get("AR_SANDBOX_CMD")
    cmd = [override, str(package_path), task_id] if override else \
          ["bash", str(RUNNER), str(package_path), task_id]

    started = time.time()
    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                              timeout=timeout_s + 60)
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        rc, out, err = -1, (exc.stdout or ""), (exc.stderr or "")
        timed_out = True
    duration = round(time.time() - started, 2)

    collected = _collect(work, artifacts_dir)
    evidence = _read_exec_json(artifacts_dir / "exec.json")

    return {
        "exit_code": rc,
        "timed_out": timed_out,
        "duration_s": duration,
        "runner_stderr_tail": (err or "")[-2000:],
        "runner_stdout_tail": (out or "")[-2000:],
        "artifacts": collected,
        "evidence": evidence,
    }


def _collect(work: Path, artifacts_dir: Path) -> dict:
    """Copy whatever the runner produced into the run's artifacts dir."""
    out_dir = work / "out"
    found = {}
    for name in ARTIFACT_NAMES:
        src = out_dir / name
        if src.is_file():
            dst = artifacts_dir / name
            shutil.copy2(src, dst)
            found[name] = {"bytes": dst.stat().st_size, "sha256": _sha256(dst)}
    # The proxy log is written outside the container, next to work/, not in it.
    proxy_log = work.parent / "egress.jsonl"
    if proxy_log.is_file() and "egress.jsonl" not in found:
        dst = artifacts_dir / "egress.jsonl"
        shutil.copy2(proxy_log, dst)
        found["egress.jsonl"] = {"bytes": dst.stat().st_size, "sha256": _sha256(dst)}
    return found


def _read_exec_json(path: Path):
    """Parse exec.json if present. Absence is a finding, not an exception."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": "exec.json is not valid JSON"}


def run_script(package_path, run_dir, code, *, task_id, timeout_s=60) -> dict:
    """Run a model-authored inspection script in the same sandbox.

    The script gets the package path as argv[1] and is expected to print JSON.
    It runs with no network and a read-only root, exactly like the probe run --
    model output is untrusted code and is treated as such.
    """
    package_path = Path(package_path).resolve()
    run_dir = Path(run_dir).resolve()
    # Own work dir: sharing one with the probe run means the second run overwrites
    # the first one's exec.json and the inspection log disappears.
    work = run_dir / "work-script"
    artifacts_dir = run_dir / "artifacts"
    work.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (work / "script.py").write_text(code, encoding="utf-8")

    env = os.environ.copy()
    env.update({
        "AR_WORKDIR": str(work),
        "AR_TASK_ID": task_id,
        "AR_MODE": "script",
        "AR_EGRESS_MODE": "none",
        "AR_ALLOW": "",
        "AR_TIMEOUT_S": str(timeout_s),
        "AR_PROBES": "",
    })

    started = time.time()
    try:
        proc = subprocess.run(["bash", str(RUNNER), str(package_path), task_id],
                              env=env, capture_output=True, text=True, timeout=timeout_s + 30)
        rc, err = proc.returncode, proc.stderr
    except subprocess.TimeoutExpired:
        rc, err = -1, "timeout"
    duration = round(time.time() - started, 2)

    log_path = work / "out" / "script.log"
    output = log_path.read_text(encoding="utf-8", errors="replace")[-4000:] if log_path.is_file() else ""
    if log_path.is_file():
        shutil.copy2(log_path, artifacts_dir / "script.log")
    # The script itself is evidence: a juror should be able to read the code the
    # model wrote, not just trust that it wrote something.
    shutil.copy2(work / "script.py", artifacts_dir / "script.py")

    return {"exit_code": rc, "duration_s": duration, "output": output,
            "stderr_tail": (err or "")[-500:]}
