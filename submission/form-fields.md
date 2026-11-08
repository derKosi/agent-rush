# Copy-paste blocks for the form

Four lengths of the same claim. Take the one the field allows; do not edit the numbers, they come
from the run store.

---

## Title

```
Quarantine — prove a package is safe before it touches your machine
```

---

## 60 words — for a card or a list

```
Quarantine runs an untrusted package inside a hardened container on Vultr and reports what it
tried to do. Three phases — build hook, first import, dependency resolve — three evidence sources
the package cannot write to, and a verdict where rules set the floor and the model may only
summarise what the files contain.
```

---

## 300 characters — for a "summary" box

```
An agent inspects an untrusted package, decides which probes to run, and executes them in a
hardened container on Vultr. The verdict rests on three evidence sources: the egress proxy log,
the process result, a filesystem diff. The model may summarise; it cannot assert what the
evidence does not contain.
```

---

## Full text — `submission/description.md`

4,689 characters, ready to paste. It opens with what the thing is, walks the six steps, then three
runs that show the point:

- `harborline 2.9.1` — clean package, poisoned dependency (`urllib3` 1.24.1, 13 advisories, 8.0
  against a threshold of 7)
- `quickchart-export 0.4.0` — no dependencies, hostile install hook (egress, write, SSH key, spawn)
- `telemetry-shim 1.1.0` — clean build, clean import, hostile on first use

It closes with what the tool does **not** do. Leave that part in.

---

## Values for the remaining fields

| Field | Value |
|---|---|
| Demo URL | `http://45.77.143.94/` |
| Repository | `https://github.com/derKosi/agent-rush` |
| Video | YouTube link, or `submission/vidsubmission.mp4` |
| Slides | `submission/slides.pptx` |
| Cover | `submission/cover.png` |
| Licence | MIT |
