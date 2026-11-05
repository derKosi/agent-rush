"""What to do when a run tells us nothing.

The playbook asks for "errors can be fed back for retries". The honest version of
that is narrow: a retry only helps when the failure is about *our* limits, not about
the package. A timeout is our limit and doubling it can work. A build that fails
before any probe runs is the package's problem; retrying it burns a container and
produces the same nothing. So the rules decide, and the run says which happened.
"""

from __future__ import annotations

RETRY_TIMEOUT = "timeout"
BUILD_FAILED = "build_failed"
NO_RESULT = "no_result"


def diagnose(result, evidence):
    """Return None if the run produced something usable, else a finding dict."""
    if result.get("timed_out"):
        return {
            "kind": RETRY_TIMEOUT,
            "retryable": True,
            "reason": "the run hit the wall-clock limit before it produced any evidence",
        }

    exec_ = evidence.get("exec")
    if exec_ is None:
        return {
            "kind": NO_RESULT,
            "retryable": False,
            "reason": "the run produced no exec.json, so the outcome is unknown",
        }

    probes = evidence.get("probe") or {}
    egress = evidence.get("egress") or {}
    learned_something = bool(probes.get("attempts")) or egress.get("denied", 0) > 0
    if exec_.get("pip_exit") not in (0, None) and not learned_something:
        return {
            "kind": BUILD_FAILED,
            "retryable": False,
            "reason": "the build failed before any probe ran, so there is nothing to judge",
        }
    return None


def next_timeout(current, ceiling=300, factor=2):
    """One retry, bounded. Returns None when there is no room left."""
    proposed = min(current * factor, ceiling)
    return proposed if proposed > current else None
