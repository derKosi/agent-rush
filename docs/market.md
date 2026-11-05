# Where this sits

Written before submission, from what the tools actually claim on their own sites — not from
benchmarks nobody ran.

## The neighbourhood

| Category | Examples | What they do | Where this differs |
|---|---|---|---|
| **Behavioural package analysis** | Socket.dev, Phylum | Static + behavioural signals on packages, blocked at install time via a proxy or registry | They ship a curated signal set and a hosted verdict. We ship an *evidence trail*: every claim in the report points at a file you can open |
| **Vulnerability databases** | Snyk, GitHub Advisory / Dependabot, OSV | Match your dependency tree against known advisories | We do this too — by querying OSV rather than owning a database. It is table stakes, not our product |
| **Sandbox detonation** | Any.run, Cuckoo, Joe Sandbox | Run an unknown binary, report behaviour, a human reads it | Same primitive, different consumer: those feed an analyst, this returns a decision to a pipeline, with a risk level and a machine-readable report |
| **Sandboxes as infrastructure** | E2B, Modal, Microsandbox | Give you a container to run agent code in | Infrastructure, no opinion about packages. We are the opinion |
| **Provenance / signing** | Sigstore, in-toto, SLSA | Prove *who built* an artifact | Orthogonal: provenance says where it came from, this says what it does when it runs |

## What we actually claim

1. **A package can be quiet while building.** Two phases, not one. Almost every scanner stops
   at the install hook.
2. **The verdict cannot contradict its own evidence.** The risk floor comes from rules; a model
   claim citing a source that is not in the run is dropped. That is checkable in the report.
3. **Self-hostable and cheap.** One 2 GB VM, no per-seat pricing, MIT.

## What we explicitly do not claim

- Not a malware detector. There are no signatures and no reputation graph.
- Not a runtime agent. What a package does inside a request handler is out of scope.
- Not a general supply-chain firewall. Python sdists and npm tarballs, one artifact per run.

## Why the honesty is the strategy

Every tool in this space eventually meets a security team that asks "show me why". A scanner
that says "high risk, trust us" loses that conversation. One that says "here are three blocked
attempts, the proxy log, and the one claim I refused to believe" wins it — even when its
detection rate is lower. That is the bet this project makes.

## If this were a company

- **Customer**: platform or AppSec team at 20–200 engineers, already running Dependabot.
- **Wedge**: the two-phase check in the release pipeline, where the artifact exists and the
  blast radius is real.
- **Pricing**: per repository, not per seat, because the buyer is a team budget.
- **Moat**: none yet. The evidence model is a design choice, easy to copy. The defensible part
  would be a corpus of packages whose build and import behaviour are both known — which is a
  data problem, not a code problem.
