"""Run store: one directory per task run, JSON on disk.

Deliberately a filesystem store and not a database. A run is an immutable set of
files plus a small state file; anything more would be infrastructure nobody asked
for. Survives a process restart, which is what the demo needs.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path

RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
STATES = ("queued", "running", "done", "failed")


class RunStoreError(RuntimeError):
    pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class RunStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def new_id(self) -> str:
        return time.strftime("%Y%m%dT%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:6]

    def dir_for(self, run_id: str) -> Path:
        if not RUN_ID_RE.match(run_id or ""):
            raise RunStoreError(f"invalid run id: {run_id!r}")
        return self.root / run_id

    def create(self, run_id: str, meta=None) -> dict:
        d = self.dir_for(run_id)
        if d.exists():
            raise RunStoreError(f"run exists: {run_id}")
        (d / "artifacts").mkdir(parents=True)
        record = {"id": run_id, "state": "queued", "created": _now(), "updated": _now()}
        record.update(meta or {})
        self._write(d, record)
        return record

    def read(self, run_id: str) -> dict:
        d = self.dir_for(run_id)
        path = d / "run.json"
        if not path.exists():
            raise RunStoreError(f"unknown run: {run_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def update(self, run_id: str, **fields) -> dict:
        record = self.read(run_id)
        if "state" in fields and fields["state"] not in STATES:
            raise RunStoreError(f"invalid state: {fields['state']}")
        record.update(fields)
        record["updated"] = _now()
        self._write(self.dir_for(run_id), record)
        return record

    def list(self, limit: int = 50):
        out = []
        for d in sorted(self.root.iterdir(), reverse=True):
            if not d.is_dir() or not RUN_ID_RE.match(d.name):
                continue
            try:
                out.append(self.read(d.name))
            except (RunStoreError, json.JSONDecodeError):
                continue
            if len(out) >= limit:
                break
        return out

    def artifact_path(self, run_id: str, name: str) -> Path:
        d = self.dir_for(run_id) / "artifacts"
        # No traversal: the name is used as a filename, nothing else.
        if os.path.basename(name) != name or name in ("", ".", ".."):
            raise RunStoreError(f"invalid artifact name: {name!r}")
        path = d / name
        if not path.exists():
            raise RunStoreError(f"no such artifact: {name}")
        return path

    @staticmethod
    def _write(directory: Path, record: dict) -> None:
        tmp = directory / "run.json.tmp"
        tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(directory / "run.json")
