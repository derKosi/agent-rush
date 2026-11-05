#!/usr/bin/env python3
"""SARIF shape.  python3 tests/test_sarif.py"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator.sarif import build  # noqa: E402

RECORD = {
    "id": "20261105T120000-abcdef",
    "runtime": "python",
    "verdict": {
        "risk": "high",
        "model_used": True,
        "findings": [
            {"severity": "high", "source": "egress.jsonl", "claim": "2 outbound attempts blocked"},
            {"severity": "medium", "source": "probe.json", "claim": "write denied"},
            {"severity": "info", "source": "fsdiff.json", "claim": "not measured"},
        ],
        "rejected_claims": [{"source": "strace.log", "claim": "read ssh keys"}],
    },
}

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, exc))
        print(f"  FAIL  {name}: {exc}")


def test_shape():
    doc = build(RECORD)
    assert doc["version"] == "2.1.0"
    assert len(doc["runs"]) == 1
    run = doc["runs"][0]
    assert run["tool"]["driver"]["name"] == "agent-rush"
    assert run["automationDetails"]["id"] == RECORD["id"]


def test_levels():
    run = build(RECORD)["runs"][0]
    levels = [r["level"] for r in run["results"][:3]]
    assert levels == ["error", "warning", "note"], levels


def test_every_finding_becomes_a_result():
    run = build(RECORD)["runs"][0]
    assert len(run["results"]) == 4          # 3 findings + 1 rejected claim


def test_rules_are_unique():
    run = build(RECORD)["runs"][0]
    ids = [r["id"] for r in run["tool"]["driver"]["rules"]]
    assert len(ids) == len(set(ids)), ids
    assert "agent-rush/rejected-claim" in ids


def test_serialisable():
    json.dumps(build(RECORD))


def test_empty_verdict_does_not_crash():
    doc = build({"id": "x", "verdict": {}})
    assert doc["runs"][0]["results"] == []


def main() -> int:
    print("sarif")
    check("shape", test_shape)
    check("levels", test_levels)
    check("findings become results", test_every_finding_becomes_a_result)
    check("rules are unique", test_rules_are_unique)
    check("serialisable", test_serialisable)
    check("empty verdict", test_empty_verdict_does_not_crash)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
