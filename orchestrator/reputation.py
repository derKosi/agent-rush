"""Known vulnerabilities for the resolved dependency tree.

The hashes tell you *what* you would install. This tells you whether that exact version
is already known to be broken. It is a lookup against OSV (osv.dev), which aggregates
GitHub Security Advisories, PyPA, RustSec and friends -- no API key, no scraping.

Deliberately optional and off the sandbox path: this runs in the orchestrator process,
not inside a container, because it talks to a third party about a package we have not
executed. AR_OSV=off disables it; AR_OSV_URL points at a mirror.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_URL = "https://api.osv.dev/v1/query"

# six-1.17.0-py2.py3-none-any.whl  or  package-1.0.0.tgz
# Greedy on the version: "six-1.17.0-py2.py3-none-any.whl" must give 1.17.0, not 1.
WHEEL = re.compile(r"^(?P<name>.+?)-(?P<version>\d[^-]*)(-[^-]+)*\.whl$")
TGZ = re.compile(r"^(?P<name>.+?)-(?P<version>\d[^-]*?)\.tgz$")


def parse_artifact(filename):
    """(name, version) from a wheel or npm tarball name, or (None, None)."""
    for pattern in (WHEEL, TGZ):
        match = pattern.match(filename)
        if match:
            return match.group("name"), match.group("version")
    return None, None


def _query(url, name, version, ecosystem, timeout):
    payload = json.dumps({"package": {"name": name, "ecosystem": ecosystem},
                          "version": version}).encode()
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
    if not body.strip():
        return []
    data = json.loads(body)
    out = []
    for vuln in data.get("vulns") or []:
        out.append({
            "id": vuln.get("id"),
            "summary": (vuln.get("summary") or "")[:200],
            "aliases": (vuln.get("aliases") or [])[:4],
        })
    return out


def dedupe(vulns):
    """GHSA and PYSEC report the same CVE twice. Collapse by shared alias."""
    groups = []
    for vuln in vulns:
        keys = {vuln.get("id")} | set(vuln.get("aliases") or [])
        keys.discard(None)
        hit = next((g for g in groups if g["keys"] & keys), None)
        if hit is None:
            groups.append({"keys": set(keys), "best": vuln})
        else:
            hit["keys"] |= keys
            if len(vuln.get("summary") or "") > len(hit["best"].get("summary") or ""):
                hit["best"] = vuln
    return [g["best"] for g in groups]


def check(resolved, *, enabled=None, url=None, timeout=8, fetch=None):
    """Look up every resolved artifact. Returns a list of findings, never raises."""
    if enabled is None:
        enabled = os.environ.get("AR_OSV", "on").lower() != "off"
    if not enabled or not resolved:
        return []

    url = url or os.environ.get("AR_OSV_URL", DEFAULT_URL)
    fetch = fetch or _query
    ecosystem = os.environ.get("AR_OSV_ECOSYSTEM", "PyPI")

    results = []
    for item in resolved:
        name, version = parse_artifact(item.get("file", ""))
        if not name or not version:
            continue
        try:
            vulns = fetch(url, name, version, ecosystem, timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError,
                json.JSONDecodeError) as exc:
            results.append({"package": name, "version": version, "error": type(exc).__name__})
            continue
        if vulns:
            unique = dedupe(vulns)
            results.append({"package": name, "version": version,
                            "count": len(unique), "vulns": unique[:8]})
    return results
