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


# Advisories label themselves inconsistently: GHSA reviewed entries carry
# database_specific.severity, others only a CVSS vector (often v4, whose base score is a
# different algorithm). So this maps the *label* where it exists, falls back to a coarse
# reading of the impact metrics, and says "unknown" rather than inventing a number.
LABEL_SCORE = {"CRITICAL": 9.5, "HIGH": 8.0, "MODERATE": 5.0, "MEDIUM": 5.0, "LOW": 2.5}
IMPACT_WEIGHT = {"H": 3, "L": 1, "N": 0}


def _score(vuln):
    """(score 0-10 or None, label) for one advisory."""
    label = ((vuln.get("database_specific") or {}).get("severity") or "").upper()
    if label in LABEL_SCORE:
        return LABEL_SCORE[label], label

    for entry in vuln.get("severity") or []:
        vector = str(entry.get("score") or "")
        if not vector:
            continue
        parts = dict(p.split(":", 1) for p in vector.split("/")[1:] if ":" in p)
        impact = [parts.get(k, "N") for k in ("VC", "VI", "VA", "SC", "SI", "SA")]
        if not any(k in parts for k in ("VC", "VI", "VA")):
            # CVSS v3 vector: only the impact trio is read here, coarsely.
            impact = [parts.get(k, "N") for k in ("C", "I", "A")]
        weight = max((IMPACT_WEIGHT.get(v, 0) for v in impact), default=0)
        if weight >= 3:
            return 8.0, "high (from impact metrics)"
        if weight >= 1:
            return 5.0, "medium (from impact metrics)"
        return 2.0, "low (from impact metrics)"
    return None, "unknown"


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
        score, label = _score(vuln)
        out.append({
            "id": vuln.get("id"),
            "summary": (vuln.get("summary") or "")[:200],
            "aliases": (vuln.get("aliases") or [])[:4],
            "score": score,
            "severity": label,
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
            scores = [v["score"] for v in unique if v.get("score") is not None]
            results.append({"package": name, "version": version,
                            "count": len(unique), "vulns": unique[:8],
                            "max_score": max(scores) if scores else None})
    return results


# --- how far behind is it? -------------------------------------------------------------
# A dependency can be perfectly fine and still three years old. That is not a
# vulnerability, but it is the thing a reviewer wants to see first, and it is cheap:
# one request to PyPI's JSON API per artifact, no key.

LATEST_CACHE = {}


def latest_version(name, timeout=6, fetch=None):
    if name in LATEST_CACHE:
        return LATEST_CACHE[name]
    fetch = fetch or _get_json
    try:
        data = fetch(f"https://pypi.org/pypi/{name}/json", timeout)
        value = (data.get("info") or {}).get("version")
    except Exception:  # noqa: BLE001 - offline is not an error, it is "unknown"
        value = None
    LATEST_CACHE[name] = value
    return value


def _get_json(url, timeout):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _version_key(text):
    parts = []
    for chunk in str(text).replace("-", ".").split("."):
        parts.append(int(chunk) if chunk.isdigit() else 0)
    return tuple(parts)


def outdated(resolved, *, enabled=None, fetch=None, timeout=6):
    """Artifacts whose version is behind the newest release on PyPI."""
    if enabled is None:
        enabled = os.environ.get("AR_OUTDATED_CHECK", "on").lower() != "off"
    if not enabled:
        return []
    out = []
    for item in resolved:
        name, version = parse_artifact(item.get("file", ""))
        if not name or not version:
            continue
        newest = latest_version(name, timeout=timeout, fetch=fetch)
        if not newest:
            continue
        if _version_key(version) < _version_key(newest):
            out.append({"package": name, "version": version, "latest": newest})
    return out
