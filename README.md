# Freelance-Analyser

Automatisierte Pipeline zur Überwachung von Freelance-Projekten auf freelancermap.de: E-Mails abholen, Projekte scrapen, CV-basiertes Matching, Rangliste — und per Klick ein Bewerbungsschreiben per LLM generieren.

## Was es kann

- **Automatisches Monitoring**: Ruft Projekt-E-Mails via IMAP ab und scrapt die Detailseiten von freelancermap.de (mit Cookie-Authentifizierung)
- **CV-Matching**: Gleicht Projekt-Skills gegen das eigene CV ab (exakter + Fuzzy-Match), berechnet einen Relevanz-Score
- **Ausschlussfilter**: Definierbare Skills und Branchen, die automatisch aus der Rangliste herausgefiltert werden
- **Web-UI**: Browser-basierte Rangliste mit Statusverwaltung und Detailansicht
- **Antwortschreiben per LLM**: Ein-Klick-Generierung eines individuellen Bewerbungsschreibens auf Basis des CVs und der Projektanforderungen (OpenAI-kompatible API)

## Web-UI

```bash
docker compose up -d       # Alle Container starten (einmalig)
# → http://localhost:8080
```

### Rangliste (`/`)

Zeigt alle gematchten Projekte sortiert nach Relevanz-Score:

- **Statusfilter**: `neu` / `gesehen` / `beworben` / `abgelehnt` / `alle`
- **Altersfilter**: Standardmäßig nur Projekte der letzten 30 Tage (`?include_old=true` für alle)
- **Top-N**: Anzahl konfigurierbar via `?top=N` (max. 500)

### Projektdetail (`/project/<id>`)

Zeigt Projektbeschreibung, geforderte Skills, gematchte und fehlende CV-Skills.

- **Status setzen**: Projekt direkt als `gesehen`, `beworben` oder `abgelehnt` markieren
- **Antwortschreiben generieren**: Klick auf „Antwortschreiben generieren" erstellt per LLM ein individuelles Bewerbungsschreiben
  - Sprache wird automatisch aus der Projektausschreibung erkannt (Deutsch/Englisch)
  - Nur tatsächlich vorhandene Erfahrungen aus dem CV fließen ein (keine Halluzinationen durch strikten Prompt)
  - Genutztes Modell wird angezeigt (konfigurierbar via `LLM_MODEL` in `.env`)

## Pipeline

```txt
E-Mail abholen → Parsen → Links extrahieren → Scrapen → DB speichern → CV-Matching → Rangliste
```

```bash
# Neue E-Mails via IMAP abholen → scrapen → matchen → ranken (Standard)
docker compose exec freelance-analyser python scripts/run_pipeline.py run

# Ohne Live-Scraping (gecachte HTML-Dateien nutzen)
docker compose exec freelance-analyser python scripts/run_pipeline.py run --no-scrape

# Lokale mbox-Datei statt IMAP
docker compose exec freelance-analyser python scripts/run_pipeline.py run \
    --no-imap --mbox "data/raw_emails/meine-mails.mbox"

# Nur Ranking neu berechnen (ohne E-Mail-Abruf)
docker compose exec freelance-analyser python scripts/run_pipeline.py rank --top 10
```

## Setup

### Voraussetzungen

- Docker + Docker Compose
- Firefox (für Cookie-Extraktion von freelancermap.de)
- OpenAI-kompatibler API-Endpunkt (für Antwortschreiben, z. B. OpenAI, Ollama, LM Studio)

### Installation

```bash
# 1. Repository klonen
git clone https://github.com/RolfMasfelder/freelance-analyser.git
cd freelance-analyser

# 2. .env anlegen
cp .env.example .env
# → Zugangsdaten eintragen (DB, IMAP, LLM-API)

# 3. CV befüllen
# data/cv.yaml mit eigenen Skills, Erfahrungen und Präferenzen anpassen

# 4. Container bauen und starten
docker compose build freelance-analyser
docker compose up -d
```

### Cookies exportieren (einmalig, auf dem HOST)

```bash
# Benötigt Firefox mit aktiver freelancermap.de-Session
python scripts/export_cookies.py
# → Speichert nach data/cookies/freelancermap.json
```

### CV aus ODT-Datei erzeugen

```bash
# Lebenslauf (ODT) per LLM analysieren und data/cv.yaml erzeugen
# Auf dem HOST ausführen (liest LLM_BASE_URL / LLM_API_KEY / LLM_MODEL aus .env)
python scripts/extract_cv.py data/mein-lebenslauf.odt

# Nur anzeigen, nicht schreiben
python scripts/extract_cv.py data/mein-lebenslauf.odt --dry-run

# Alternativer Ausgabepfad
python scripts/extract_cv.py data/mein-lebenslauf.odt -o data/cv_neu.yaml
```

> Das Script liest den Volltext aus der ODT-Datei, sendet ihn an das konfigurierte LLM und schreibt strukturiertes YAML mit Skills, Projekterfahrungen und Präferenzen direkt nach `data/cv.yaml`.

## Konfiguration (`.env`)

| Variable | Beschreibung |
|---|---|
| `DATABASE_URL` | PostgreSQL-Verbindung |
| `IMAP_HOST` / `IMAP_USER` / `IMAP_PASSWORD` | E-Mail-Zugang |
| `FREELANCERMAP_COOKIE_BROWSER` | Browser für Cookie-Extraktion (`firefox`) |
| `LLM_BASE_URL` | API-Endpunkt (OpenAI-kompatibel) |
| `LLM_API_KEY` | API-Key |
| `LLM_MODEL` | Modellname, z. B. `gpt-4o-mini`, `llama3` |
| `CV_PATH` | Pfad zur CV-Datei (Standard: `data/cv.yaml`) |
| `LOG_LEVEL` | Logging-Level (`INFO`, `DEBUG`, …) |

## Tests

```bash
docker compose exec freelance-analyser python -m pytest tests/ -v
```

## Projektstruktur

```txt
src/
├── email_fetcher.py    — IMAP-Abruf
├── email_parser.py     — E-Mail parsen, Links extrahieren
├── cookie_manager.py   — Browser-Cookies auslesen
├── project_scraper.py  — Projektseiten scrapen (authentifiziert, mit Retry)
├── project_parser.py   — HTML → strukturierte Projektdaten
├── database.py         — SQLAlchemy-Models, PostgreSQL-Zugriff
├── cv_manager.py       — Lebenslauf laden (YAML)
├── matcher.py          — Skill-Abgleich (exakt + fuzzy)
├── scoring.py          — Relevanz-Score & Ranking
├── letter_generator.py — Antwortschreiben per LLM (OpenAI-kompatibel)
└── web.py              — FastAPI-Web-UI
scripts/
├── run_pipeline.py     — CLI-Einstiegspunkt (Click)
├── export_cookies.py   — Firefox-Cookies für freelancermap.de exportieren (HOST)
└── extract_cv.py       — Lebenslauf (ODT) per LLM in data/cv.yaml konvertieren
```
