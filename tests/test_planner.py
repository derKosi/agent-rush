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


def test_audit_allows_mentions_in_strings():
    code = 'import re\npat = re.compile(r"subprocess|os\\.system|popen")\nprint(pat)'
    assert planner.audit_script(code) is None


def test_audit_rejects_real_import():
    assert "imports subprocess" in planner.audit_script("import subprocess\nsubprocess.run([])")


def test_audit_rejects_real_call():
    assert "os.system" in planner.audit_script("import os\nos.system('ls')")


def test_audit_rejects_syntax_error():
    assert "syntax error" in planner.audit_script("def broken(:\n  pass")


def test_write_script_without_model():
    r = planner.write_script(FIXTURE)
    assert r["code"] is None and "no model" in r["reason"]


def test_write_script_extracts_fenced_code():
    def fake(messages, model=None):
        return "Here you go:\n```python\nimport tarfile, sys, json\nprint(json.dumps({}))\n```\nDone."

    r = planner.write_script(FIXTURE, chat=fake)
    assert r["code"].startswith("import tarfile"), r
    assert "```" not in r["code"]


def test_write_script_refuses_dangerous_code():
    def fake(messages, model=None):
        return "```python\nimport subprocess\nsubprocess.run(['ls'])\n```"

    r = planner.write_script(FIXTURE, chat=fake)
    assert r["code"] is None and "refused" in r["reason"]


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
    print("script generation")
    check("audit allows string mentions", test_audit_allows_mentions_in_strings)
    check("audit rejects real import", test_audit_rejects_real_import)
    check("audit rejects real call", test_audit_rejects_real_call)
    check("audit rejects syntax error", test_audit_rejects_syntax_error)
    check("no model -> no script", test_write_script_without_model)
    check("fenced code extracted", test_write_script_extracts_fenced_code)
    check("dangerous code refused", test_write_script_refuses_dangerous_code)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
