"""Accept a package from a browser, and refuse everything that is not one.

The API already took a path. A path only works if you can put a file on the machine first,
which meant the only thing a visitor could test was our own fixtures. This module is the
missing half: bytes in, a validated distribution on disk out.

Three shapes are accepted, in this order of preference:

* ``.tar.gz`` / ``.tgz`` -- a Python sdist or an npm package, detected from the contents
* ``.py`` -- a single module, wrapped into a minimal sdist so the same three phases apply
* everything else -- refused with a sentence that says what to send instead

A zip sdist is refused on purpose. ``pip`` does accept one, but our pipeline reads tar, and
unpacking a zip in the API process is attack surface for a feature we can describe in one line.
"""

from __future__ import annotations

import hashlib
import io
import re
import tarfile
import time
from pathlib import Path

MAX_BYTES = 25 * 1024 * 1024
MAX_MEMBERS = 4000
MAX_UNPACKED = 200 * 1024 * 1024
MAX_PY_BYTES = 2 * 1024 * 1024
MAX_NAME = 120

GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK\x03\x04"


class UploadError(ValueError):
    """The bytes are not a package we can test. The message is shown to the user."""


def _safe_name(name: str) -> str:
    """A filename we are willing to write. Never the path a browser sent."""
    raw = (name or "").strip()
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(raw).name if raw else "").strip("-.")
    if not base:
        base = "package.tar.gz"
    if len(base) > MAX_NAME:
        stem, _dot, ext = base.rpartition(".")
        base = (stem[: MAX_NAME - len(ext) - 1] + "." + ext) if ext else base[:MAX_NAME]
    return base


def _member_ok(member: tarfile.TarInfo) -> bool:
    if not member.name or len(member.name) > 1024:
        return False
    if member.name.startswith("/") or member.name.startswith("\\"):
        return False
    parts = member.name.replace("\\", "/").split("/")
    if any(part in ("..", "") for part in parts[:-1]):
        return False
    return member.isfile() or member.isdir()


def _looks_like_python(tar: tarfile.TarFile) -> bool:
    for member in tar.getmembers():
        name = member.name
        if name.count("/") <= 1 and name.endswith("setup.py"):
            return True
        if name.endswith("/pyproject.toml") and name.count("/") == 1:
            return True
    return False


def _looks_like_npm(tar: tarfile.TarFile) -> bool:
    for member in tar.getmembers():
        name = member.name
        if name in ("package/package.json", "./package/package.json"):
            return True
        if name.endswith("/package.json") and name.count("/") == 1:
            return True
    return False


def inspect_tar(data: bytes) -> str:
    """Return "python" or "npm", or raise UploadError with the reason."""
    try:
        tar = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    except tarfile.TarError as exc:
        raise UploadError("not a gzip tar archive -- send the sdist you would pass to pip") from exc

    with tar:
        members = tar.getmembers()
        if not members:
            raise UploadError("the archive is empty")
        if len(members) > MAX_MEMBERS:
            raise UploadError(f"too many files ({len(members)}); limit is {MAX_MEMBERS}")
        unpacked = 0
        for member in members:
            if not _member_ok(member):
                raise UploadError(f"unsafe path or file type in archive: {member.name[:80]!r}")
            unpacked += max(member.size, 0)
        if unpacked > MAX_UNPACKED:
            raise UploadError(
                f"archive unpacks to {unpacked // (1024 * 1024)} MB; "
                f"limit is {MAX_UNPACKED // (1024 * 1024)} MB"
            )
        python = _looks_like_python(tar)
        npm = _looks_like_npm(tar)

    if python:
        return "python"
    if npm:
        return "npm"
    raise UploadError(
        "no setup.py, pyproject.toml or package/package.json inside -- "
        "this is an archive, but not a package we can install and import"
    )


def wrap_python_module(data: bytes, filename: str) -> tuple[bytes, str]:
    """Turn one .py file into an sdist so the same three phases can run on it.

    The build hook is ours, not the package's, so phase 1 proves nothing here -- but phase 2
    imports the module with the probes attached, which is the phase that matters for a single
    file someone pasted from the internet.
    """
    if len(data) > MAX_PY_BYTES:
        raise UploadError(f"python file is larger than {MAX_PY_BYTES // (1024 * 1024)} MB")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadError("python file is not UTF-8 text") from exc

    stem = re.sub(r"[^A-Za-z0-9_]+", "_", Path(filename).stem).strip("_") or "module"
    if stem[0].isdigit():
        stem = "m_" + stem
    module = stem[:60]
    version = "0.0.0"

    setup = (
        "from setuptools import setup\n\n"
        f'setup(name="{module}", version="{version}", py_modules=["{module}"],\n'
        '      description="Uploaded module, triaged as a source distribution")\n'
    )

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, payload in (
            (f"{module}/{module}.py", data),
            (f"{module}/setup.py", setup.encode()),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mtime = int(time.time())
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(payload))
    return buf.getvalue(), f"{module}-{version}.tar.gz"


def accept(data: bytes, filename: str, dest_dir: Path) -> tuple[Path, str]:
    """Validate, save, and return (path, kind). Raises UploadError with a readable reason."""
    if not data:
        raise UploadError("empty upload")
    if len(data) > MAX_BYTES:
        raise UploadError(f"file is larger than {MAX_BYTES // (1024 * 1024)} MB")

    name = _safe_name(filename)
    kind = ""

    if data.startswith(ZIP_MAGIC):
        raise UploadError(
            "zip is not accepted -- pip installs a zip, our pipeline reads tar. "
            "Send the sdist (.tar.gz), or a single .py file."
        )
    if data.startswith(GZIP_MAGIC) or name.endswith((".tar.gz", ".tgz")):
        if not data.startswith(GZIP_MAGIC):
            raise UploadError("name says tar.gz but the bytes are not gzip")
        kind = inspect_tar(data)
    elif name.endswith(".py") or (b"\n" in data[:4096] and b"import " in data[:4096]):
        data, name = wrap_python_module(data, name)
        kind = "python"
    else:
        raise UploadError(
            f"{name} is not a package format we read -- send a .tar.gz sdist, an npm .tgz, "
            "or a single .py file"
        )

    if not name.endswith((".tar.gz", ".tgz")):
        name = name + ".tar.gz"

    digest = hashlib.sha256(data).hexdigest()[:12]
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    # One directory per upload, the file keeps its own name: the rail then shows
    # "harborline-2.9.1.tar.gz" instead of a timestamp with a hash in the middle.
    target_dir = dest_dir / f"{stamp}-{digest}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / name
    target.write_bytes(data)

    # Re-check what we are about to hand to the pipeline, from disk, not from the bytes in hand.
    inspect_tar(target.read_bytes())
    return target, kind
