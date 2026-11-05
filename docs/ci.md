# Using this from a pipeline

This repo has **no CI workflows** and will not get any — that is a deliberate decision
(see the README). What follows is documentation for *your* pipeline, not a file in this repo.

The pattern: build your package the way you normally would, then call `tools/triage.py`
before it reaches a machine that holds credentials.

```bash
python3 tools/triage.py dist/*.tar.gz --base https://your-triage-host --fail-on high
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | nothing at or above the threshold |
| 1 | threshold hit — fail the job |
| 2 | request failed, or the batch did not finish |

## Example step (GitHub Actions)

```yaml
# .github/workflows/release.yml — YOUR repo, not this one
- name: Build sdist
  run: python -m build --sdist

- name: Triage the sdist before it is published
  run: |
    pip install --quiet requests-optional 2>/dev/null || true
    python tools/triage.py dist/*.tar.gz \
      --base ${{ secrets.TRIAGE_URL }} \
      --fail-on high
```

Two notes that matter more than the YAML:

- **The triage host needs the package.** Either upload it, or put the triage service on the
  same runner as an ephemeral VM. A hosted instance with `--fail-on` is the cheap version;
  a per-job instance is the version that scales.
- **`--fail-on medium` is noisy at first.** Start with `high`, look at what comes back for a
  week, then tighten. A gate nobody trusts gets deleted.

## Machine-readable output

`--json` prints the batch report:

```json
{
  "batch": "b20261105T181500-ab12cd",
  "state": "done",
  "worst": "high",
  "fail_on": "high",
  "failed": true,
  "packages": [
    {"package": "sample_pkg-0.1.0.tar.gz", "run": "20261105T181501-1f2e3d",
     "state": "done", "risk": "high", "findings": 12, "rejected": 0}
  ]
}
```
