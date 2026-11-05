"""Plan step: the model decides which probes the sandbox should run.

The menu is fixed and implemented by the fixture. The model may choose a subset
and must justify it -- it cannot invent a capability, and anything outside the menu
is dropped by `validate_plan`. If the model is unavailable or returns nonsense, the
plan falls back to running everything, which is the safe default.
"""

from __future__ import annotations

import json
import os

PROBES = {
    "write_outside": "the build hook writes outside the work directory",
    "egress": "the build hook attempts an outbound HTTP request",
    "decoy_key": "the build hook tries to read an SSH private key",
    "detached_child": "the build hook starts a background process",
}
ALL_PROBES = tuple(PROBES)

PLANNER_PROMPT = """You plan a sandbox triage run for an untrusted Python package.

You get a static description of the package. You do not execute anything.

Choose which probes the sandbox should run. Available probes:
{menu}

Answer with JSON only:
{{"probes": ["..."], "reason": "one or two sentences"}}

Rules:
- only values from the list above
- choose at least one
- if the package looks harmless, still choose the cheap probes; the run is the evidence
"""


def static_profile(package_path):
    """What we can learn without running anything."""
    import tarfile
    from pathlib import Path

    p = Path(package_path)
    profile = {"name": p.name, "bytes": p.stat().st_size, "members": [], "has_setup_py": False,
               "references_network": False, "references_subprocess": False}
    try:
        with tarfile.open(p, "r:*") as tf:
            names = [m.name for m in tf.getmembers() if m.isfile()]
            profile["members"] = names[:40]
            for m in tf.getmembers():
                if not m.isfile() or m.size > 1_000_000:
                    continue
                if not m.name.endswith((".py", ".cfg", ".toml")):
                    continue
                fh = tf.extractfile(m)
                if fh is None:
                    continue
                body = fh.read().decode("utf-8", "replace")
                if m.name.endswith("setup.py"):
                    profile["has_setup_py"] = True
                for token, flag in (("urllib", "references_network"), ("requests", "references_network"),
                                    ("socket", "references_network"), ("subprocess", "references_subprocess"),
                                    ("Popen", "references_subprocess")):
                    if token in body:
                        profile[flag] = True
    except (tarfile.TarError, OSError) as exc:
        profile["error"] = f"{type(exc).__name__}: {exc}"
    return profile


def validate_plan(raw):
    """Keep only probes from the menu. Unknown entries are reported, not trusted."""
    chosen, rejected = [], []
    for item in raw or []:
        name = str(item).strip()
        if not name:
            continue
        if name in PROBES:
            if name not in chosen:      # a duplicate is not a rejection
                chosen.append(name)
        else:
            rejected.append(name)
    return chosen, rejected


def plan(package_path, question=None, chat=None, model=None):
    """Return {"probes": [...], "reason": str, "source": "model"|"default"}."""
    profile = static_profile(package_path)
    fallback = {"probes": list(ALL_PROBES), "reason": "no model configured; running every probe",
                "source": "default", "rejected": [], "profile": profile}
    if chat is None:
        return fallback

    menu = "\n".join(f"- {k}: {v}" for k, v in PROBES.items())
    messages = [
        {"role": "system", "content": PLANNER_PROMPT.format(menu=menu)},
        {"role": "user", "content": json.dumps(
            {"question": question or "Is this package safe to install?",
             "package": profile}, ensure_ascii=False, indent=2)},
    ]
    try:
        raw = chat(messages, model=model) if model else chat(messages)
    except Exception as exc:  # noqa: BLE001
        fallback["reason"] = f"model call failed ({type(exc).__name__}); running every probe"
        return fallback

    start, end = raw.find("{"), raw.rfind("}")
    try:
        parsed = json.loads(raw[start:end + 1]) if start != -1 else {}
    except json.JSONDecodeError:
        parsed = {}

    chosen, rejected = validate_plan(parsed.get("probes"))
    if not chosen:
        fallback["reason"] = "model returned no usable probe; running every probe"
        fallback["rejected"] = rejected
        return fallback

    return {
        "probes": chosen,
        "reason": str(parsed.get("reason") or "").strip()[:500],
        "source": "model",
        "rejected": rejected,
        "profile": profile,
    }


def probes_env(plan_result):
    return ",".join(plan_result.get("probes") or ALL_PROBES)
