#!/usr/bin/env python3
"""Dependency reputation without network.  python3 tests/test_reputation.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import reputation  # noqa: E402

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, exc))
        print(f"  FAIL  {name}: {exc}")


def test_wheel_name_parsing():
    assert reputation.parse_artifact("urllib3-1.24.1-py2.py3-none-any.whl") == ("urllib3", "1.24.1")
    assert reputation.parse_artifact("six-1.17.0-py2.py3-none-any.whl") == ("six", "1.17.0")


def test_npm_name_parsing():
    assert reputation.parse_artifact("sample-pkg-node-0.1.0.tgz") == ("sample-pkg-node", "0.1.0")


def test_unknown_files_are_ignored():
    assert reputation.parse_artifact("notes.txt") == (None, None)


def test_duplicates_are_collapsed():
    vulns = [
        {"id": "GHSA-1", "summary": "long summary here", "aliases": ["CVE-2020-1"]},
        {"id": "PYSEC-1", "summary": "", "aliases": ["CVE-2020-1"]},
    ]
    unique = reputation.dedupe(vulns)
    assert len(unique) == 1, unique
    assert unique[0]["summary"] == "long summary here"


def test_disabled_makes_no_calls():
    calls = []

    def fetch(*a, **k):
        calls.append(a)
        return [{"id": "X", "summary": "s", "aliases": []}]

    out = reputation.check([{"file": "six-1.17.0-py2.py3-none-any.whl"}],
                           enabled=False, fetch=fetch)
    assert out == [] and calls == []


def test_lookup_failure_is_reported_not_raised():
    def boom(*a, **k):
        raise OSError("no route")

    out = reputation.check([{"file": "six-1.17.0-py2.py3-none-any.whl"}], fetch=boom)
    assert out and out[0]["error"] == "OSError", out


def test_clean_dependency_returns_nothing():
    def empty(*a, **k):
        return []

    assert reputation.check([{"file": "six-1.17.0-py2.py3-none-any.whl"}], fetch=empty) == []


def main() -> int:
    print("reputation")
    check("wheel names", test_wheel_name_parsing)
    check("npm names", test_npm_name_parsing)
    check("unknown files", test_unknown_files_are_ignored)
    check("duplicates collapsed", test_duplicates_are_collapsed)
    check("disabled means no calls", test_disabled_makes_no_calls)
    check("failure is reported", test_lookup_failure_is_reported_not_raised)
    check("clean dependency", test_clean_dependency_returns_nothing)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
