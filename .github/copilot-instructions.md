# AI Coding Agent Instructions

## Critical Rules

**Development with Python 3.13**: Use Python 3.13 syntax and libraries only
**Tests required**: ALL features/bugfixes MUST have tests (unit + integration)
**Development with venv**: Use virtual environment for local dev (python -m venv venv). Any new Terminal must use `source venv/bin/activate` before running Python commands. DO NOT install packages globally.
**Git Commits**: Keep messages concise (feat/fix/refactor format). NO long descriptions. Only one line as commit-message
**Always use Docker**: ALL commands via `docker compose exec freelance-analyser ...` (Container must be running). DO NOT run Python scripts directly on host.

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
- `github` → Github mirror (→ PRs, Issues, CI)
- always push to both remotes: `git push origin dev && git push github dev`

## Git Workflow
- Work on `dev` branch only. NEVER push directly to `main`.
- Merge to `main` exclusively via Pull Request on GitHub (also applies to repo owner).
- After merging a PR: `git checkout main && git pull github main && git push origin main && git checkout dev && git merge main && git push origin dev && git push github dev`


## Documentation (if needed)
- Check `TODO.md` if needed
- Use `docs/` folder for additional docs
- Use `scripts/` folder for additional shell scripts
