# AI Coding Agent Instructions

## Critical Rules

**Development with Python 3.13**: Use Python 3.13 syntax and libraries only
**Tests required**: ALL features/bugfixes MUST have tests (unit + integration)
**Development with venv**: Use virtual environment for local dev (python -m venv venv)
**Git Commits**: Keep messages concise (feat/fix/refactor format). NO long descriptions. Only one line as commit-message
**Docker first**: ALL commands via `docker compose exec freelance-analyser`

## Architecture Basics

### Pipeline
```
Email-Fetch → Email-Parse → Link-Extract → Scrape (mit Cookies) → Parse HTML → DB Store → CV-Match → Rangliste
```

### Modules (src/)
- `email_fetcher.py` — IMAP-Abruf
- `email_parser.py` — E-Mail parsen, Kopfdaten + Links extrahieren
- `cookie_manager.py` — Browser-Cookies auslesen für freelancermap.de
- `project_scraper.py` — Projektseiten per HTTP abrufen (authentifiziert)
- `project_parser.py` — HTML → strukturierte Projektdaten
- `database.py` — SQLAlchemy-Models, DB-Zugriff (PostgreSQL)
- `cv_manager.py` — Lebenslauf laden und strukturieren
- `matcher.py` — Skill-Abgleich Projekt ↔ CV
- `scoring.py` — Relevanz-Score berechnen

### Key Libraries
- httpx (HTTP), beautifulsoup4+lxml (HTML), browser-cookie3 (Cookies)
- sqlalchemy+psycopg (DB), imapclient (E-Mail)
- rapidfuzz+scikit-learn (Matching), pydantic (Models), click (CLI)

## Git Remotes
- `origin` → Local mirror (NO CI)

## Documentation (if needed)
- Check `TODO.md` if needed
- Use `docs/` folder for additional docs
- Use `scripts/` folder for additional shell scripts
