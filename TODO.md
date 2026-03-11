# Freelance-Analyser — Aufgabenübersicht

## Pipeline-Übersicht

```
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

---

## Offen

### IMAP-Abruf
- [ ] IMAP-Verbindung zu ionos.de testen/fixen (Verbindungsfehler)
- [ ] E-Mails automatisch vom Postfach abrufen (nur neue/ungelesene)
- [ ] Bereits verarbeitete E-Mails markieren (kein Doppelt-Import)
- [ ] Aktuell nur mbox-Import — Live-IMAP-Abruf integrieren

### Scoring-Tuning
- [ ] Gewichtungen anpassen (aktuell: Skills 50%, Keywords 15%, Remote 15%, Ort 10%, Vertrag 10%)
- [ ] Fuzzy-Matching-Schwellenwert optimieren (aktuell 80)
- [ ] Primär-Skills stärker gewichten
- [ ] Ergebnisse mit manuellem Feedback vergleichen

### Cookie-Management
- [ ] Fallback: Login via Username/Passwort wenn Cookie abgelaufen
- [ ] Cookie-Extraktion im Container (kein Host-Firefox verfügbar)

### Ergebnis-Export
- [ ] Export als CSV/JSON/Markdown
- [ ] Tägliche Zusammenfassung per E-Mail

### Automatisierung
- [ ] Scheduler (cron/systemd-Timer) für regelmäßigen Pipeline-Lauf
- [ ] Alembic-Migrationen einrichten
- [ ] .dockerignore anlegen (venv, __pycache__, .git, data/projects)

### Später / Nice-to-have
- [ ] Web-UI für Ergebnisanzeige
- [ ] Historisierung (wann Projekt gesehen, Status-Änderungen)
- [ ] Benachrichtigung bei neuen Top-Treffern
