# Abgabe-Checkliste

Ziel: heute fertig. Reihenfolge zählt, weil der Selbsttest die Demo-Historie verändert.

## 1. Instanz prüfen (5 min)

```bash
bash tools/selftest.sh http://45.77.143.94
```

Erwartet: `selftest: ok`, drei echte Läufe mit `low / low / high`.

## 2. Demo-Daten zurücksetzen (3 min)

```bash
ssh root@45.77.143.94 'rm -rf /opt/agent-rush/work/runs/*; systemctl restart agent-rush'
```

Dann die fünf Pakete in dieser Reihenfolge über die UI oder per CLI fahren:

`left-pad-again 1.2.0` · `blazingly-fast-utils 0.9.3` · `harborline 2.8.0` · `2.9.0` · `2.9.1`

## 3. Video auswählen und prüfen (5 min)

| Datei | Stimme | Länge |
|---|---|---|
| `submission/video-v1-andrew.mp4` | US, männlich | 1:53 |
| `submission/video-v2-ava.mp4` | US, weiblich | 2:00 |
| `submission/video-v3-vivienne.mp4` | FR-multilingual, weiblich | 1:49 |

Einmal ganz ansehen — Ton, Untertitel, und ob der Containment-Moment (Dependencies-Tab,
`blocked`) verständlich rüberkommt.

## 4. Formular ausfüllen (15 min)

| Feld | Quelle |
|---|---|
| Title, Short, Long description, Tags | `submission/description.md` |
| Application URL | `http://45.77.143.94/` |
| Public repository | `https://github.com/derKosi/agent-rush` |
| Video | gewählte Datei aus `submission/` |
| Slides | `submission/slides.pptx` |
| Cover | `submission/cover.png` |

## 5. Vor dem Absenden

- [ ] Demo-URL im Browser geöffnet, fünf Läufe sichtbar, keine Fixture-Namen im Rail
- [ ] Repo öffentlich, `LICENSE` sichtbar, README rendert (Bild + Diagramm)
- [ ] Video hochgeladen und in der Vorschau angespielt
- [ ] Alle Pflichtfelder grün, keine Warnung im Formular
- [ ] Bestätigungsseite als Screenshot gesichert

## 6. Nach dem Absenden

- [ ] Nichts mehr am Repo ändern
- [ ] Instanz laufen lassen (Juroren schauen nach der Deadline)
- [ ] Kostenlog abschließen, Nicht-Demo-Ressourcen terminieren
