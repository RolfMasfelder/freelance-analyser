# AI Coding Agent Instructions

## Critical Rules

**Development with Python 3.13**: Use Python 3.13 syntax and libraries only
**Tests required**: Every feature or bugfix MUST include at least one unit test; integration tests are required when the change affects module boundaries (DB, HTTP, IMAP). Run tests via `docker compose exec freelance-analyser pytest tests/`. Minimum 80% coverage on new code.
**Always use Docker**: ALL commands via `docker compose exec freelance-analyser ...`. DO NOT run Python scripts directly on the host. If the container is not running, start it first with `docker compose up -d`.
**Git Commits**: Use Conventional Commits format: `<type>: <subject>` where type ∈ {feat, fix, refactor, chore, docs, test}. Single line, max 72 chars, no body.
**Language**: Code, comments, and docstrings in English. Commit messages in English. User-facing CLI output in German.

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
- If pushing to one remote fails, report the failure explicitly — do not consider the operation complete until both remotes are in sync.

## Git Workflow
- Work on `dev` branch only. NEVER push directly to `main`.
- Merge to `main` exclusively via Pull Request on GitHub (also applies to repo owner).
- After merging a PR, run these steps in order:
  1. `git checkout main`
  2. `git pull github main`
  3. `git push origin main`
  4. `git checkout dev`
  5. `git merge main` — if conflicts occur, stop and request user guidance; do not auto-resolve or force-push
  6. `git push origin dev && git push github dev`


## Documentation (if needed)
- Consult `TODO.md` before starting any new feature or when the user references pending work.
- Use `docs/` folder for additional docs
- Use `scripts/` folder for additional shell scripts
