#!/usr/bin/env python3
"""Recovery rules: when is a retry worth a container?  python3 tests/test_recovery.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import recovery  # noqa: E402

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, exc))
        print(f"  FAIL  {name}: {exc}")


def _ev(exec_=None, probes=None, denied=0):
    return {"exec": exec_, "probe": probes, "egress": {"collected": True, "denied": denied}}


def test_timeout_is_retryable():
    d = recovery.diagnose({"timed_out": True}, _ev(exec_={"pip_exit": None}))
    assert d["kind"] == recovery.RETRY_TIMEOUT and d["retryable"] is True, d


def test_missing_exec_is_not_retryable():
    d = recovery.diagnose({"timed_out": False}, _ev(exec_=None))
    assert d["kind"] == recovery.NO_RESULT and d["retryable"] is False, d


def test_build_failure_without_evidence_is_not_retryable():
    d = recovery.diagnose({"timed_out": False}, _ev(exec_={"pip_exit": 1}))
    assert d["kind"] == recovery.BUILD_FAILED and d["retryable"] is False, d


def test_build_failure_with_probe_evidence_is_usable():
    d = recovery.diagnose({"timed_out": False},
                          _ev(exec_={"pip_exit": 1}, probes={"attempts": ["egress=denied:URLError"]}))
    assert d is None, d


def test_failed_build_with_egress_is_usable():
    d = recovery.diagnose({"timed_out": False}, _ev(exec_={"pip_exit": 1}, denied=2))
    assert d is None, d


def test_clean_run_needs_no_recovery():
    assert recovery.diagnose({"timed_out": False}, _ev(exec_={"pip_exit": 0})) is None


def test_timeout_doubles_and_is_bounded():
    assert recovery.next_timeout(60) == 120
    assert recovery.next_timeout(200) == 300
    assert recovery.next_timeout(300) is None


def main() -> int:
    print("recovery")
    check("timeout retryable", test_timeout_is_retryable)
    check("missing exec not retryable", test_missing_exec_is_not_retryable)
    check("build failure not retryable", test_build_failure_without_evidence_is_not_retryable)
    check("probe evidence makes it usable", test_build_failure_with_probe_evidence_is_usable)
    check("egress evidence makes it usable", test_failed_build_with_egress_is_usable)
    check("clean run untouched", test_clean_run_needs_no_recovery)
    check("timeout bounded", test_timeout_doubles_and_is_bounded)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
