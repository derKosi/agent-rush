"""SARIF 2.1.0 output.

Honest framing: this is a *reporting* format, not code analysis. GitHub ingests SARIF from
any producer via upload-sarif, so a run becomes visible where a team already looks. The
locations are the evidence files, not source lines -- claiming source locations we do not
have would be a lie the format makes easy to tell.
"""

from __future__ import annotations

LEVEL = {"high": "error", "medium": "warning", "low": "note", "info": "note"}


def build(record):
    verdict = record.get("verdict") or {}
    findings = verdict.get("findings") or []
    run_id = record.get("id", "unknown")

    rules, seen = [], set()
    for finding in findings:
        source = str(finding.get("source") or "unknown")
        rule_id = f"agent-rush/{source}"
        if rule_id in seen:
            continue
        seen.add(rule_id)
        rules.append({
            "id": rule_id,
            "name": source,
            "shortDescription": {"text": f"Finding from {source}"},
            "defaultConfiguration": {"level": LEVEL.get(finding.get("severity"), "note")},
        })

    results = []
    for finding in findings:
        source = str(finding.get("source") or "unknown")
        results.append({
            "ruleId": f"agent-rush/{source}",
            "level": LEVEL.get(finding.get("severity"), "note"),
            "message": {"text": str(finding.get("claim") or "")[:1000]},
            "properties": {"severity": finding.get("severity"), "run": run_id},
        })

    rejected = verdict.get("rejected_claims") or []
    for claim in rejected:
        results.append({
            "ruleId": "agent-rush/rejected-claim",
            "level": "note",
            "message": {"text": f"Rejected model claim: {str(claim.get('claim'))[:400]} "
                                f"(cited {claim.get('source')})"},
            "properties": {"run": run_id},
        })
        if "agent-rush/rejected-claim" not in seen:
            seen.add("agent-rush/rejected-claim")
            rules.append({
                "id": "agent-rush/rejected-claim",
                "name": "rejected-claim",
                "shortDescription": {"text": "A model claim that cited a source not in this run"},
                "defaultConfiguration": {"level": "note"},
            })

    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "agent-rush",
                "version": "0.1",
                "informationUri": "https://github.com/derKosi/agent-rush",
                "rules": rules,
            }},
            "automationDetails": {"id": run_id},
            "results": results,
            "properties": {
                "risk": verdict.get("risk"),
                "model_used": verdict.get("model_used"),
                "runtime": record.get("runtime"),
            },
        }],
    }
