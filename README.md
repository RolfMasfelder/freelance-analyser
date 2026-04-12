# Freelance-Analyser

Automatisierte Pipeline zur Überwachung von Freelance-Projekten auf freelancermap.de mit CV-basiertem Matching und Ranking.

## Pipeline

```txt
E-Mail abholen → Parsen → Links extrahieren → Scrapen → DB speichern → CV-Matching → Rangliste
```

## Voraussetzungen

- Docker + Docker Compose
- Firefox (für Cookie-Extraktion von freelancermap.de)
- mbox-Datei mit Projekt-E-Mails (Export aus E-Mail-Client)

## Setup

```bash
# 1. Repository klonen
git clone <repo-url> && cd freelance-analyser

# 2. .env anlegen
cp .env.example .env
# → Zugangsdaten eintragen (DB, IMAP, Freelancermap)

# 3. CV vorbereiten
# data/cv.yaml mit eigenen Skills/Präferenzen befüllen (siehe data/cv.yaml als Vorlage)

# 4. Container starten
docker compose build freelance-analyser  # App-Image bauen
docker compose up -d                     # Alle Container starten
```

## Benutzung

Alle Befehle werden über Docker Compose ausgeführt (Container muss laufen):

```bash
# Hilfe anzeigen
docker compose exec freelance-analyser python scripts/run_pipeline.py --help

# Cookies exportieren (auf dem HOST, nicht im Container!)
# → Benötigt Firefox mit gültiger freelancermap.de-Session
# → Speichert Cookies nach data/cookies/freelancermap.json
python scripts/export_cookies.py

# Neue E-Mails via IMAP abholen → scrapen → DB → Match → Rank (Standard)
docker compose exec freelance-analyser python scripts/run_pipeline.py run

# Ohne Live-Scraping (nur E-Mail-Basisdaten + gecachte HTML-Dateien)
docker compose exec freelance-analyser python scripts/run_pipeline.py run --no-scrape

# Mit eigener CV-Datei (Standard: data/cv.yaml)
docker compose exec freelance-analyser python scripts/run_pipeline.py run \
    --cv data/cv.yaml

# Alternativ: Lokale mbox-Datei verarbeiten (kein IMAP)
docker compose exec freelance-analyser python scripts/run_pipeline.py run \
    --no-imap --mbox "data/raw_emails/meine-mails.mbox"

# Nur Ranking auf bereits gespeicherte Projekte
docker compose exec freelance-analyser python scripts/run_pipeline.py rank --top 10
```

## Tests

```bash
docker compose exec freelance-analyser python -m pytest tests/ -v
```

## Web-UI

Das Frontend zeigt die Rangliste und Projektdetails im Browser.

```bash
# Web-Container starten (nur einmalig nötig, läuft dann dauerhaft)
docker compose up -d web

# → http://localhost:8080
```

| Route | Beschreibung |
|---|---|
| `/` | Rangliste (Top 50, konfigurierbar via `?top=N`, max. 500) |
| `/project/<id>` | Projektdetail: Infos, geforderte Skills, CV-Match |

Die Anzeige basiert auf den in der DB gespeicherten Match-Ergebnissen — zuerst die Pipeline ausführen (`run_pipeline.py run`), dann das Frontend öffnen.

## Projektstruktur

```
src/
├── email_fetcher.py    — IMAP-Abruf
├── email_parser.py     — E-Mail parsen, Links extrahieren
├── cookie_manager.py   — Browser-Cookies auslesen
├── project_scraper.py  — Projektseiten scrapen (authentifiziert)
├── project_parser.py   — HTML → strukturierte Projektdaten
├── database.py         — SQLAlchemy-Models, PostgreSQL-Zugriff
├── cv_manager.py       — Lebenslauf laden (YAML)
├── matcher.py          — Skill-Abgleich (exakt + fuzzy)
└── scoring.py          — Relevanz-Score & Ranking
scripts/
└── run_pipeline.py     — CLI-Einstiegspunkt (Click)
```

## Konfiguration

Alle Einstellungen über `.env` (siehe `.env.example`):

| Variable | Beschreibung |
|---|---|
| `DATABASE_URL` | PostgreSQL-Verbindung |
| `IMAP_HOST/USER/PASSWORD` | E-Mail-Zugang |
| `FREELANCERMAP_COOKIE_BROWSER` | Browser für Cookie-Extraktion (`firefox`) |
| `LOG_LEVEL` | Logging-Level (`INFO`, `DEBUG`, …) |
