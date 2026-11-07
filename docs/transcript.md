# Voice-over transcript — v2 script

Nine beats: hero page → live run → dependencies → settings → the release before → evidence →
GitHub → close. Every number comes from a real run on the live instance.

## Before you record

- `Cmd+Shift+R` on every tab. A cached page has cost ten minutes three times.
- One Safari tab. Close the rest — the tab strip has been in two screenshots already.
- Window 1440×900 at {0, 25}. The page starts at y=136 px in the 2880-wide capture.

## Shot list and lines

**0:00 — `http://45.77.143.94/hero.html`**
> Quarantine. Proof, not claims.
> Every `pip install` runs someone else's code before anyone has read it. This one runs it inside
> a container that cannot reach the network, cannot write outside its folder, and does not have
> root — and then shows you what it tried.

**0:16 — click "Open the live runs"**
> Five runs, three packages, one of them blocked.

**0:26 — open `harborline 2.9.1`**
> `harborline` 2.9.1. The model read it, chose which probes to run, and executed them on a Vultr
> VM. Verdict: high. And the sentence that matters is the first one — the package builds and
> imports cleanly.

**0:50 — Dependencies tab**
> Because the problem is not in the package. It pins `urllib3` 1.24.1, a release from 2018:
> thirteen known advisories, the worst scored eight out of ten. The block threshold is seven, so
> this stops here. The wheels are fetched and hashed, never installed — that hash is what you
> would actually get.

**1:15 — Settings**
> The threshold is a setting, not a constant. So is the model, the reasoning budget, and how many
> runs one address may start per hour. And the honest part: accounts are demo-only here, and the
> delete button is deliberately inert, because a delete button without authentication would be a
> mistake.

**1:32 — `harborline 2.9.0`, then `2.8.0`**
> Two runs earlier, the same package was fine. 2.9.0 and 2.8.0 both came back low — 2.9.0 with a
> note that one dependency was a minor behind. The regression arrived with 2.9.1.

**1:50 — Evidence tab**
> Every claim in this report points at a file: the proxy log, the process result, the filesystem
> diff. The model may summarise them. It may not assert anything they do not contain — a claim
> citing a source that is not in this run is dropped, and you can see it here.

**2:10 — `https://github.com/derKosi/agent-rush`**
> The architecture fits in three sentences: a VM runs the control plane, every task gets its own
> hardened container, and the verdict is built from evidence the container cannot write to.
> Source is public, MIT, ninety-six tests.

**2:26 — back to the hero page**
> Quarantine. Live at this URL.

## Timing check

| Beat | Starts | Words |
|---|---|---|
| Hero | 0:00 | 52 |
| Five runs | 0:16 | 9 |
| Verdict | 0:26 | 40 |
| Dependencies | 0:50 | 55 |
| Settings | 1:15 | 50 |
| Regression | 1:32 | 42 |
| Evidence | 1:50 | 51 |
| GitHub | 2:10 | 40 |
| Close | 2:26 | 7 |

Measured with `fr-FR-VivienneMultilingualNeural`: **2:00.05**, nine beats. The visuals follow the
audio; `tools/make-video-v2.sh` records this script and takes the caption mode as an argument.

## Deutsche Fassung

**0:00**
> Quarantine. Beweis statt Behauptung. Jedes `pip install` führt fremden Code aus, bevor ihn
> jemand gelesen hat. Dieser hier läuft in einem Container, der kein Netzwerk erreicht, nicht
> außerhalb seines Ordners schreiben kann und kein Root hat — und zeigt dir danach, was er
> versucht hat.

**0:16**
> Fünf Läufe, drei Pakete, eines blockiert.

**0:26**
> `harborline` 2.9.1. Das Modell hat es gelesen, die Prüfungen gewählt und auf einer Vultr-VM
> ausgeführt. Urteil: hoch. Und der Satz, auf den es ankommt, ist der erste — das Paket baut und
> importiert sauber.

**0:50**
> Denn das Problem steckt nicht im Paket. Es pinnt `urllib3` 1.24.1, eine Version von 2018:
> dreizehn Advisories, die schlechteste mit acht von zehn. Die Schwelle liegt bei sieben, also
> stoppt es hier. Die Wheels werden geholt und gehasht, nie installiert.

**1:15**
> Die Schwelle ist eine Einstellung, keine Konstante. Ebenso das Modell, das Denk-Budget und wie
> viele Läufe eine Adresse pro Stunde starten darf. Und der ehrliche Teil: Konten sind hier Demo,
> und der Löschknopf ist absichtlich inaktiv — ohne Authentifizierung wäre er ein Fehler.

**1:32**
> Zwei Läufe vorher war dasselbe Paket unauffällig. 2.9.0 und 2.8.0 kamen beide mit niedrigem
> Risiko zurück. Die Regression kam mit 2.9.1.

**1:50**
> Jede Aussage zeigt auf eine Datei: Proxy-Log, Prozessergebnis, Datei-Diff. Das Modell darf
> zusammenfassen, nicht behaupten. Eine Quelle, die es in diesem Lauf nicht gibt, wird verworfen.

**2:10**
> Die Architektur in drei Sätzen: eine VM fährt die Kontrollschicht, jeder Task bekommt seinen
> eigenen Container, und das Urteil entsteht aus Beweisen, die der Container nicht schreiben kann.
> Quellcode öffentlich, MIT, sechsundneunzig Tests.

**2:26**
> Quarantine. Live unter dieser Adresse.
