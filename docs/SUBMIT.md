# Submit — Sunday 8 November 2026

**Deadline 23:00 UTC.** That is 00:00 Monday in Berlin. Aim to be done by 20:00 UTC / 21:00 local,
so there is time to fix a rejected upload instead of watching the clock.

## State, verified this morning (09:55 UTC)

| Check | Result |
|---|---|
| `GET /health` | `ok`, model `glm-5.2`, threshold 7.0, 0 active runs |
| Runs on the instance | **7 runs, 5 packages, 3 blocked** — the demo line, nothing else |
| `bash tools/selftest.sh <url>` | `selftest: ok` — 52 unit checks plus three real runs (low / low / high as expected) |
| Repository | public, MIT, branch `main`, `d808846` |
| Tests | 96 test functions in `tests/` |
| Video | `submission/vidsubmission.mp4`, 1:58, 1440×762, AAC — the three-act cut |
| Captions | none ship with this cut; YouTube generates its own |

Everything below assumes nothing changes on the instance. **Do not redeploy, do not re-run the
self-test after this point** — it writes three fixture runs into the rail the jury looks at.

## 1. Video to YouTube (about 10 minutes)

Upload `submission/vidsubmission.mp4` (3.4 MB, 1:58).

- **Title:** `Quarantine — prove a package is safe before it touches your machine`
- **Visibility:** Unlisted (the form needs a link, not an audience)
- **Thumbnail:** `submission/cover.png`
- **Captions:** leave YouTube's automatic ones. The burned-in text is deliberately absent —
  a caption file for this cut would have to be re-timed, and a mis-timed caption is worse than none.

Description for the video:

```
An agent triages an untrusted package before it reaches a machine: it plans which probes to run,
executes them in a hardened container on Vultr, and returns a verdict built from evidence the
package cannot write to — the egress proxy log, the process result, a filesystem diff.

Three acts: a clean package with a poisoned dependency, an install hook that is hostile on its
own, and a package that is only hostile on first import.

Live: http://45.77.143.94/ · Source (MIT): https://github.com/derKosi/agent-rush

Built for Vultr Agent Rush, Track 1 "Blast Radius Zero".
```

Copy the link YouTube gives you (`https://youtu.be/…`).

## 2. The form

| Field | Value |
|---|---|
| Project title | `Quarantine — prove a package is safe before it touches your machine` |
| Short description | see the two sentences at the top of `submission/description.md` |
| Long description | the whole of `submission/description.md` (4,689 characters) |
| Demo URL | `http://45.77.143.94/` |
| Repository | `https://github.com/derKosi/agent-rush` |
| Video | the YouTube link from step 1, or the mp4 itself |
| Slides | `submission/slides.pptx` |
| Cover | `submission/cover.png` |
| Licence | MIT |
| Track | Vultr — Track 1, Blast Radius Zero |

If a field has a character limit below 4,689, cut in this order: the "Two runtimes" section, then
the "What the runs actually caught" table rows for `telemetry-shim`, then the closing paragraph.
Never cut the "Where it stops" section — that is the part that makes the rest credible.

## 3. Before you press submit

- Open `http://45.77.143.94/` in a fresh window and click one run. If the rail shows three
  fixtures named `selftest-*`, the self-test ran after the seed — tell me, I reseed in five minutes.
- Check the video link opens in a private window (an unlisted link that only works for you is
  the classic way to submit a dead link).
- Screenshot the confirmation page. It is the only proof of the timestamp.

## 4. After submitting

Leave the instance running. Jurors look at it after the deadline, and every link in the report
points at a file that only exists while the VM is up.

Do **not**, between now and the deadline:

- restart the service (it is fine, but the run timestamps move)
- re-run the self-test (writes three runs)
- push to `main` unless something is broken — the repo link is in the form

## If something breaks

| Symptom | Fix |
|---|---|
| Form rejects the YouTube link | upload `submission/vidsubmission.mp4` directly, it is 3.4 MB |
| Demo URL does not load | `ssh root@45.77.143.94 'systemctl restart agent-rush'` |
| Rail shows fixture names | I reseed: it is a 5-minute job, the fixtures are all in `fixtures/` |
| A number in the description looks wrong | check it against `/runs` first, then edit the text, not the claim |

## What we say we do not do

Keep these in the submission as they are — they are in `description.md` and the README:

- dependencies are listed and checked, never executed
- what runs after the first import is out of scope
- a detached child process is not prevented; the report says `spawned`
- accounts are demo-only, so the delete button is inert

A judge who finds one of these unannounced discounts everything else. A judge who reads them
listed stops looking for the catch.
