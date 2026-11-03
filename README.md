# Agent Rush — Package Triage Sandbox

Submission for **Vultr: Agent Rush Hackathon**, Track 1 *Blast Radius Zero* (Nov 3–8, 2026).

An agent inspects an **untrusted Python source package**, decides how to probe it, runs the
probe inside a hardened container on a Vultr VM, and returns a **risk report plus the raw
evidence** — a deny log from the egress proxy, the process result, and a file-system diff.

The point is not that the agent claims something was blocked. The point is that the artifact
shows the *attempt* and the *denial* side by side.

> An agent that only chats is a demo; an agent that executes safely is a product.

---

## Status

| Area | State |
|---|---|
| Repo scaffold, LICENSE, docs, cost log | done before kickoff |
| Sandbox image + runner + egress proxy | scaffolded before kickoff, **first verified run on the VM still pending** |
| Inference client (Vultr Serverless Inference) | scaffolded, key not yet provisioned |
| Orchestrator: sandbox dispatch + evidence collection | **built 03.11.**, 7/7 tests green against a stub runner |
| Orchestrator: planner + verdict | not started |
| Web app, API, deployment on Vultr | not started |

See [`docs/provenance.md`](docs/provenance.md) for the file-by-file record of what existed
before the event and what was built during it. That distinction is a rule of this hackathon,
so it is tracked explicitly rather than asserted.

## Architecture

```
                 ┌──────────────────────────────────────────┐
   browser ─────▶│  Web app (FastAPI + static UI)  :8080    │
                 │  task input · live trace · artifacts     │
                 └───────────────┬──────────────────────────┘
                                 │
                 ┌───────────────▼──────────────────────────┐
                 │  Orchestrator                            │
                 │  plan → dispatch → execute → observe →   │
                 │  verdict, with timeout and retry         │
                 └───────┬───────────────────────┬──────────┘
                         │                       │
        ┌────────────────▼─────────┐   ┌─────────▼─────────────────────┐
        │ Vultr Serverless         │   │ Sandbox runner (Docker)        │
        │ Inference                │   │ network:none · read-only root  │
        │ api.vultrinference.com   │   │ non-root · pids/mem/cpu caps   │
        └──────────────────────────┘   │ tmpfs /tmp · cap-drop ALL      │
                                       └─────────┬─────────────────────┘
                                                 │ attempts leave the box
                                       ┌─────────▼─────────────────────┐
                                       │ Egress proxy, deny by default │
                                       │ logs every attempt as JSONL   │
                                       └───────────────────────────────┘
```

Full detail, threat model and the containment invariants: [`docs/architecture.md`](docs/architecture.md).

## Vultr services used

- **Vultr Cloud Compute** — one Ubuntu VM runs the web app, the orchestrator and the Docker
  daemon that spawns sandboxes. Vultr is the control layer, not a static host.
- **Vultr Serverless Inference** — all model calls go to `https://api.vultrinference.com/v1`
  (OpenAI-compatible). No local GPU, no third-party inference.
- **Vultr Firewall** — only 80/443 inbound; the API and proxy are never publicly reachable.

## Quickstart (on the VM, after the kickoff)

```bash
cp .env.example .env          # then fill AR_VULTR_KEY
python3 models/smoke_test.py --list     # discover the real model ids
python3 models/smoke_test.py --prompt "ping"
bash fixtures/make_fixture.sh          # builds the probe package (gitignored artifact)
bash deploy/build_and_push.sh           # builds the sandbox image
bash sandbox/run.sh fixtures/sample_pkg-0.1.0.tar.gz
```

`sandbox/run.sh` is where the containment policy lives. Read it before trusting any claim
in this repo about isolation.

## Layout

```
sandbox/   Dockerfile, entrypoint, run.sh (the policy as executable flags)
proxy/     deny-by-default egress proxy, writes the evidence log
models/    Vultr Serverless Inference client + smoke test
web/       UI shell (wired up during the event)
deploy/    VM bootstrap (cloud-init), systemd unit, Caddyfile, image build
fixtures/  synthetic probe package used in the demo — no real malware, ever
docs/      architecture, provenance, demo storyboard, cost log
```

## License

MIT — see [LICENSE](LICENSE).
