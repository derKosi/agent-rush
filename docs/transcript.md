# Voice-over transcript — v3 script

Ten beats in three acts. **Act one** is a clean package with a dirty dependency. **Act two** is
two packages that misbehave themselves — one at install, one only at import — because dependency
checking is the smaller half of what this does. **Act three** is the evidence and the settings.

Every number comes from a run on the live instance on 7 November 2026.

## Before you record

- `Cmd+Shift+R` on the tab. A cached page has cost ten minutes three times.
- One Safari tab. The tab strip has been in two screenshots already.
- Window 1440×900 at {0, 25}; the page starts at y=136 px of the 2880-wide capture.

## The three acts, in one line each

| Act | Run | What it proves |
|---|---|---|
| one | `harborline 2.9.1` | the package is clean; its dependency is not — score 8.0 against threshold 7 |
| two | `quickchart-export 0.4.0` | the install hook itself is hostile: egress, write, SSH key, spawn |
| two | `telemetry-shim 1.1.0` | clean build, clean import, hostile on first use — only the import phase sees it |

## Shot list and lines

**0:00 — `http://45.77.143.94/hero.html`**
> Quarantine. Proof, not claims.
> Every `pip install` runs someone else's code before anyone has read it. This one runs it inside
> a container that cannot reach the network, cannot write outside its folder, and has no root —
> and then shows you what it tried.

**0:16 — "Open the live runs" → the dashboard**
> Seven runs, five packages, three of them blocked.

**0:26 — `harborline 2.9.1`**
> `harborline` 2.9.1. It builds and imports cleanly, and still comes back high. Keep that in mind:
> it is the whole point of the next two runs.

**0:46 — Dependencies**
> Because its problem is not its own code, it is what it pins. `urllib3` 1.24.1, a release from
> 2018, thirteen known advisories, the worst scored eight out of ten. The threshold is seven.
> The wheels are fetched and hashed, never installed.

**1:06 — `quickchart-export 0.4.0`**
> Dependencies are half of it. This package has none. Its install hook tried to reach a host,
> write outside its own directory, and read an SSH key. The sandbox denied all three — and every
> denial points at a file you can open.

**1:28 — `telemetry-shim 1.1.0`**
> And this one builds clean, imports clean, and only on import spawns a process and calls home.
> A dependency scanner would have passed it. That is why there are three phases, and why the
> import phase is not optional.

**1:50 — Evidence**
> Every claim in the report cites something that exists in this run: the proxy log, the process
> result, the filesystem diff. The model may summarise them, never exceed them — a claim pointing
> at a source that is not here gets dropped.

**2:10 — Settings**
> The threshold is a setting, not a constant. So is the model, the reasoning budget, and how many
> runs one address may start per hour. And the honest part: accounts are demo-only, and the
> delete button is deliberately inert.

**2:26 — `https://github.com/derKosi/agent-rush`**
> The architecture in three sentences: a VM runs the control plane, every task gets its own
> hardened container, and the verdict is built from evidence the container cannot write to.
> MIT, ninety-six tests.

**2:42 — back to the hero page**
> Quarantine. Live at this URL.

## Timing check

Measured with `fr-FR-VivienneMultilingualNeural` after the take was rendered; `holds.txt` carries
the per-beat lengths and the record script reads them, so a change in wording moves the visuals.

## Deutsche Fassung

**0:00**
> Quarantine. Beweis statt Behauptung. Jedes `pip install` führt fremden Code aus, bevor ihn
> jemand gelesen hat. Dieser hier läuft in einem Container ohne Netzwerk, ohne Schreibrechte
> außerhalb seines Ordners und ohne Root — und zeigt dir danach, was er versucht hat.

**0:16**
> Sieben Läufe, fünf Pakete, drei blockiert.

**0:26**
> `harborline` 2.9.1. Es baut und importiert sauber — und kommt trotzdem mit hohem Risiko zurück.
> Das ist der Punkt der nächsten beiden Läufe.

**0:46**
> Denn das Problem ist nicht sein eigener Code, sondern das, was es festnagelt: `urllib3` 1.24.1,
> eine Version von 2018, dreizehn Advisories, die schlechteste mit acht von zehn. Die Schwelle
> liegt bei sieben. Die Wheels werden geholt und gehasht, nie installiert.

**1:06**
> Abhängigkeiten sind die Hälfte. Dieses Paket hat keine. Sein Install-Hook wollte einen Host
> erreichen, außerhalb seines Ordners schreiben und einen SSH-Schlüssel lesen. Der Sandbox hat
> alles drei verweigert — und jede Verweigerung zeigt auf eine Datei.

**1:28**
> Und dieses hier baut sauber, importiert sauber und startet erst beim Import einen Prozess und
> ruft nach Hause. Ein Dependency-Scanner hätte es durchgelassen. Deshalb gibt es drei Phasen.

**1:50**
> Jede Aussage im Bericht zitiert etwas, das es in diesem Lauf gibt: Proxy-Log, Prozessergebnis,
> Datei-Diff. Das Modell darf zusammenfassen, nicht behaupten.

**2:10**
> Die Schwelle ist eine Einstellung, keine Konstante. Ebenso das Modell, das Denk-Budget und das
> Limit pro Adresse. Und der ehrliche Teil: Konten sind Demo, der Löschknopf ist inaktiv.

**2:26**
> Die Architektur in drei Sätzen: eine VM fährt die Kontrollschicht, jeder Task bekommt seinen
> eigenen Container, das Urteil entsteht aus Beweisen, die der Container nicht schreiben kann.

**2:42**
> Quarantine. Live unter dieser Adresse.
