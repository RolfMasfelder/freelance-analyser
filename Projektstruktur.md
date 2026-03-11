freelance-analyser/
├── .github/copilot-instructions.md   ← aktualisiert mit Architektur
├── docker-compose.yml                ← App-Container + PostgreSQL
├── Dockerfile                        ← Python 3.13-slim
├── requirements.in                   ← alle Abhängigkeiten
├── .env.example                      ← Konfigurationsvorlage
├── .gitignore
├── TODO.md                           ← Aufgabenübersicht mit 10 Teilaufgaben
├── src/
│   ├── email_fetcher.py              ← 1. E-Mail abholen (IMAP)
│   ├── email_parser.py               ← 2. E-Mail parsen, Links extrahieren
│   ├── cookie_manager.py             ← 3. Browser-Cookies auslesen
│   ├── project_scraper.py            ← 4. Projektseiten scrapen
│   ├── project_parser.py             ← 5. HTML → strukturierte Daten
│   ├── database.py                   ← 6. PostgreSQL-Zugriff
│   ├── cv_manager.py                 ← 7. Lebenslauf verwalten
│   ├── matcher.py                    ← 8. Skill-Abgleich
│   └── scoring.py                    ← 8. Relevanz-Score
├── scripts/
│   └── run_pipeline.py               ← 10. Pipeline-Einstiegspunkt
├── tests/
├── data/
│   ├── raw_emails/
│   ├── projects/
│   └── cookies/
└── docs/
