"""Batch triage: several packages, one report.

A team does not check one package, it checks the set that is about to be merged.
The batch runs sequentially on purpose -- one container at a time keeps the resource
story honest on a 1-vCPU box, and a report is more useful than parallelism here.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import pipeline

RISK_ORDER = {"unknown": -1, "low": 0, "medium": 1, "high": 2}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class BatchStore:
    """Same shape as RunStore, kept separate so a batch is not a run."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def new_id(self):
        import uuid
        return "b" + time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:6]

    def _path(self, batch_id):
        if not batch_id or "/" in batch_id or ".." in batch_id:
            raise ValueError(f"invalid batch id: {batch_id!r}")
        return self.root / f"{batch_id}.json"

    def create(self, batch_id, meta=None):
        record = {"id": batch_id, "state": "queued", "created": _now(), "results": [], "worst": None}
        record.update(meta or {})
        self._write(record)
        return record

    def read(self, batch_id):
        path = self._path(batch_id)
        if not path.is_file():
            raise FileNotFoundError(batch_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def update(self, batch_id, **fields):
        record = self.read(batch_id)
        record.update(fields)
        record["updated"] = _now()
        self._write(record)
        return record

    def list(self, limit=20):
        out = []
        for path in sorted(self.root.glob("*.json"), reverse=True)[:limit]:
            try:
                out.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return out

    def _write(self, record):
        path = self._path(record["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


def worst_risk(results):
    worst = "low"
    for item in results:
        risk = str(item.get("risk") or "unknown")
        if RISK_ORDER.get(risk, -1) > RISK_ORDER.get(worst, 0):
            worst = risk
    return worst


def run_batch(run_store, batch_store, batch_id, packages, *, question=None,
              egress_mode="proxy", chat=None, model=None, timeout_s=180):
    batch_store.update(batch_id, state="running", started=_now())
    results = []
    for package in packages:
        run_id = run_store.new_id()
        run_store.create(run_id, {"batch": batch_id, "package": str(package)})
        try:
            record = pipeline.execute(run_store, run_id, package, question,
                                      egress_mode=egress_mode, timeout_s=timeout_s,
                                      chat=chat, model=model)
        except Exception as exc:  # noqa: BLE001 - one bad package must not kill the batch
            record = {"state": "failed", "error": f"{type(exc).__name__}: {exc}"}

        verdict = record.get("verdict") or {}
        results.append({
            "package": Path(package).name,
            "run": run_id,
            "state": record.get("state"),
            "risk": verdict.get("risk"),
            "findings": len(verdict.get("findings") or []),
            "rejected": len(verdict.get("rejected_claims") or []),
        })
        batch_store.update(batch_id, results=results, worst=worst_risk(results))

    return batch_store.update(batch_id, state="done", finished=_now(),
                              worst=worst_risk(results), results=results)
