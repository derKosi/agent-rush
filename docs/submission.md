# Submission copy (LabLab)

Copy-paste text for the submission form. Nothing here claims anything the repo does not show.

## Title

**Quarantine — prove a package is safe before it touches your machine**

## Short description (max ~300 chars)

An agent inspects an untrusted Python package, decides which probes to run, and executes them in
a hardened container on Vultr. You get a verdict backed by three independent evidence sources:
the deny-proxy log, the process result, and a filesystem diff. The model may summarise; it may
not assert what the evidence cannot support.

## Long description

### The problem

`pip install` runs code before anyone reads it. The build hook of a source package executes with
the installing user's rights: it can read SSH keys, call out to the internet, and leave files
behind. Security teams know this, and still install packages they have not read, because reading
them does not scale.

### What this does

You give it a package and a question. Then:

1. **Plan** — the model reads a static profile of the archive (file list, whether `setup.py`
   exists, whether it references network or subprocess modules) without executing anything, and
   picks which probes to run from a fixed menu, with a reason.
2. **Execute** — only the chosen probes run, inside a container with a read-only root filesystem,
   no network, a non-root user, and caps on memory, processes and time.
3. **Observe** — three sources are collected, none of which the sandboxed process controls:
   the egress proxy log (what was attempted, and the decision), the process result, and a
   filesystem diff.
4. **Verdict** — rules first, model second. Every model claim must cite a source that exists in
   *this* run; a claim citing anything else is rejected and cannot raise the risk level.

### Why the evidence model matters

Every containment tool can print "safe". This one cannot get away with it: the report is built
from the proxy log and the filesystem, and the model is only allowed to talk about what those
contain. In our own run the model tried to raise the risk with a citation that did not exist in
the run; it was rejected and the verdict stayed where the evidence put it.

We also publish the limits. A detached child process is **not** prevented by this setup — the
report says `spawned`, because saying otherwise would be a lie. What is prevented is the process
escaping the container, and that is the property the design is built on.

### Built on Vultr

- **Cloud Compute** (`vc2-1c-2gb`, Frankfurt) runs the web app, the orchestrator and the Docker
  daemon that spawns one container per task. Vultr is the control layer, not static hosting.
- **Serverless Inference** (`api.vultrinference.com/v1`, `glm-5.2`) does the planning and the
  verdict. Reasoning is disabled per call: measured at 2.2 s instead of 7.0 s with the same
  structure.
- No credential ever enters the sandbox. The inference key lives in the service environment.

### Status at submission

Working and publicly reachable: live URL, public repository with MIT license, 35 tests green,
one verified containment moment recorded in the README with the exact observations.

## Technology & category tags

`Python` · `FastAPI` · `Docker` · `Vultr Cloud Compute` · `Vultr Serverless Inference` ·
`sandboxing` · `supply chain security` · `LLM agents` · `developer tools` · `security`

## Links

| | |
|---|---|
| Demo | http://45.77.143.94/ |
| Repository | https://github.com/derKosi/agent-rush |
| Slides | `docs/slides/agent-rush.pdf` |
| Cover | `docs/slides/cover.png` |

## Submission checklist (from the event page)

- [x] Project title
- [x] Short description
- [x] Long description
- [x] Technology & category tags
- [ ] Cover image — *to add*
- [ ] Video presentation — *recorded by Kosi, script in `docs/demo-storyboard.md`*
- [ ] Slide presentation — *in progress*
- [x] Public GitHub repository (MIT)
- [x] Demo application platform + application URL
- [x] README explains the Vultr architecture and the agent's use case
- [ ] Containment moment in the video
