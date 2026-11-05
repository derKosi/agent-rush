#!/usr/bin/env python3
"""Dependency visibility without execution.  python3 tests/test_deps.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import deps  # noqa: E402
from orchestrator.verdict import rule_findings  # noqa: E402

WITH_DEPS = REPO / "fixtures" / "sample_pkg_deps-0.1.0.tar.gz"
WITHOUT = REPO / "fixtures" / "sample_pkg-0.1.0.tar.gz"

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, exc))
        print(f"  FAIL  {name}: {exc}")


def test_reads_pkg_info():
    assert deps.declared_dependencies(WITH_DEPS) == ["six>=1.16"]


def test_no_pkg_info_means_none_declared():
    assert deps.declared_dependencies(WITHOUT) == []


def test_legacy_parentheses():
    assert deps.normalise("six (>=1.16)") == "six>=1.16"


def test_markers_are_dropped():
    assert deps.normalise('foo>=1; python_version<"3.9"') == "foo>=1"


def test_missing_file_is_not_an_error():
    assert deps.declared_dependencies(REPO / "does-not-exist.tar.gz") == []


def test_resolved_dependencies_are_informational():
    ev = {"dependencies": {"declared": ["six>=1.16"],
                           "resolved": [{"file": "six-1.17.0-py2.py3-none-any.whl"}]}}
    found = [f for f in rule_findings(ev) if f["source"] == "dependencies"]
    assert found and found[0]["severity"] == "info", found


def test_declared_but_unresolved_is_medium():
    ev = {"dependencies": {"declared": ["six>=1.16"], "resolved": []}}
    found = [f for f in rule_findings(ev) if f["source"] == "dependencies"]
    assert found and found[0]["severity"] == "medium", found


def main() -> int:
    print("dependencies")
    check("reads PKG-INFO", test_reads_pkg_info)
    check("no PKG-INFO", test_no_pkg_info_means_none_declared)
    check("legacy parentheses", test_legacy_parentheses)
    check("env markers dropped", test_markers_are_dropped)
    check("missing file is quiet", test_missing_file_is_not_an_error)
    check("resolved is info", test_resolved_dependencies_are_informational)
    check("declared but unresolved is medium", test_declared_but_unresolved_is_medium)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
