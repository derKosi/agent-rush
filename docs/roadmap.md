# Roadmap

Written the day before submission, so it describes what exists rather than what was hoped for.

## Where it stands

Two runtimes (Python sdist, npm tarball), three execution phases (build, import, resolve),
one evidence model the sandboxed process cannot write to. 89 tests, six fixtures, a CLI that
exits non-zero, and a verdict whose risk floor comes from rules rather than from the model.

Known limits, stated in the README: dependencies are listed and checked against OSV but
never executed; what runs after the first import is out of scope; dead code is never seen.

## Before submission

- Record the demo video. Everything else is done.
- Freeze. No new features; only fixes for things that are visibly wrong.

## Next, roughly a week of work

1. **Judge the dependency tree, not just list it.** Each resolved wheel goes through the same
   two phases. Cost: one container per dependency, so it needs a cap (`--max-deps 10`) and a
   "truncated" note in the report.
2. **Adversarial suite as a published artifact.** Four defences exist (risk floor, citation
   validation, mandatory probes, summary withholding). A test that runs an injection against
   each and prints a pass table belongs in the README.
3. **SARIF output.** So GitHub code scanning can ingest a run without a custom parser.
4. **Policy file** (`.triage.yml`): thresholds per repository, plus an allowlist for
   advisories the team has accepted. Without it, `--fail-on medium` is unusable in practice.

## Candidate: a council of models

The model is swappable already (`AR_MODEL`). Running several *at once* and taking a consensus
is the obvious next step, and cheap: the calls are independent, so three models in parallel
cost roughly the latency of the slowest (measured: 1.6–4.9 s each).

Design worth trying:

- run N models on the same evidence, in parallel
- consensus rule: **maximum risk wins**, and disagreement is reported rather than averaged
  (a model that says "low" while two say "high" is information, not noise to smooth away)
- every finding still has to survive citation validation, per model
- the report shows which model said what

Why it matters: it turns "we use an LLM" into "we do not trust one LLM". Measured evidence
that the models disagree already exists — in a four-model comparison on the same payload,
three said `low` and one said `medium`.

## Candidate: parallel branches for ecosystems

Adding Cargo, NuGet or Go is mostly mechanical and parallelises well: one branch per adapter,
each carrying an install step, an import pass and a fixture, then merged. The shared surface is
small but real — the entrypoint, the Dockerfile and the planner's probe menu — so the branches
will conflict there and need a serial merge. Worth doing with subagents only if the merge
surface is frozen first.

## Later, if anyone keeps it

- **More ecosystems.** Cargo (`build.rs`), NuGet (MSBuild targets), Go (`init()`). Each needs
  an install adapter, an import pass and a fixture — about a day each, and the evidence layer
  does not change.
- **History and regression detection.** The run store already keeps every run; comparing a
  package against its previous version ("this got riskier in 0.2.1") is a report away.
- **Second model as a cross-check.** Two models, disagreement shown rather than averaged.
  Cheap to build, and it turns "we use an LLM" into "we don't trust one LLM".
- **Disk quota for the work directory.** Currently measured, not enforced.

## Deliberately not

- **A runtime agent.** Watching what an installed package does at request time is a different
  product with a different threat model. Pretending otherwise would be the dishonest move.
- **A malware scanner.** No signatures, no YARA. The evidence model is the point; a signature
  list would invite people to trust a green checkmark.
- **Browser automation.** Track 1 allowed it. It was cut first, on purpose, and the README
  says so.
