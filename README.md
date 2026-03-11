# Freelance-Analyser

Automatisierte Pipeline zur Überwachung von Freelance-Projekten auf freelancermap.de mit CV-basiertem Matching und Ranking.

## Pipeline

```
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
docker compose up -d db            # PostgreSQL starten
docker compose build freelance-analyser  # App-Image bauen
```

## Benutzung

Alle Befehle werden über Docker Compose ausgeführt:

```bash
# Hilfe anzeigen
docker compose exec freelance-analyser python scripts/run_pipeline.py --help

# Komplette Pipeline: mbox parsen → gecachte HTML laden → DB → Match → Rank
docker compose exec freelance-analyser python scripts/run_pipeline.py run \
    --cv data/cv.yaml \
    --mbox data/raw_emails/freelancermap.mbox

# Mit Live-Scraping (benötigt gültige Browser-Cookies)
docker compose exec freelance-analyser python scripts/run_pipeline.py run \
    --cv data/cv.yaml \
    --mbox data/raw_emails/freelancermap.mbox \
    --scrape

# Nur Ranking auf bereits gespeicherte Projekte
docker compose exec freelance-analyser python scripts/run_pipeline.py rank \
    --cv data/cv.yaml \
    --top 10
```

## Tests

```bash
docker compose exec freelance-analyser python -m pytest tests/ -v
```

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
