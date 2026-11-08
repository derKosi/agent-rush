#!/usr/bin/env python3
"""Upload validation.  python3 tests/test_upload.py

The interesting cases are the refusals: an upload endpoint that accepts whatever arrives is a
file store with a queue attached.
"""

import io
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from orchestrator import upload  # noqa: E402

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


def expect_upload_error(fn, needle=""):
    try:
        fn()
    except upload.UploadError as exc:
        assert needle.lower() in str(exc).lower(), f"message did not mention {needle!r}: {exc}"
        return
    raise AssertionError("accepted something that should have been refused")


def tar_bytes(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, payload, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(payload)
                tar.addfile(info, io.BytesIO(payload))
            elif kind == "dir":
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            elif kind == "sym":
                info.type = tarfile.SYMTYPE
                info.linkname = payload.decode()
                tar.addfile(info)
    return buf.getvalue()


def test_python_sdist():
    assert upload.inspect_tar((FIX / "harborline-2.9.1.tar.gz").read_bytes()) == "python"


def test_npm_tarball():
    assert upload.inspect_tar((FIX / "sample_pkg_node-0.1.0.tar.gz").read_bytes()) == "npm"


def test_traversal_refused():
    data = tar_bytes([("../../etc/evil", b"x", "file"), ("pkg/setup.py", b"", "file")])
    expect_upload_error(lambda: upload.inspect_tar(data), "unsafe")


def test_symlink_refused():
    data = tar_bytes([("pkg/setup.py", b"", "file"), ("pkg/passwd", b"/etc/passwd", "sym")])
    expect_upload_error(lambda: upload.inspect_tar(data), "unsafe")


def test_absolute_path_refused():
    data = tar_bytes([("/etc/cron.d/x", b"x", "file"), ("pkg/setup.py", b"", "file")])
    expect_upload_error(lambda: upload.inspect_tar(data), "unsafe")


def test_not_a_package():
    data = tar_bytes([("notes/readme.txt", b"hello", "file")])
    expect_upload_error(lambda: upload.inspect_tar(data), "no setup.py")


def test_not_gzip():
    expect_upload_error(lambda: upload.inspect_tar(b"hello world"), "")


def test_zip_refused_with_a_sentence():
    expect_upload_error(lambda: upload.accept(b"PK\x03\x04rest", "pkg.zip", Path("/tmp")), "zip")


def test_too_many_members():
    members = [(f"pkg/f{i}.py", b"", "file") for i in range(upload.MAX_MEMBERS + 1)]
    members.append(("pkg/setup.py", b"", "file"))
    expect_upload_error(lambda: upload.inspect_tar(tar_bytes(members)), "too many files")


def test_single_py_is_wrapped():
    src = b"print('hello')\n"
    data, name = upload.wrap_python_module(src, "my_script.py")
    assert name.endswith(".tar.gz"), name
    assert upload.inspect_tar(data) == "python"


def test_accepted_file_lands_on_disk():
    with tempfile.TemporaryDirectory() as tmp:
        path, kind = upload.accept((FIX / "left-pad-again-1.2.0.tar.gz").read_bytes(),
                                   "left-pad-again-1.2.0.tar.gz", Path(tmp))
        assert kind == "python"
        assert path.is_file() and path.is_relative_to(Path(tmp))
        assert path.name == "left-pad-again-1.2.0.tar.gz", path.name


def test_filename_is_sanitised():
    assert upload._safe_name("../../etc/passwd") == "passwd"
    assert upload._safe_name("weird name (1).tar.gz") == "weird-name-1-.tar.gz"
    assert upload._safe_name("") == "package.tar.gz"


def test_python_file_is_sanitised_module():
    data, name = upload.wrap_python_module(b"x = 1\n", "../evil module.py")
    assert "/" not in name and " " not in name, name
    assert upload.inspect_tar(data) == "python"


def main() -> int:
    print("upload")
    check("python sdist", test_python_sdist)
    check("npm tarball", test_npm_tarball)
    check("traversal refused", test_traversal_refused)
    check("symlink refused", test_symlink_refused)
    check("absolute path refused", test_absolute_path_refused)
    check("archive that is not a package", test_not_a_package)
    check("not gzip", test_not_gzip)
    check("zip refused", test_zip_refused_with_a_sentence)
    check("too many members", test_too_many_members)
    check("single .py wrapped", test_single_py_is_wrapped)
    check("accepted file on disk", test_accepted_file_lands_on_disk)
    check("filename sanitised", test_filename_is_sanitised)
    check("module name sanitised", test_python_file_is_sanitised_module)
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)}/{len(results)} ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
