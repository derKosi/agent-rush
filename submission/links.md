# Links und Felder

| Feld im Formular | Wert |
|---|---|
| Project title | Quarantine — prove a package is safe before it touches your machine |
| Demo application URL | http://45.77.143.94/ |
| Public GitHub repository | https://github.com/derKosi/agent-rush |
| Video | `video-v1/v2/v3.mp4` — eines auswählen und hochladen |
| Slides | `slides.pptx` |
| Cover image | `cover.png` |
| Licence | MIT (`LICENSE`) |

Demo-Zustand vor dem Absenden prüfen: `bash tools/selftest.sh http://45.77.143.94` muss
`selftest: ok` sagen. Achtung: der Selbsttest erzeugt drei eigene Läufe — danach Seed neu
fahren, sonst stehen Fixture-Namen zwischen den Demo-Läufen.
