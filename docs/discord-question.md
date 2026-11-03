# Discord-Frage vor dem Event (Entwurf)

Nicht abschicken, bevor du sie gelesen hast. Kurz halten — im LabLab-Discord antworten
Organisatoren lieber auf eine präzise Frage als auf einen Absatz.

**Kanal:** Vultr-Hackathon-Channel (Invite: https://discord.gg/uP2TQVtkRj)

---

Hi — quick clarification on the pre-work rule for Track 1, so I don't burn time on the wrong
side of the line.

I have scaffolding ready and **not** the agent itself:

- repo skeleton, MIT LICENSE, README
- a hardened Dockerfile + `docker run` flags (read-only root, non-root, pids/mem caps)
- a deny-by-default egress proxy that just logs decisions (no agent logic)
- an OpenAI-compatible client for `api.vultrinference.com` that lists the catalog and reads
  the model id from an env var
- a synthetic test package whose build hook logs what it attempts (write outside the build
  dir, one HTTP call to a `.invalid` host, a decoy key read, a detached child)

The agent loop, the verdict logic, the API and the web wiring will all be written during
3–8 Nov, and the repo documents which file was created when.

Question: is the synthetic **test package** acceptable as pre-work, or would you rather it be
authored inside the window? It's test data, not product code, but it is also the thing the demo
detonates, so I'd rather ask than assume.

Thanks!

---

## Was du mit der Antwort machst

- **„fine"** → Package bleibt, `docs/provenance.md` bekommt eine Zeile mit Datum und Zitat.
- **„author it in the window"** → `fixtures/` wird am 03.11. neu geschrieben, alte Fassung aus
  dem Repo entfernt. Der Rest des Vorwerks bleibt unberührt.
- **keine Antwort bis 03.11.** → Package im Fenster neu schreiben. Zehn Minuten Arbeit,
  null Risiko bei der Bewertung.
