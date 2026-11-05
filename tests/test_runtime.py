#!/usr/bin/env python3
"""Runtime detection.  python3 tests/test_runtime.py"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import runtime  # noqa: E402

FIX = REPO / "fixtures"
results = []


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ok    {name}")
    except Exception as exc:  # noqa: BLE001
        results.append((name, exc))
        print(f"  FAIL  {name}: {exc}")


def test_node_tarball():
    assert runtime.detect(FIX / "sample_pkg_node-0.1.0.tar.gz") == "node"


def test_python_tarballs():
    for name in ("sample_pkg-0.1.0.tar.gz", "sample_pkg_deps-0.1.0.tar.gz",
                 "sample_pkg_injected-0.1.0.tar.gz"):
        assert runtime.detect(FIX / name) == "python", name


def test_missing_file_defaults_to_python():
    assert runtime.detect(FIX / "nope.tar.gz") == "python"


def test_mixed_archive_is_python():
    # A package.json inside a Python project (some wheel builds ship one) must not
    # flip the runtime and run npm on a setup.py project.
    import tarfile
    import tempfile
    tmp = Path(tempfile.mkdtemp()) / "mixed.tar.gz"
    payload = tmp.parent / "pkg"
    payload.mkdir()
    (payload / "setup.py").write_text("# setup")
    (payload / "package.json").write_text("{}")
    with tarfile.open(tmp, "w:gz") as tf:
        tf.add(payload, arcname="pkg")
    assert runtime.detect(tmp) == "python"


def main() -> int:
    print("runtime")
    check("node tarball", test_node_tarball)
    check("python tarballs", test_python_tarballs)
    check("missing file", test_missing_file_defaults_to_python)
    check("mixed archive", test_mixed_archive_is_python)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
