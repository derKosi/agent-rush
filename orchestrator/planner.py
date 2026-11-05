"""Plan step: the model decides which probes the sandbox should run.

The menu is fixed and implemented by the fixture. The model may choose a subset
and must justify it -- it cannot invent a capability, and anything outside the menu
is dropped by `validate_plan`. If the model is unavailable or returns nonsense, the
plan falls back to running everything, which is the safe default.
"""

from __future__ import annotations

import ast
import json
import os

PROBES = {
    "write_outside": "the build hook writes outside the work directory",
    "egress": "the build hook attempts an outbound HTTP request",
    "decoy_key": "the build hook tries to read an SSH private key",
    "detached_child": "the build hook starts a background process",
}
ALL_PROBES = tuple(PROBES)

# The model may add probes; it may not remove these. Without a floor, a package that
# talks the model out of running the egress probe also removes the evidence that would
# have caught it -- the plan step would become an injection surface with consequences.
MANDATORY_PROBES = ("egress", "write_outside")

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
                "source": "default", "rejected": [], "profile": profile,
                "mandatory": list(MANDATORY_PROBES)}
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

    final = [p for p in MANDATORY_PROBES] + [p for p in chosen if p not in MANDATORY_PROBES]
    return {
        "probes": final,
        "from_model": chosen,
        "mandatory": list(MANDATORY_PROBES),
        "reason": str(parsed.get("reason") or "").strip()[:500],
        "source": "model",
        "rejected": rejected,
        "profile": profile,
    }


def probes_env(plan_result):
    return ",".join(plan_result.get("probes") or ALL_PROBES)


SCRIPT_PROMPT = """Write a short Python 3 script that inspects an untrusted package archive.

Constraints, all mandatory:
- stdlib only, no third-party imports
- read the archive at sys.argv[1] with tarfile; never import or execute the package
- no network, no subprocess, no eval/exec
- print ONE JSON object to stdout: {"summary": "...", "findings": [{"claim": "...", "severity": "info|low|medium|high"}]}
- at most 40 lines, no prose outside the code block

Answer with the code only, in a single ```python block."""

# Static audit of the script the model wrote. Two earlier attempts matched text and
# both failed the same way: a regex like os\.system fires inside the string
# "subprocess|os\.system|popen". So this walks the AST instead -- real imports and real
# calls only. It is not the defence (the sandbox is); it just refuses code that wants
# capabilities the task does not need.
BANNED_MODULES = {"subprocess", "socket", "urllib", "requests", "ctypes", "http", "ftplib"}
BANNED_OS_ATTRS = {"system", "popen", "execv", "execve", "spawnv", "spawnl"}


def audit_script(code):
    """Return None if the script is acceptable, else a reason string."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in BANNED_MODULES:
                    return f"imports {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in BANNED_MODULES:
                return f"imports from {node.module}"
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == "os" and func.attr in BANNED_OS_ATTRS:
                    return f"calls os.{func.attr}"
                if func.value.id in BANNED_MODULES:
                    return f"calls {func.value.id}.{func.attr}"
            elif isinstance(func, ast.Name) and func.id in {"eval", "exec", "__import__"}:
                return f"calls {func.id}"
    return None


def write_script(package_path, question=None, chat=None, model=None):
    """Ask the model for an inspection script. Returns dict with code or a reason."""
    if chat is None:
        return {"code": None, "reason": "no model configured"}
    profile = static_profile(package_path)
    messages = [
        {"role": "system", "content": SCRIPT_PROMPT},
        {"role": "user", "content": json.dumps(
            {"question": question or "Is this package safe to install?",
             "package": profile}, ensure_ascii=False, indent=2)},
    ]
    try:
        raw = chat(messages, model=model) if model else chat(messages)
    except Exception as exc:  # noqa: BLE001
        return {"code": None, "reason": f"model call failed: {type(exc).__name__}"}

    code = raw
    if "```" in raw:
        parts = raw.split("```")
        if len(parts) >= 2:
            code = parts[1]
            if code.lstrip().startswith("python"):
                code = code.lstrip()[6:]
    code = code.strip()
    if not code:
        return {"code": None, "reason": "model returned no code"}

    problem = audit_script(code)
    if problem:
        return {"code": None, "reason": f"refused: {problem}", "rejected_code": code}
    if len(code.splitlines()) > 60:
        return {"code": None, "reason": "refused: script longer than 60 lines",
                "rejected_code": code}
    return {"code": code, "reason": "ok"}
