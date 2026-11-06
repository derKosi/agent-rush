# Handoff — Stand 06.11.2026, 00:20

Zum Weiterarbeiten morgen. Alles hier ist belegt; was offen ist, steht unten.

## Wo was liegt

| | |
|---|---|
| Repo | `~/Documents/Dev/agent-rush` · `github.com/derKosi/agent-rush` (MIT) |
| Live | <http://45.77.143.94/> · Instanz `f0770065`… → `vc2-1c-2gb`, Frankfurt, ~$0.014/h |
| VM | `root@45.77.143.94`, Dienst `agent-rush`, Repo unter `/opt/agent-rush` |
| Video v1 | `recordings/demo-v1.mp4` — **1:53**, männliche Stimme (`en-US-AndrewNeural`) (gitignored) |
| Video v2 | `recordings/demo-v2.mp4` — **2:00**, weibliche Stimme (`en-US-AvaNeural`), Untertitel eingebrannt (gitignored) |
| Untertitel | `recordings/voice/subs.srt` (8 Cues, dieselben Zeiten wie die Tonspur) |
| Bauen | `bash tools/make-video.sh` — Stimme erzeugen, Bildschirm passend takten, muxen |
| Transkript | `docs/transcript.md` — EN + DE, 343 Wörter ≈ 2:32 |
| Doku | `README.md`, `docs/architecture.md`, `docs/ci.md`, `docs/market.md`, `docs/roadmap.md`, `docs/provenance.md`, `docs/build-log.md`, `docs/assets.md`, `docs/submission.md` |
| Blog | `blog/` (vier Fassungen + Bilder) — liegt **außerhalb** des Repos |

Letzter Commit: `6bac416`. 96 Tests, 13 Fixtures, 5 Läufe im Store.

## Was fertig und verifiziert ist

- Zwei Laufzeiten (Python-sdist, npm-Tarball), drei Phasen pro Lauf (build, import, resolve)
- Container: read-only, no-net, non-root, cap-drop, pids/mem/time-Limits — auf der VM gemessen
- Verdict: Regel-Untergrenze, Citation-Validierung, zurückgehaltene Summaries, Pflicht-Probes
- Abhängigkeiten: gehasht, gegen OSV geprüft, Score 0–10, Schwelle 7 blockt (`AR_DEP_RISK_THRESHOLD`)
- API: `/tasks`, `/batch`, `/runs`, `/runs/{id}/sarif`, Artefakte, Guard (12/h, 20/Tag pro IP, 1 gleichzeitig)
- CLI `triage` installierbar, Exit 0/1/2; SARIF 2.1.0; Compose + App-Image
- UI: Seitenleiste mit Läufen, Lauf als Dokument mit drei Tabs, Topbar mit Modell + Account, Hell-/Dunkelmodus

## Was noch fehlt (Pflicht)

1. **Stimme ersetzen, falls gewünscht.** v1 hat eine synthetische edge-tts-Stimme
   (`en-US-AndrewNeural`). Wer ElevenLabs will: dieselben acht Beats dort einsprechen, die mp3s
   in `recordings/voice/beat-N.mp3` legen und `bash tools/make-video.sh` erneut laufen lassen —
   die Bilder takten sich dann neu. Bekannte Ungenauigkeit: pro Navigation ~0,3 s Verzug,
   in Summe ~2,7 s. Das ist korrigiert: `make-video.sh` zieht 0,34 s pro Navigation von den
   Haltezeiten ab, danach sitzen Bild und Ton zusammen.
2. **Submission-Formular** auf LabLab. Text steht in `docs/submission.md`.
3. **Video-Upload** und Application-URL im Formular eintragen.

Deadline: **So 08.11. 23:00 UTC**. Ziel: 20:00 UTC abgeben, drei Stunden Puffer.

## Was optional noch ginge

- Council of models (mehrere Modelle parallel, max. Risiko gewinnt) — Design in `docs/roadmap.md`
- Abhängigkeits-Wheels wirklich durchprüfen statt nur listen
- Version-Diff zwischen zwei Releases eines Pakets
- Adversarial-Suite als veröffentlichte Tabelle

