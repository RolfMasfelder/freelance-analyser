# Freelance-Analyser — Aufgabenübersicht

## Pipeline-Übersicht

```txt
E-Mail abholen → Parsen → Links extrahieren → Projektseiten scrapen → Projekte speichern → CV-Matching → Trefferliste
```

---

## Erledigt

- [x] E-Mail-Parsing aus mbox (Kopfdaten, Links, Projekt-ID) — `email_parser.py`
- [x] Browser-Cookies auslesen (Firefox) — `cookie_manager.py`
- [x] Projektseiten scrapen (authentifiziert, 5s Delay, Cache) — `project_scraper.py`
- [x] HTML → strukturierte Projektdaten — `project_parser.py`
- [x] PostgreSQL-Schema, Upsert, CRUD — `database.py`
- [x] CV aus YAML laden, Skills strukturieren — `cv_manager.py`
- [x] Skill-Matching (exakt + fuzzy, Ausschlüsse) — `matcher.py`
- [x] Scoring (gewichtet: Skills/Remote/Ort/Vertragsart) — `scoring.py`
- [x] CLI-Pipeline mit `run` und `rank` Kommandos — `run_pipeline.py`
- [x] Docker-Container (App + PostgreSQL) — `Dockerfile`, `docker-compose.yml`
- [x] 120 Tests (alle bestanden)
- [x] IMAP-Verbindung zu ionos.de (Live-Abruf via `email_fetcher.py`) — `email_fetcher.py`
- [x] E-Mails automatisch abrufen (nur neue/ungelesene, `UNSEEN`-Filter) — `email_fetcher.py`
- [x] Bereits verarbeitete E-Mails markieren (`mark_seen=True`) — `email_fetcher.py`
- [x] Scoring-Gewichtungen gesetzt (Skills 50%, Keywords 15%, Remote 15%, Ort 10%, Vertrag 10%) — `scoring.py`
- [x] Fuzzy-Matching-Schwellenwert gesetzt (80) — `matcher.py`
- [x] Primär-Skills stärker gewichten (2× Multiplikator) — `scoring.py`
- [x] Cookie-Extraktion im Container (JSON-Datei unter `data/cookies/`) — `cookie_manager.py`
- [x] Web-UI für Ergebnisanzeige (FastAPI + Jinja2, Bootstrap 5) — `src/web.py`, `templates/`
- [x] .dockerignore angelegt

---

## Offen

### Cookie-Management

- [ ] Abgelaufenes/ungültiges Cookie erkennen, Hinweis ausgeben und Lauf abbrechen (Cookie manuell erneuern via Browser-Login)

### Ergebnis-Export

- [ ] ~~Export als CSV/JSON/Markdown~~ *(zurückgestellt — Terminal-Output reicht derzeit)*

### Automatisierung

- [x] Alembic-Migrationen einrichten
- [x] .dockerignore anlegen (venv, __pycache__, .git, data/projects)

### Web-UI

- [x] Filter für Projekte älter als 30 Tage (ein-/ausblendbar)

### Später / Nice-to-have

- [x] Historisierung (wann Projekt gesehen, Status-Änderungen)
- [ ] Benachrichtigung bei neuen Top-Treffern *(wird noch überlegt)*
