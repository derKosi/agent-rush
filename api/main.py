"""Agent Rush control plane.

Three endpoints do the work; everything else exists to make them legible.
A task is accepted, dispatched to the sandbox, and its evidence is served back
from disk. The API never keeps state in memory -- restart it mid-run and the
run is still there.
"""

from __future__ import annotations

import os
import sys
import threading
import urllib.parse
from pathlib import Path
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from api.guard import Guard                            # noqa: E402
from orchestrator import upload as upload_mod
from orchestrator import batch as batch_mod            # noqa: E402
from orchestrator import sarif as sarif_mod            # noqa: E402
from orchestrator import pipeline                      # noqa: E402
from orchestrator.run_store import RunStore, RunStoreError  # noqa: E402
from models import client as inference                 # noqa: E402

RUNS_DIR = Path(os.environ.get("AR_RUNS_DIR", REPO / "work" / "runs")).resolve()
STORE = RunStore(RUNS_DIR)
BATCHES = batch_mod.BatchStore(RUNS_DIR.parent / "batches")

# A task may only name a package inside these roots. Without this, the endpoint
# would happily execute anything readable by the service user.
UPLOADS_DIR = (RUNS_DIR / "uploads").resolve()
ALLOWED_ROOTS = [(REPO / "fixtures").resolve(), UPLOADS_DIR]

app = FastAPI(title="Agent Rush", version="0.1", docs_url="/api/docs")
GUARD = Guard.from_env()


def client_ip(request: Request) -> str:
    """Caddy is the only ingress and sets X-Real-IP; trust it, fall back to the peer."""
    return (request.headers.get("x-real-ip")
            or (request.client.host if request.client else "unknown"))


class BatchIn(BaseModel):
    packages: List[str] = Field(..., min_length=1, max_length=10)
    question: Optional[str] = None
    egress_mode: Literal["none", "proxy"] = "proxy"
    fail_on: Literal["none", "low", "medium", "high"] = "high"


class TaskIn(BaseModel):
    package: str = Field(..., description="path inside fixtures/ or work/runs/uploads/")
    question: Optional[str] = None
    egress_mode: Literal["none", "proxy"] = "none"