## Fallen, die Zeit gekostet haben

- **Safari-Cache.** Dreimal eine alte Seite fotografiert. Vor jedem Take `Cmd+Shift+R` oder
  `?v=<n>` an die URL. Assets sind deshalb versioniert (`app.css?v=…`).
- **`set URL of front document`** navigiert manchmal nicht. `open location` öffnet dafür einen
  neuen Tab — nach mehreren Aufrufen waren 24 Tabs im Bild.
- **`rm -rf work/runs/*` ohne `cd`** läuft im Home von root und löscht nichts. Immer absoluter Pfad.
- **Screencapture filmt den ganzen Bildschirm**, `-R` wird im Video-Modus ignoriert. Zuschneiden
  mit ffmpeg: `-vf "crop=2880:1470:0:190,scale=1440:-2"` — Höhe muss gerade sein, sonst
  scheitert libx264 mit „Invalid argument".
- **Theme vor dem ersten Paint setzen**, sonst blitzt die Seite und Screenshots werden halb.

## Zahlen für das Formular

96 Tests · 13 Fixtures · 5 Läufe · Median 13,4 s pro Lauf · 3 Phasen · 2 Laufzeiten ·
1 Block bei `harborline 2.9.1` (urllib3 1.24.1, 13 Advisories, Score 8,0, Schwelle 7).

## Bild-Fakten (für den Fall, dass Vorschaubilder verschwinden)

Alles Visuelle liegt als Datei im Repo; `docs/assets.md` beschreibt es im Detail.

- **Cover** `docs/slides/cover.png`, 1920×1080: Titel „Quarantine", Untertitel „Prove a package is
  safe / before it touches your machine", mintfarbener Würfel in einem Drahtgitter-Käfig,
  Zeile „Vultr: Agent Rush · Track 1 Blast Radius Zero", Fußzeile `github.com/derKosi/agent-rush`.
  Palette `#0D1117` / `#4CC2A0` / `#E6EDF3` / `#8B949E`.
- **Architektur** `docs/architecture.svg`, 1240×780: Browser → Caddy:80 → FastAPI:8080 →
  fünf Schritte (plan, build, import, resolve, verdict) → Sandbox-Flags → Deny-Proxy →
  Evidence → Verdict. Annotation: „resolve gets network — alone".
- **Hellmodus** geprüft: drei Bildschirmbereiche messen 240–250 (Weiß), also vollständig.
- **Screenshots in Gebrauch**: `demo-summary.png`, `demo-deps.png`, `demo-light.png`,
  `demo-clean.png`, `demo-dialog.png`. Ältere (`ui-*.png`, `demo-dashboard.png`,
  `demo-blocked.png`) sind überholt und werden nicht mehr referenziert.

## Push: erledigt

Der `fatal error in commit_refs_rules` war transient; am 06.11. um 19:46 UTC ging der Push
durch. Remote und lokal standen danach auf demselben Commit. Sicherung bleibt:
`~/agent-rush-2026-11-06.bundle`.

## Reihenfolge, die zählt

`tools/selftest.sh` mit Ziel-URL erzeugt **drei eigene Läufe** (`sample_pkg_deps`, `_stale`,
`_vuln`). Für ein sauberes Demo-Bild also: erst Selbsttest, dann Seed löschen und die fünf
Demo-Läufe neu fahren. Andernfalls stehen Fixture-Namen zwischen den Harborline-Läufen.

```bash
bash tools/selftest.sh http://45.77.143.94          # Gesundheitscheck
ssh root@45.77.143.94 'rm -rf /opt/agent-rush/work/runs/*; systemctl restart agent-rush'
# dann die fünf Pakete aus fixtures/ in dieser Reihenfolge:
#   left-pad-again 1.2.0, blazingly-fast-utils 0.9.3, harborline 2.8.0, 2.9.0, 2.9.1
```

## Erster Schritt morgen

```bash
cd ~/Documents/Dev/agent-rush && bash tools/selftest.sh http://45.77.143.94
```
Wenn das grün ist, ist die Instanz gesund und du kannst direkt aufnehmen.
