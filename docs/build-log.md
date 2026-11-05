# Build log — fünf Tage, chronologisch

Für den Blogpost: was wann entstand, welche Entscheidung warum fiel, und welche Fehler nur ein
echter Lauf gefunden hat. Alles hier ist aus Commits und Läufen belegbar.

## Tag 0 — vor dem Fenster (26.10.)

Repo-Skelett, MIT-Lizenz, Architektur, Demo-Drehbuch, gehärtetes Dockerfile, Deny-Proxy,
Inference-Client. Ausdrücklich **nicht**: Agent-Loop, API, UI-Verdrahtung. `docs/provenance.md`
führt Datei für Datei, was vorher entstand — die LabLab-Regel verlangt diese Trennung, also
wird sie dokumentiert statt behauptet.

Entscheidung: **VM-first**, nicht lokal. Kein Docker auf dem Mac, aber die VM ist das Ziel —
dann prüft man gleich dort.

## Tag 1 (03.11.) — Fundament

`run_store` (ein Verzeichnis pro Lauf) und `sandbox` (ruft `run.sh`, liest Artefakte von
Platte statt die Ausgabe zu parsen). Sieben Tests gegen ein Stub-Runner, damit die Basis ohne
Docker prüfbar ist.

Fehler: `sshkey_ids` statt `sshkey_id` — Vultr ignoriert unbekannte Felder still, die Instanz
bootete ohne Key. Eine Instanz umsonst gebaut. Zweiter Fehler: User-Data wurde über den
API-Weg gar nicht angewandt, cloud-init lief durch und installierte nichts. Seitdem macht
`deploy/vm-bootstrap.sh` die Arbeit über SSH.

## Tag 2 (04.11.) — Urteil und Oberfläche

`verdict.py`: Regeln zuerst, Modell zweitens, jede Modell-Aussage muss eine Quelle zitieren,
die in *diesem* Lauf existiert. `api/main.py` mit drei Endpunkten. 27 Tests.

Erster echter Containerlauf: `write /opt` → `OSError`, Egress → 403 am Proxy, Decoy-Key →
`FileNotFoundError`, Spawn → **ok**. Der Spawn wird als „nicht verhindert" berichtet, weil
alles andere gelogen wäre.

## Tag 3 (05.11.) — die unangenehmen Funde

Vier Dinge, die nur durch Ausführen auffielen:

1. **macOS-tar** packte AppleDouble-Dateien ein → pip sah kein `setup.py`.
2. **python:3.12-slim** hat kein setuptools → `BackendUnavailable` bei `--no-build-isolation`.
3. **pip schluckt die Ausgabe** eines erfolgreichen Build-Hooks → der Report musste in eine Datei.
4. **Mein Guard gegen Modellcode** verwarf ein harmloses Skript, weil im Kommentar
   „no subprocess" stand. Textmatching ist kein Verständnis; jetzt läuft eine AST-Prüfung.

Dann der Injection-Moment: ein Fixture, das beim Install eine Anweisung an den Leser ausgibt.
Der erste Versuch scheiterte unspektakulär — der Auszug las nur die ersten 1500 Zeichen, die
Injection stand am Dateiende. Kopf **und** Ende lesen, dann findet es das Modell selbst.

Zwei Löcher, die dabei auffielen und geschlossen wurden: das Modell konnte Probes **abwählen**
(damit verschwindet der Beweis, der es überführt hätte), und seine Zusammenfassung konnte dem
Risiko-Badge widersprechen.

## Tag 4 — Reichweite statt Tiefe

Import-Pass (ein Paket kann beim Bauen brav und beim ersten `import` feindlich sein),
Abhängigkeiten als Wheels geholt und gehasht, npm-Adapter, OSV-Reputation mit konfigurierbarer
Block-Schwelle, SARIF, CLI mit Exit-Codes, Compose.

Jede dieser Erweiterungen hat dieselbe Form: neuer Adapter, gleiche Evidence-Schicht. Das war
die eigentliche These des Projekts — Beweise sind sprachunabhängig, Ausführung nicht.

## Was ich anders machen würde

- **Früher echt ausführen.** Die vier Fehler von Tag 3 hätte ich an Tag 1 haben können.
- **Weniger Breite, früher Tiefe.** npm und Dependencies kamen vor dem Video. Aus
  Jury-Sicht war das die falsche Reihenfolge.
- **Den Flake früher jagen.** Ein Batch-Test schlug einmal fehl und ließ sich in sieben
  Läufen nicht reproduzieren — das steht so im Bericht, statt „behoben" zu behaupten.
