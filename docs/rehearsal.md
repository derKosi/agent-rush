# Probe für den Containment-Moment

Zweck: die Befehlsfolge fürs Video einmal trocken laufen, bevor die Kamera an ist. Alles hier
ist Terminal-Zeug, keine Folien. Wenn ein Befehl hier anders aussieht als in
`docs/demo-storyboard.md`, gilt diese Datei — sie ist die ausführbare Fassung.

Voraussetzung: Repo auf der VM, `.env` gesetzt, Sandbox-Image gebaut.

## 0. Ausgangszustand herstellen

```bash
cd /opt/agent-rush
mkdir -p work
rm -f work/egress.jsonl
docker ps -a --filter name=ar-task --format '{{.Names}}'    # muss leer sein
```

Für den Host-Gegenbeweis eine Datei außerhalb des Containers markieren:

```bash
echo "untouched $(date -u +%FT%TZ)" | sudo tee /opt/ar-host-marker
sha256sum /opt/ar-host-marker
```

Diese Summe steht später im Video **vor** und **nach** dem Lauf. Sie ist der Punkt, an dem
die Jury sieht, dass der Host unberührt blieb.

## 1. Policy zeigen (10 Sekunden, vor dem Lauf)

```bash
bash sandbox/run.sh --dry-run fixtures/sample_pkg-0.1.0.tar.gz demo
```

Gibt den vollständigen `docker run` aus: `--network none`, `--read-only`, `--user 10001:10001`,
`--cap-drop ALL`, `--pids-limit`, `--memory`. Das ist die Behauptung „isoliert" in ausführbarer
Form — deshalb steht sie vor dem Lauf im Video, nicht danach.

## 2. Lauf mit Beweisen

```bash
AR_EGRESS_MODE=proxy AR_ALLOW= AR_PROXY_LOG="$PWD/work/egress.jsonl" \
  bash sandbox/run.sh fixtures/sample_pkg-0.1.0.tar.gz demo
```

Erwartete Artefakte danach:

```bash
cat work/egress.jsonl              # deny-Zeile mit collector.invalid
cat /tmp/ar-sandbox-*/out/exec.json # pip_exit, duration
docker ps -a --filter name=ar-task  # leer
sha256sum /opt/ar-host-marker       # identisch zu Schritt 0
ls /opt/ar-probe                    # existiert nicht
```

## 3. Was schiefgehen kann, und was dann zu tun ist

| Symptom | Ursache | Reaktion |
|---|---|---|
| `egress.jsonl` bleibt leer | Container nicht im Proxy-Netz | auf `AR_EGRESS_MODE=none` wechseln, Datei-Diff als Beweis nehmen |
| Lauf hängt bis Timeout | Kindprozess hält stdout | `AR_TIMEOUT_S=20` setzen, nicht debuggen |
| `pip_exit=0` | Fixture wurde nicht ausgeführt | Tarball prüfen: `tar tzf` muss `setup.py` zeigen |
| `docker: permission denied` | User nicht in der Docker-Gruppe | neu einloggen, nicht `sudo` drumherum |

## 4. Aufnahme-Reihenfolge (ein Take)

1. `sha256sum` des Markers — sichtbar im Bild
2. `bash sandbox/run.sh --dry-run …` — Flags scrollen langsam
3. echter Lauf, Trace im Browser daneben
4. `cat work/egress.jsonl` — die deny-Zeile
5. `sha256sum` erneut — identisch
6. Report im UI öffnen, Download zeigen

Wenn ein Schritt hakt: Take neu, nicht erklären. Drei Takes sind das Budget.
