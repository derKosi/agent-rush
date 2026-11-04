# Provenance — was wann entstanden ist

Die LabLab-Regel: Kernfunktionalität muss im Event-Fenster (03.11. 15:00 UTC – 08.11. 23:00 UTC)
entstehen. Vorarbeit ist nur für Konten, Credits, Repo-Skelett, Deployment-Pipeline,
Sandbox-Auswahl, Architektur und Demo-Drehbuch erlaubt.

Diese Tabelle ist die Abrechnung dazu. Sie wird beim Commit mitgeführt, nicht am Ende rekonstruiert.

| Pfad | Entstanden | Erlaubte Kategorie |
|---|---|---|
| `LICENSE`, `.gitignore`, `.env.example` | vor dem Event | Repo-Skelett |
| `README.md` | vor dem Event | Repo-Skelett |
| `docs/architecture.md` | vor dem Event | Architektur |
| `docs/demo-storyboard.md` | vor dem Event | Demo-Drehbuch |
| `docs/rehearsal.md` | vor dem Event | Demo-Drehbuch (ausführbare Fassung) |
| `docs/cost-log.md` | vor dem Event | Dokumentation |
| `docs/runbook.md` | vor dem Event | Deployment-Pipeline |
| `docs/discord-question.md` | vor dem Event | Dokumentation (Rückfrage zur Regel) |
| `sandbox/Dockerfile` | vor dem Event | Sandbox-Auswahl |
| `sandbox/entrypoint.sh` | vor dem Event | Sandbox-Auswahl |
| `sandbox/run.sh` | vor dem Event | Sandbox-Auswahl |
| `proxy/deny_proxy.py` | vor dem Event | Sandbox-Auswahl (Isolation) |
| `models/client.py`, `models/smoke_test.py` | vor dem Event | Deployment-Pipeline (Endpoint-Zugang) |
| `deploy/build_and_push.sh` | vor dem Event | Deployment-Pipeline |
| `deploy/cloud-init.yaml` | vor dem Event | Deployment-Pipeline (VM-Bootstrap) |
| `deploy/agent-rush.service` | vor dem Event | Deployment-Pipeline (Prozessaufsicht) |
| `deploy/Caddyfile` | vor dem Event | Deployment-Pipeline (Reverse Proxy) |
| `deploy/install-service.sh` | vor dem Event | Deployment-Pipeline |
| `deploy/check-vm.sh` | **im Event** (03.11.) | Deployment-Pipeline |
| `deploy/remote-setup.sh` | **im Event** (04.11.) | Deployment-Pipeline |
| `web/index.html`, `web/app.css` | vor dem Event | Repo-Skelett (UI-Hülle, ohne Logik) |
| `fixtures/` | vor dem Event | Testdaten, kein Produktcode |
| `api/` (FastAPI, Endpunkte) | **im Event** | Kernfunktionalität |
| `orchestrator/` (plan→dispatch→verify) | **im Event** | Kernfunktionalität |
| `tests/` | **im Event** | Prüfcode, keine Produktfunktion |
| Agent-Prompting, Verdict-Logik | **im Event** | Kernfunktionalität |
| Wiring UI → API | **im Event** | Kernfunktionalität |
| Deployment auf Vultr, Härtung | **im Event** | Betrieb |

## Grenzfälle, die ich bewusst so entschieden habe

- **`proxy/deny_proxy.py`** ist Infrastruktur, kein Agent. Er entscheidet nichts über Risiko,
  er protokolliert nur. Ohne ihn ist die Sandbox-Auswahl nicht prüfbar, deshalb fällt er unter
  Sandbox-Auswahl.
- **`models/client.py`** ist ein Transport-Client. Die Modellwahl passiert im Event, und der
  Client hardcodet bewusst keine Modell-ID.
- **`fixtures/`** ist grenzwertig. Es ist Testmaterial, aber es ist auch das Herzstück der Demo.
  Im Zweifel im LabLab-Discord fragen, bevor Zeit versenkt wird — Frage ist vorbereitet.
- **`web/`** ist Markup und CSS ohne Datenlogik. Die UI-Hülle ist Skelett; sobald sie fetch()-Calls
  bekommt, ist sie Kernfunktionalität und wandert in die Spalte „im Event".

## Regel für dieses Repo

Jeder Commit im Event-Fenster bekommt im README-Abschnitt „Status" eine Zeile. Keine Datei
wandert in die Tabelle oben, nachdem sie gebaut wurde.
