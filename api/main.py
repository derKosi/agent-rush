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
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from api.guard import Guard                            # noqa: E402
from orchestrator import pipeline                      # noqa: E402
from orchestrator.run_store import RunStore, RunStoreError  # noqa: E402
from models import client as inference                 # noqa: E402

RUNS_DIR = Path(os.environ.get("AR_RUNS_DIR", REPO / "work" / "runs")).resolve()
STORE = RunStore(RUNS_DIR)

# A task may only name a package inside these roots. Without this, the endpoint
# would happily execute anything readable by the service user.
ALLOWED_ROOTS = [(REPO / "fixtures").resolve(), (RUNS_DIR / "uploads").resolve()]

app = FastAPI(title="Agent Rush", version="0.1", docs_url="/api/docs")
GUARD = Guard.from_env()


def client_ip(request: Request) -> str:
    """Caddy is the only ingress and sets X-Real-IP; trust it, fall back to the peer."""
    return (request.headers.get("x-real-ip")
            or (request.client.host if request.client else "unknown"))


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
        "runs_dir": str(RUNS_DIR),
        "sandbox_override": bool(os.environ.get("AR_SANDBOX_CMD")),
        "limits": GUARD.snapshot(),
    }


@app.post("/tasks", status_code=202)
def create_task(task: TaskIn, request: Request):
    package = resolve_package(task.package)

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
    GUARD.begin()

    run_id = STORE.new_id()
    STORE.create(run_id, {"task": task.model_dump()})
    threading.Thread(target=_dispatch, args=(run_id, package, task), daemon=True).start()
    return {"id": run_id, "state": "queued"}


@app.get("/runs")
def list_runs(limit: int = 25):
    return {"runs": STORE.list(limit=max(1, min(limit, 200)))}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    try:
        return STORE.read(run_id)
    except RunStoreError as exc:
        raise HTTPException(404, str(exc)) from exc


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
