"""Verdict: rules first, model second, and nothing that the evidence cannot support.

Two independent paths produce a risk level:

1. `rule_findings` -- deterministic, reads only the artifacts. Runs without a model,
   which is why the test suite can cover it on a laptop with no API key.
2. `model_findings` -- asks the model, then `validate` throws away every claim whose
   `source` is not a reference that actually exists in this run.

The second path is allowed to *raise* the risk level only if at least one of its
findings survived validation. A model that invents a source cannot move the verdict.
That is the whole point of the design, and it is what the demo shows.
"""

from __future__ import annotations

import json
from pathlib import Path

SEVERITY = {"info": 0, "low": 1, "medium": 2, "high": 3}
RISK_FROM_TOP = {0: "low", 1: "low", 2: "medium", 3: "high"}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def _read_json(path):
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"_parse_error": True}


def egress_summary(path):
    """Collapse the proxy log into counts. Absent log != clean log."""
    p = Path(path)
    if not p.is_file():
        return {"collected": False, "denied": 0, "allowed": 0, "denied_hosts": []}
    entries = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    denies = [e for e in entries if e.get("decision") == "deny"]
    allows = [e for e in entries if str(e.get("decision", "")).startswith("allow")]
    return {
        "collected": True,
        "total": len(entries),
        "denied": len(denies),
        "allowed": len(allows),
        "denied_hosts": sorted({str(e.get("host")) for e in denies if e.get("host")}),
    }


def rule_findings(evidence):
    """Deterministic findings. No model, no guessing, no severity inflation."""
    out = []
    ex = evidence.get("exec")
    eg = evidence.get("egress") or {}
    fs = evidence.get("fsdiff")

    if ex is None:
        out.append({
            "severity": "medium", "source": "exec.json",
            "claim": "The run produced no exec.json, so the build hook outcome is unknown.",
        })
    elif ex.get("_parse_error"):
        out.append({
            "severity": "medium", "source": "exec.json",
            "claim": "exec.json exists but is not valid JSON.",
        })
    else:
        code = ex.get("pip_exit")
        if code not in (0, None):
            out.append({
                "severity": "low", "source": "exec.json",
                "claim": f"The build hook exited with status {code}.",
            })
        dur = ex.get("duration_s")
        if isinstance(dur, (int, float)) and dur > 60:
            out.append({
                "severity": "info", "source": "exec.json",
                "claim": f"The run took {dur}s, which is long for a build hook.",
            })

    if eg.get("denied", 0) > 0:
        hosts = ", ".join(eg.get("denied_hosts") or []) or "an unnamed host"
        out.append({
            "severity": "high", "source": "egress.jsonl",
            "claim": f"{eg['denied']} outbound connection attempt(s) were blocked, "
                     f"targeting {hosts}.",
        })

    if fs is None:
        # Not collected is not the same as clean. Say so rather than implying safety.
        out.append({
            "severity": "info", "source": "fsdiff.json",
            "claim": "No filesystem diff was collected for this run; host-side "
                     "changes were not measured.",
        })
    elif fs.get("changed", 0) > 0:
        paths = ", ".join((fs.get("paths") or [])[:5]) or "unlisted paths"
        out.append({
            "severity": "high", "source": "fsdiff.json",
            "claim": f"{fs['changed']} path(s) changed outside the work directory: {paths}.",
        })

    return out


def risk_from_findings(findings):
    top = max((SEVERITY.get(f.get("severity"), 0) for f in findings), default=0)
    return RISK_FROM_TOP[top]


def evidence_refs(evidence):
    """Every source string a claim is allowed to cite for this run."""
    refs = set()
    if evidence.get("exec") is not None:
        refs.add("exec.json")
        if isinstance(evidence["exec"], dict):
            refs.update("exec.json." + k for k in evidence["exec"])
    if (evidence.get("egress") or {}).get("collected"):
        refs.add("egress.jsonl")
    if evidence.get("fsdiff") is not None:
        refs.add("fsdiff.json")
    refs.update(evidence.get("artifacts") or {})
    return refs


def validate(findings, evidence):
    """Split model findings into grounded and rejected. Rejection carries a reason."""
    refs = evidence_refs(evidence)
    accepted, rejected = [], []
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        src = str(f.get("source") or "")
        claim = str(f.get("claim") or f.get("text") or "").strip()
        if not claim:
            continue
        if src in refs:
            accepted.append({"severity": f.get("severity", "medium"), "source": src, "claim": claim})
        else:
            rejected.append({
                "source": src or "(none)",
                "claim": claim,
                "reason": "cited source is not part of this run's evidence",
            })
    return accepted, rejected


MODEL_PROMPT = """You triage an untrusted Python package that was executed in a sandbox.

You get JSON evidence only. You did not see the package and you must not speculate.

Rules:
- Every finding needs a "source" that is EXACTLY one of these: {refs}
- If evidence is missing, say so instead of assuming the run was clean.
- risk: "low" | "medium" | "high"
- Answer with JSON only, no prose, no code fences:
{{"risk": "...", "summary": "...", "findings": [{{"claim": "...", "source": "...", "severity": "info|low|medium|high"}}]}}
"""


def _extract_json(text):
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1] if "```" in stripped[3:] else stripped
        stripped = stripped.lstrip("json").strip() if stripped.lower().startswith("json") else stripped
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(stripped[start:end + 1])
    except json.JSONDecodeError:
        return None


def verdict(evidence, question=None, chat=None, model=None):
    """Combine rules and (optionally) a model into one auditable verdict."""
    rule = rule_findings(evidence)
    base_risk = risk_from_findings(rule)

    result = {
        "risk": base_risk,
        "findings": rule,
        "rejected_claims": [],
        "summary": None,
        "model_used": False,
        "notes": [],
    }

    if chat is None:
        result["notes"].append("no model configured; verdict is rule-based only")
        return result

    refs = sorted(evidence_refs(evidence))
    prompt = MODEL_PROMPT.format(refs=", ".join(refs) or "(none)")
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps({
            "question": question or "Is this package safe to install on a developer machine?",
            "evidence": evidence,
        }, ensure_ascii=False, indent=2)},
    ]

    try:
        raw = chat(messages, model=model) if model else chat(messages)
    except Exception as exc:  # noqa: BLE001 - any failure must degrade, not crash
        result["notes"].append(f"model call failed: {type(exc).__name__}: {exc}")
        return result

    parsed = _extract_json(raw)
    if not parsed:
        result["notes"].append("model answer was not parseable as JSON; rules kept")
        return result

    result["model_used"] = True
    result["summary"] = parsed.get("summary")
    accepted, rejected = validate(parsed.get("findings"), evidence)
    result["rejected_claims"] = rejected
    result["findings"] = rule + accepted

    model_risk = str(parsed.get("risk") or "").lower()
    if model_risk not in RISK_ORDER:
        result["notes"].append(f"model returned an unknown risk level: {model_risk!r}")
    elif RISK_ORDER[model_risk] > RISK_ORDER[base_risk]:
        if accepted:
            result["risk"] = model_risk
            result["notes"].append("model raised the risk level, and its findings were grounded")
        else:
            result["notes"].append(
                "model tried to raise the risk level without a grounded finding; ignored")
    if rejected:
        result["notes"].append(
            f"{len(rejected)} model claim(s) rejected: cited sources not in the evidence")

    return result
