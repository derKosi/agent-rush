# Using this from a pipeline

This repo has **no CI workflows** and will not get any — a deliberate decision, see the
README. What follows is documentation for *your* pipeline.

The pattern: build your artifact the way you normally would, then send it through triage
before it reaches a machine that holds credentials.

## Install the client

The CLI is a small stdlib-only script; installing it gives you a `triage` command.

```bash
pipx install git+https://github.com/derKosi/agent-rush   # or:
pip install --user git+https://github.com/derKosi/agent-rush
triage --help
```

It talks to a running instance. Nothing is bundled: no Docker, no Python packages, no
network access beyond the URL you pass.

## One command

```bash
triage dist/*.tar.gz --base https://your-triage-host --fail-on high
```

| Exit code | Meaning |
|---|---|
| 0 | nothing at or above the threshold |
| 1 | threshold hit — fail the job |
| 2 | request failed, or the batch did not finish |

## Auth

If the instance sets `AR_API_TOKEN`, requests need a bearer token:

```bash
triage pkg.tar.gz --base https://triage.example.com --token "$TRIAGE_TOKEN"
# or keep it out of the process list:
export AGENT_RUSH_TOKEN=...   # picked up automatically
```

Without `AR_API_TOKEN` the instance is open but bounded: 12 runs/hour per IP, one at a
time, 150 per day. That is the demo default, not a production default.

## GitHub Actions

```yaml
# .github/workflows/release.yml — YOUR repo, not this one
- name: Build sdist
  run: python -m build --sdist

- name: Triage before publish
  env:
    TRIAGE_TOKEN: ${{ secrets.TRIAGE_TOKEN }}
  run: |
    pip install --quiet git+https://github.com/derKosi/agent-rush
    triage dist/*.tar.gz --base ${{ vars.TRIAGE_URL }} --fail-on high
```

## GitLab CI

```yaml
triage:
  stage: test
  image: python:3.12-slim
  variables:
    TRIAGE_URL: "https://triage.example.com"
  script:
    - pip install --quiet git+https://github.com/derKosi/agent-rush
    - python -m build --sdist
    - triage dist/*.tar.gz --base "$TRIAGE_URL" --token "$TRIAGE_TOKEN" --fail-on high
  rules:
    - if: $CI_COMMIT_TAG
```

## Pre-commit, before anyone installs anything

```yaml
# .pre-commit-config.yaml — runs on the artifact, not the source tree
- repo: local
  hooks:
    - id: triage
      name: triage new sdists
      entry: triage
      language: system
      files: '\.tar\.gz$'
      pass_filenames: true
      args: ["--base", "https://triage.example.com", "--fail-on", "high"]
```

## Running your own instance

Fastest path, any host with Docker:

```bash
docker build -t ar-sandbox:0.1 sandbox/
docker compose up --build        # app on :8080
```

The demo runs on a Vultr VM (`vc2-1c-2gb`, ~$0.014/h). To stand up your own the long way:

```bash
# on a fresh Ubuntu 24.04 box with root access
ssh root@<ip> 'bash -s' < deploy/vm-bootstrap.sh
rsync -az --exclude .git --exclude .venv ./ root@<ip>:/opt/agent-rush/
ssh root@<ip> 'bash /opt/agent-rush/deploy/install-service.sh'
```

Then put `AR_VULTR_KEY` and `AR_MODEL` into `/opt/agent-rush/.env` (the model is optional:
without it the verdict is rule-based only). `deploy/runbook.md` has the details.

## Scope, so you know what you are buying

This is not a general supply-chain firewall. It tests **one artifact, in two phases**:

| | |
|---|---|
| Artifact | Python **sdist** (`.tar.gz` with `setup.py`) or **npm tarball** |
| Phase 1 | `pip install` runs the build hook, with the chosen probes |
| Phase 2 | the installed distribution is imported, top-level modules only |
| Observed | egress attempts, filesystem changes, process result, spawns |
| **Not** observed | dependency *behaviour* (the tree is fetched and hashed, never executed), what runs later at request time, code paths never executed |

Other ecosystems — npm `postinstall`, Cargo `build.rs`, NuGet MSBuild targets, Go `init()` —
have the same shape and would need their own install adapter. That is roadmap, not shipped.

`--fail-on medium` is noisy at first. Start with `high`, look at a week of results, then
tighten. A gate nobody trusts gets deleted.
