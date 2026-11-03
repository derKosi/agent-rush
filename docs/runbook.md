# Runbook — VM aufsetzen und deployen

Status: **noch nicht ausgeführt.** Alles hier ist vorbereitet, aber kein Befehl ist auf einer
echten Vultr-Instanz gelaufen. Das bleibt so, bis am 03.11. der erste grüne Durchlauf existiert.

## 1. VM anlegen

In der Vultr-Konsole:

- Region: Frankfurt oder Amsterdam
- Plan: 2 vCPU / 4 GB, **Ubuntu 24.04 LTS**
- SSH-Key hinterlegen (Pflicht — Passwort-Login wird vom Bootstrap abgeschaltet)
- **User Data einfügen:** Inhalt von `deploy/cloud-init.yaml`
- Firewall-Gruppe: inbound nur 22, 80, 443. **8080 und 8899 nie öffentlich.**

Der Bootstrap installiert Docker, Caddy, ufw; legt den User `arrush` an, gibt ihm die
Docker-Gruppe und öffnet nur 22/80/443. Prüfen:

```bash
ssh root@<ip> 'cat /var/log/agent-rush-bootstrap.log; docker run --rm hello-world | head -3'
ssh root@<ip> 'ufw status; systemctl is-active docker caddy'
```

**Wenn cloud-init nicht durchläuft:** nicht debuggen, sondern die sechs Schritte von Hand —
`apt-get install -y docker.io git python3-venv caddy ufw`, dann `ufw allow 22/tcp 80/tcp 443/tcp`,
`useradd -m arrush`, `usermod -aG docker arrush`, `systemctl enable --now docker caddy`.
Das kostet fünf Minuten, Fehlersuche im Bootstrap kostet eine Stunde.

## 2. Repo und Secrets

```bash
git clone https://github.com/derKosi/agent-rush.git /opt/agent-rush
cd /opt/agent-rush
sudo bash deploy/install-service.sh
sudo -u arrush cp .env.example .env && sudo chmod 600 .env
sudo -u arrush nano .env          # AR_VULTR_KEY eintragen
```

Der Key steht nur in `.env` auf der VM und in der Prozessumgebung des Orchestrators.
Nicht im Container, nicht im Repo, nicht im Log.

## 3. Inference prüfen, bevor Code entsteht

```bash
cd /opt/agent-rush
set -a && . ./.env && set +a
python3 models/smoke_test.py --list          # echte Modell-IDs aus dem Katalog
# GLM 5.2 heraussuchen, AR_MODEL in .env setzen, dann:
python3 models/smoke_test.py --prompt "ping"
```

Das ist der erste Meilenstein des Tages. Solange dieser Call nicht antwortet, ist jede
Agent-Logik Spekulation.

## 4. Sandbox-Image

```bash
bash fixtures/make_fixture.sh
bash deploy/build_and_push.sh
bash sandbox/run.sh --dry-run fixtures/sample_pkg-0.1.0.tar.gz demo
bash sandbox/run.sh fixtures/sample_pkg-0.1.0.tar.gz demo
```

Erwartung beim ersten echten Lauf: `pip_exit != 0` ist **normal**, das Fixture scheitert
absichtlich. Entscheidend ist, dass `out/exec.json` entsteht und danach kein Container läuft
(`docker ps` leer).

## 5. Proxy-Modus (die Beweisvariante fürs Video)

```bash
mkdir -p work
AR_EGRESS_MODE=proxy AR_ALLOW= AR_PROXY_LOG="$PWD/work/egress.jsonl" \
  bash sandbox/run.sh fixtures/sample_pkg-0.1.0.tar.gz demo1
```

Erwartung: eine Zeile mit `"decision": "deny"` für `collector.invalid`. Bleibt der Log leer,
stimmt die Netzwerk-Topologie nicht — nicht das Fixture.

## 6. Web-App

Nachdem `api/main.py` existiert (im Event-Fenster):

```bash
sudo -u arrush /opt/agent-rush/.venv/bin/pip install fastapi uvicorn
sudo systemctl start agent-rush && sudo systemctl status agent-rush
curl -s localhost:8080/health
```

Caddy läuft davor und ist bereits aktiv; die öffentliche URL ist `http://<ip>/`.
Für TLS ohne Domain: Instanz als `203.0.113.10.sslip.io` benennen und in `deploy/Caddyfile`
`:80` durch diesen Hostnamen ersetzen.

## 7. Nach der Abgabe

```bash
docker ps -a                  # keine Reste
vultr-cli instance list       # alles außer der Demo-Instanz weg
```

Kostentabelle in `docs/cost-log.md` abschließen.