def resolve_package(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = REPO / p
    p = p.resolve()
    if not any(p.is_relative_to(root) for root in ALLOWED_ROOTS):
        raise HTTPException(400, "package path is outside the allowed roots")
    if not p.is_file():
        raise HTTPException(404, f"package not found: {p.name}")
    return p


def _chat():
    """The model is optional. Without a key the verdict stays rule-based."""
    if os.environ.get("AR_VULTR_KEY") and os.environ.get("AR_MODEL"):
        return inference.chat
    return None


def _dispatch(run_id: str, package: Path, task: TaskIn) -> None:
    try:
        pipeline.execute(
            STORE, run_id, package, task.question,
            egress_mode=task.egress_mode,
            timeout_s=int(os.environ.get("AR_TIMEOUT_S", "180")),
            chat=_chat(),
            model=os.environ.get("AR_MODEL") or None,
        )
    finally:
        GUARD.end()


@app.get("/health")
def health():
    return {
        "ok": True,
        "model_configured": bool(os.environ.get("AR_VULTR_KEY") and os.environ.get("AR_MODEL")),
        "model": os.environ.get("AR_MODEL") or None,
        "reasoning": "on" if os.environ.get("AR_REASONING", "").lower() == "on" else "off",
        "dep_threshold": float(os.environ.get("AR_DEP_RISK_THRESHOLD", "7")),
        "runs_dir": str(RUNS_DIR),
        "sandbox_override": bool(os.environ.get("AR_SANDBOX_CMD")),
        "limits": GUARD.snapshot(),
    }


def _token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    return token or request.headers.get("x-api-token", "").strip()


def _admit(request: Request) -> None:
    """One rate-limit decision for every way in."""
    decision = GUARD.check(client_ip(request), _token(request))
    if not decision.allowed:
        raise HTTPException(
            status_code=429 if "token" not in decision.reason else 401,
            detail=decision.reason,
            headers={"Retry-After": str(decision.retry_after)} if decision.retry_after else None,
        )


@app.post("/tasks", status_code=202)
def create_task(task: TaskIn, request: Request):
    package = resolve_package(task.package)
    token = _token(request)

    decision = GUARD.check(client_ip(request), token)
    if not decision.allowed:
        raise HTTPException(
            status_code=429 if "token" not in decision.reason else 401,
            detail=decision.reason,
            headers={"Retry-After": str(decision.retry_after)} if decision.retry_after else None,
        )
    GUARD.begin(client_ip(request))

    run_id = STORE.new_id()
    STORE.create(run_id, {"task": task.model_dump()})
    threading.Thread(target=_dispatch, args=(run_id, package, task), daemon=True).start()
    return {"id": run_id, "state": "queued"}


def _batch_report(record):
    threshold = record.get("fail_on", "high")
    worst = record.get("worst")
    failed = (threshold != "none"
              and batch_mod.RISK_ORDER.get(str(worst), -1) >= batch_mod.RISK_ORDER[threshold])
    return {
        "batch": record["id"],
        "state": record.get("state"),
        "worst": worst,
        "fail_on": threshold,
        "failed": failed,
        "packages": record.get("results", []),
    }


@app.post("/tasks/upload", status_code=202)
async def create_task_from_upload(request: Request):
    """The browser path: the file is the request body, the name is in ``X-Filename``.

    Raw body instead of multipart on purpose -- no extra dependency in the image, and one fewer
    parser between the internet and a queue that runs docker. Everything that makes a package
    testable is decided here, before the pipeline sees it.
    """
    # Validate the bytes before taking a queue slot: a refusal should be about the file, not
    # about what else is running. The size cap still comes first, so a 25 MB body is cheap.
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > upload_mod.MAX_BYTES:
        raise HTTPException(413, f"file is larger than {upload_mod.MAX_BYTES // (1024 * 1024)} MB")

    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > upload_mod.MAX_BYTES:
            raise HTTPException(413, f"file is larger than {upload_mod.MAX_BYTES // (1024 * 1024)} MB")
        chunks.append(chunk)
    data = b"".join(chunks)

    name = request.headers.get("x-filename") or request.query_params.get("filename") or ""
    try:
        name = urllib.parse.unquote(name)
    except Exception:  # noqa: BLE001
        pass
    try:
        path, kind = upload_mod.accept(data, name or "package.tar.gz", UPLOADS_DIR)
    except upload_mod.UploadError as exc:
        raise HTTPException(400, str(exc)) from exc

    _admit(request)

    mode = request.query_params.get("egress_mode", "proxy")
    mode = mode if mode in ("none", "proxy") else "proxy"
    question = request.query_params.get("question") or None
    task = TaskIn(package=str(path.relative_to(REPO)), question=question, egress_mode=mode)

    GUARD.begin(client_ip(request))
    run_id = STORE.new_id()
    STORE.create(run_id, {
        "task": task.model_dump(),
        "upload": {"kind": kind, "filename": path.name, "bytes": len(data)},
    })
    threading.Thread(target=_dispatch, args=(run_id, path, task), daemon=True).start()
    return {"id": run_id, "state": "queued", "kind": kind, "filename": path.name}


@app.post("/batch", status_code=202)
def create_batch(payload: BatchIn, request: Request):
    paths = [resolve_package(pkg) for pkg in payload.packages]

    token = ""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    token = token or request.headers.get("x-api-token", "").strip()

    decision = GUARD.check(client_ip(request), token)
    if not decision.allowed:
        raise HTTPException(
            status_code=429 if "token" not in decision.reason else 401,
            detail=decision.reason,
            headers={"Retry-After": str(decision.retry_after)} if decision.retry_after else None,
        )
    GUARD.begin(client_ip(request))

    batch_id = BATCHES.new_id()
    BATCHES.create(batch_id, {"packages": [str(p) for p in paths],
                              "fail_on": payload.fail_on,
                              "question": payload.question})

    def _run():
        try:
            batch_mod.run_batch(
                STORE, BATCHES, batch_id, paths,
                question=payload.question,
                egress_mode=payload.egress_mode,
                chat=_chat(),
                model=os.environ.get("AR_MODEL") or None,
                timeout_s=int(os.environ.get("AR_TIMEOUT_S", "180")),
            )
        finally:
            GUARD.end()

    threading.Thread(target=_run, daemon=True).start()
    return {"id": batch_id, "state": "queued", "packages": len(paths)}


@app.get("/batches")
def list_batches(limit: int = 20):
    return {"batches": BATCHES.list(limit=max(1, min(limit, 100)))}


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str):
    try:
        return BATCHES.read(batch_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "unknown batch") from exc


@app.get("/batches/{batch_id}/report")
def get_batch_report(batch_id: str):
    try:
        return _batch_report(BATCHES.read(batch_id))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(404, "unknown batch") from exc


@app.get("/runs")
def list_runs(limit: int = 25):
    return {"runs": STORE.list(limit=max(1, min(limit, 200)))}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    try:
        return STORE.read(run_id)
    except RunStoreError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/runs/{run_id}/sarif")
def get_sarif(run_id: str):
    """SARIF for `github/codeql-action/upload-sarif` and friends."""
    try:
        record = STORE.read(run_id)
    except RunStoreError as exc:
        raise HTTPException(404, str(exc)) from exc
    return JSONResponse(sarif_mod.build(record),
                        media_type="application/sarif+json")


@app.get("/runs/{run_id}/artifacts/{name}")
def get_artifact(run_id: str, name: str):
    try:
        path = STORE.artifact_path(run_id, name)
    except RunStoreError as exc:
        raise HTTPException(404, str(exc)) from exc
    return FileResponse(path, filename=name)


# Mounted last: static files must not shadow the API routes above.
WEB = REPO / "web"
if WEB.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
