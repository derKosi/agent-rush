# Voice-over transcript

Target 2:30. Spoken English, ~135 words per minute. The German version follows at the end.
Every number in here was produced by a real run on the live instance — nothing is read off a slide.

## Before you record

- Hard reload the page (`Cmd+Shift+R`). Safari has served a cached page three times during this
  build and every time it cost ten minutes.
- Open `http://45.77.143.94/?run=<id-of-2.9.1>` so the run is already selected; the summary tab
  should be active.
- Window 1440×900, browser zoom 100 %, light or dark — pick one and stay in it.
- Close every other tab. The tab strip has been in two screenshots already.

## Shot list and lines

**0:00 — Dashboard, nothing selected**
> This is a package registry for one team. Five runs, three packages, one of them blocked.

**0:06 — Click `harborline 2.9.1`**
> `pip install` runs code before anyone has read it. The build hook of a source package executes
> with the installing user's rights: it can read SSH keys, call out, leave files behind.
> Everyone knows this, and everyone installs packages nobody read — because reading does not scale.

**0:24 — Summary tab is open; let the finding list land**
> This is `harborline` 2.9.1. The model read it, chose which probes to run, and executed them in a
> container on Vultr with no network, a read-only filesystem and no root.
> Verdict: high. And the sentence that matters is the first one — the package builds and imports
> cleanly.

**0:48 — Click Dependencies**
> Because the problem is not in the package. It pins `urllib3` 1.24.1 — a release from 2018.
> Thirteen known advisories, the worst scored eight out of ten. The threshold is seven, so this
> blocks.
> The wheels are fetched and hashed, never installed. That hash is what you would actually get.

**1:15 — Point at the gauge, then back to the rail**
> Two runs earlier, the same package was fine. 2.8.0 and 2.9.0 both came back low — 2.9.0 with a
> note that one dependency was a minor behind. The regression arrived with 2.9.1.

**1:38 — Click Evidence**
> Every claim in this report points at a file: the proxy log, the process result, the filesystem
> diff. The model is allowed to summarise them. It is not allowed to assert anything they do not
> contain — a claim citing a source that is not in this run gets dropped, and you can see it here.

**2:05 — Back to the summary, scroll the finding list slowly**
> That is the difference between a scanner and a verdict: this one can show you why, on the same
> screen, without you trusting a green checkmark.

**2:18 — End card or just the dashboard**
> Agent Rush. Source and MIT licence in the repository, demo at this URL.

## Timing check

| Beat | Starts | Words |
|---|---|---|
| Hook | 0:06 | 52 |
| Run verdict | 0:24 | 74 |
| Dependencies | 0:48 | 66 |
| Regression | 1:15 | 44 |
| Evidence | 1:38 | 62 |
| Close | 2:05 | 45 |

Total spoken words ≈ 343 → 2:32 at 135 wpm. Cut the hook's third sentence if you need 2:15.


## Measured with edge-tts

Two takes exist:

| File | Voice | Length |
|---|---|---|
| `recordings/demo-v1.mp4` | `en-US-AndrewNeural` (male) | 1:53 |
| `recordings/demo-v2.mp4` | `en-US-AvaNeural` (female, expressive) | 2:00 |
| `recordings/demo-v3.mp4` | `fr-FR-VivienneMultilingualNeural` (female, French native) | 1:49 |

The French multilingual voice reads English with a light accent — clear, but audibly not a native
speaker. Ava reads slower than Andrew, so the holds regenerate and the screen pass re-times itself — the visuals
follow the voice, never the other way round. The table below is the v1 measurement.

The table above was an estimate at 135 wpm. The actual voice runs faster, so the video is
**1:53.2** and the beats are:

| Beat | Hold |
|---|---|
| dashboard | 6.7s |
| hook | 18.4s |
| verdict | 18.7s |
| dependencies | 20.6s |
| regression | 15.5s (9.0 + 6.5, two runs) |
| evidence | 17.8s |
| close | 8.9s |
| end card | 6.3s |

`tools/build-voiceover.py` regenerates the audio and writes `recordings/voice/holds.txt`;
`tools/make-video.sh` reads it and times the screen pass to it. Swapping the voice (ElevenLabs,
another edge-tts voice) means running those two scripts again — the visuals follow automatically.

## Deutsche Fassung

**0:06**
> `pip install` führt Code aus, bevor ihn jemand gelesen hat. Der Build-Hook läuft mit den Rechten
> des Installierenden: Schlüssel lesen, nach außen telefonieren, Dateien hinterlassen. Alle wissen
> das, und alle installieren trotzdem Pakete, die niemand gelesen hat — weil Lesen nicht skaliert.

**0:24**
> Das ist `harborline` 2.9.1. Das Modell hat es gelesen, die Prüfungen ausgewählt und in einem
> Container auf Vultr ausgeführt: kein Netzwerk, read-only Dateisystem, kein Root.
> Urteil: hoch. Und der Satz, auf den es ankommt, ist der erste — das Paket baut und importiert
> sauber.

**0:48**
> Denn das Problem steckt nicht im Paket. Es pinnt `urllib3` 1.24.1 — eine Version von 2018.
> Dreizehn bekannte Advisories, die schlechteste mit acht von zehn bewertet. Die Schwelle liegt
> bei sieben, also wird blockiert.
> Die Wheels werden geholt und gehasht, nie installiert. Dieser Hash ist das, was du wirklich
> bekommst.

**1:15**
> Zwei Läufe vorher war dasselbe Paket unauffällig. 2.8.0 und 2.9.0 kamen beide mit niedrigem
> Risiko zurück — 2.9.0 mit dem Hinweis, dass eine Abhängigkeit ein Minor hinterherhängt. Die
> Regression kam mit 2.9.1.

**1:38**
> Jede Aussage in diesem Bericht zeigt auf eine Datei: Proxy-Log, Prozessergebnis, Datei-Diff. Das
> Modell darf zusammenfassen. Es darf nicht behaupten, was dort nicht steht — eine Aussage mit
> einer Quelle, die es in diesem Lauf nicht gibt, wird verworfen. Hier ist sie.

**2:05**
> Das ist der Unterschied zwischen einem Scanner und einem Urteil: dieses Werkzeug kann zeigen,
> warum — auf demselben Bildschirm, ohne dass du einem grünen Haken glauben musst.
