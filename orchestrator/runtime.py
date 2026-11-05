"""Which runtime does this artifact belong to?

Decided from the archive contents, not from the file extension: a `.tgz` can hold
anything, and guessing from a name is how you end up running the wrong command on a
hostile file.
"""

from __future__ import annotations

import tarfile
from pathlib import Path


def detect(package_path):
    """Return 'node' or 'python'."""
    try:
        with tarfile.open(Path(package_path), "r:*") as tf:
            names = [m.name for m in tf.getmembers() if m.isfile()]
    except (tarfile.TarError, OSError):
        return "python"

    has_pkg_json = any(n.endswith("package.json") for n in names)
    has_python = any(n.endswith(("setup.py", "PKG-INFO", "pyproject.toml")) for n in names)
    if has_pkg_json and not has_python:
        return "node"
    return "python"
