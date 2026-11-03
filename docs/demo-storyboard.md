# Demo-Drehbuch (Ziel: 2:30, max. 3:00)

Ein Take, der scheitert, ist normal. Budget: 3 Takes, nicht 30.

## 0:00–0:20 — Problem, ein Satz

Sprecher, Bildschirm: ein Terminal, `pip install some-package`, dann ein Editor mit `setup.py`,
das `urllib` und `subprocess` importiert.

> „Jedes `pip install` führt fremden Code aus, bevor irgendjemand ihn gelesen hat.
> Das hier läuft auf einem Rechner, auf dem auch eure Schlüssel liegen."

## 0:20–0:50 — Die Kontrollschicht zeigen

Web-UI auf der Vultr-URL. Task eintippen: „Triage this package before we install it."
Trace läuft los: der Agent liest `setup.py`, listet die Dateien, schreibt seinen Plan.
Sichtbar: der Plan nennt die vier Probes. Kein Chat, ein Protokoll.

## 0:50–1:50 — Containment-Moment (der Kern des Videos)

Der eigentliche Beweis, in dieser Reihenfolge, ohne Schnitt:

1. Container startet — `docker ps` zeigt ihn, `--network none`/Proxy im Befehl sichtbar.
2. Build-Hook läuft. Im UI erscheinen nacheinander drei Denials:
   - `write /opt/ar-probe → EROFS (read-only root)`
   - `POST http://collector.invalid/v1/collect → 403 (proxy, deny by default)`
   - `open /home/sandbox/.ssh/id_rsa → ENOENT (decoy path, nothing there)`
3. Container endet. `docker ps` ist leer.
4. Host-Gegenprobe im selben Take: `shasum` einer Host-Datei vor und nach dem Lauf — identisch.
   Und `ls /opt/ar-probe` — existiert nicht.

Nichts davon wird behauptet. Alles wird gezeigt.

## 1:50–2:20 — Artefakt

Risk-Report öffnen: Verdict, die drei blockierten Aktionen mit Quelle (Proxy-Log, Exec-Result,
FS-Diff), Download-Button. Ein Satz dazu, dass die drei Beweisquellen unabhängig sind und der
Agent nur zusammenfassen darf, was sie hergeben.

## 2:20–2:30 — Vultr-Architektur und Käufer

Ein Bild: VM, Serverless Inference, Sandbox, Proxy. Dann der Satz, für wen das gebaut ist —
AppSec und Plattform-Teams, die vor dem Merge entscheiden müssen.

## Checkliste vor der Aufnahme

- [ ] Demo-Instanz frisch gestartet, keine Testreste im UI
- [ ] `.env` nicht im Bild, keine Keys in der Konsole sichtbar
- [ ] Fontgröße im Terminal groß genug für 1080p
- [ ] Proxy-Log und UI-Trace zeigen dieselbe Uhrzeit (sonst wirkt es gestellt)
- [ ] Host-Hash-Gegenprobe vorher einmal geprobt
- [ ] Bildschirmaufnahme: 1920×1080, 30 fps, Cursor sichtbar
- [ ] Audio: ein Take mit Ton, kein Voiceover über stummem Bild

## Was im Video nicht vorkommt

- Folien am Anfang. Die Jury sieht 30 Videos mit „Hi, ich bin…".
- Ein zweiter Use Case. Eine Idee, zu Ende gezeigt.
- Behauptungen ohne Artefakt. Wenn etwas nicht klappt: rausschneiden, nicht erklären.
