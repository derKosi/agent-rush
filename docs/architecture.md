# Architecture

## What the system does

A user submits an untrusted Python source package (sdist tarball) plus an optional question.
The agent:

1. **Inspects** — reads `setup.py`, `pyproject.toml`, the file list, and any install hooks
   without executing them.
2. **Plans** — picks the probes worth running (always: execute the build hook; optionally:
   read a decoy secret path, attempt egress, attempt a detached child process).
3. **Dispatches** — starts a container with the containment policy applied and the proxy in
   the egress path.
4. **Executes** — the build hook runs as an unprivileged user inside the container.
5. **Observes** — collects three independent evidence sources (below).
6. **Verdicts** — maps observed attempts to a risk level and returns a downloadable report.

## Two passes, on purpose

The build hook is one place a payload can hide. The more common one is the first import:
a package that is perfectly polite while installing and exfiltrates when a developer
types `import`. A single-pass tool reports that package as clean, which is worse than
reporting nothing.

So each run does two passes in the same hardened container:

1. **build** — `pip install` runs the hook, with the probes the planner chose
2. **import** — the installed distribution is found via its metadata and each top-level
   module is imported deliberately

The import pass writes `import_probe.json` and `import.log`, and its egress runs through
the same deny proxy. A finding from this phase is cited as `import_pass`, so the report
says which phase produced it.

## The dependency phase, and why it has network

A third phase lists what the package would pull in. `Requires-Dist` is read from
`PKG-INFO` as plain text — no execution — and the resulting requirements are fetched with
`pip download --only-binary=:all:` into a separate container.

Two deliberate choices:

- **Network on.** This is the only phase that needs it, and it is a different container
  with a different job. Mixing it into the probe run would mean the sandbox that executes
  hostile code also has egress.
- **Wheels only.** Resolving an sdist runs its build backend, which would execute exactly
  the code we are trying not to run. A dependency that only exists as an sdist is therefore
  not resolved, and the report says so rather than silently skipping it.

## The three evidence sources

Containment is claimed only where it is *recorded*. Each run produces:

| Source | Produced by | Answers |
|---|---|---|
| `egress.jsonl` | deny proxy, outside the container | what network destinations were attempted, and the decision |
| `exec.json` | sandbox entrypoint | exit status, duration, the probe's own self-report |
| `fsdiff.json` | host-side scan of the work dir before/after | what the process actually changed |

The agent may *describe* a risk. Only these three files are treated as fact. A verdict the
evidence does not support is a bug.

## Containment invariants

The container **must** satisfy all of these, enforced in `sandbox/run.sh`:

- `--network none` (baseline) or an internal Docker network whose only route out is the proxy
- `--read-only` root filesystem; the only writable paths are the mounted work dir and tmpfs
- `--tmpfs /tmp:rw,noexec,nosuid,size=<n>`
- `--user 10001:10001`, non-root, no shell login for that user
- `--cap-drop ALL`, `--security-opt no-new-privileges`
- `--pids-limit`, `--memory` with `--memory-swap` equal, `--cpus`
- wall-clock timeout enforced by the orchestrator, not by the container
- one container per task, `--rm`, destroyed afterwards

Invariant that matters most in review: **no credential ever enters the container.** The
inference key lives in the orchestrator process. The sandbox gets a package and nothing else.

## Two egress modes

- **Mode A — `--network none`.** Simplest, strongest. An attempt surfaces as a socket error;
  the evidence is the process result, not a proxy log. Used when the proxy is unavailable.
- **Mode B — internal network + proxy.** The proxy denies by default and logs the attempted
  host, so the evidence shows *intent* (the URL) and *decision* (403) together. Preferred for
  the demo because it is legible to a non-engineer.

Mode B is not a weakening: the proxy is the only route, and it denies everything not on a
per-task allowlist that is empty by default.

## Why a local tarball and not a real registry

`pip install --no-deps --no-build-isolation <file>` removes three failure modes at once:
registry availability, rate limits, and the need to publish anything hostile. The build hook
still executes real code as the installing user — which is the entire attack surface under
test. The fixture is authored by us and committed, so the demo is reproducible and reviewable.

## Non-goals

- Not a general malware analysis platform. One artifact class, one execution pattern.
- Not a runtime firewall for production installs. It is a triage gate you run *before* the
  install touches a developer machine or CI runner.
- No browser automation. Track 1 allows it; the plan cuts it first if the runner slips.
