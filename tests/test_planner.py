#!/usr/bin/env python3
"""Planner tests. No model, no Docker.  python3 tests/test_planner.py"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import planner  # noqa: E402

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


def test_validate_drops_unknown():
    chosen, rejected = planner.validate_plan(["egress", "rootkit", "egress", "decoy_key"])
    assert chosen == ["egress", "decoy_key"], chosen
    assert rejected == ["rootkit"], rejected


def test_no_model_runs_everything():
    p = planner.plan(FIXTURE)
    assert p["source"] == "default"
    assert set(p["probes"]) == set(planner.ALL_PROBES)


def test_model_choice_is_used():
    def fake(messages, model=None):
        return json.dumps({"probes": ["egress"], "reason": "network reference found"})

    p = planner.plan(FIXTURE, chat=fake)
    assert p["source"] == "model"
    assert p["probes"] == ["egress"]
    assert "network" in p["reason"]


def test_unknown_only_falls_back():
    def fake(messages, model=None):
        return json.dumps({"probes": ["curl_the_internet"], "reason": "trust me"})

    p = planner.plan(FIXTURE, chat=fake)
    assert p["source"] == "default"
    assert set(p["probes"]) == set(planner.ALL_PROBES)
    assert p["rejected"] == ["curl_the_internet"]


def test_model_error_falls_back():
    def boom(messages, model=None):
        raise RuntimeError("503")

    p = planner.plan(FIXTURE, chat=boom)
    assert p["source"] == "default"
    assert "failed" in p["reason"]


def test_garbage_answer_falls_back():
    def fake(messages, model=None):
        return "I would check everything carefully."

    p = planner.plan(FIXTURE, chat=fake)
    assert p["source"] == "default"


def test_profile_reads_without_executing():
    prof = planner.static_profile(FIXTURE)
    assert prof["has_setup_py"] is True
    assert prof["references_network"] is True
    assert any(m.endswith("setup.py") for m in prof["members"])


def test_probes_env():
    assert planner.probes_env({"probes": ["egress", "decoy_key"]}) == "egress,decoy_key"
    assert set(planner.probes_env({}).split(",")) == set(planner.ALL_PROBES)


def main() -> int:
    print("planner")
    check("unknown probes dropped", test_validate_drops_unknown)
    check("no model -> all probes", test_no_model_runs_everything)
    check("model choice used", test_model_choice_is_used)
    check("unknown-only -> fallback", test_unknown_only_falls_back)
    check("model error -> fallback", test_model_error_falls_back)
    check("garbage -> fallback", test_garbage_answer_falls_back)
    check("profile without execution", test_profile_reads_without_executing)
    check("probes env", test_probes_env)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
