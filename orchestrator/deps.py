"""Read the dependency list without running anything.

The list lives in PKG-INFO, which is plain text inside the archive. Parsing it is the
only way to see dependencies without executing a build backend -- which is exactly what
we are trying to avoid. Nothing here imports the package.
"""

from __future__ import annotations

import re
import tarfile
from pathlib import Path

REQUIRES = re.compile(r"^Requires-Dist:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
ENV_MARKER = re.compile(r"\s*;.*$")
LEGACY_PARENS = re.compile(r"^([A-Za-z0-9_.\-]+)\s*\((.+)\)$")


def normalise(spec):
    """'six (>=1.16)' -> 'six>=1.16'. PEP 345 parentheses, still common in the wild."""
    spec = ENV_MARKER.sub("", spec).strip()
    match = LEGACY_PARENS.match(spec)
    if match:
        return f"{match.group(1)}{match.group(2).strip()}"
    return spec


def declared_dependencies(package_path, limit=40):
    """Requirement strings from PKG-INFO. Empty list means 'none declared'."""
    path = Path(package_path)
    try:
        with tarfile.open(path, "r:*") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                if not member.name.endswith("PKG-INFO"):
                    continue
                handle = tf.extractfile(member)
                if handle is None:
                    continue
                text = handle.read(200_000).decode("utf-8", "replace")
                found = [normalise(m) for m in REQUIRES.findall(text)]
                return [f for f in found if f][:limit]
    except (tarfile.TarError, OSError):
        return []
    return []
