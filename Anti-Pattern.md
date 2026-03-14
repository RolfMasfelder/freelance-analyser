# Anti-Pattern — Befunde und Korrekturen

Ergebnis eines Code-Reviews. Punkte 1 und 2 (Konfiguration) wurden bereits in einer früheren Session behoben.

---

## 1. Hardcoded Credentials in Config-Defaults ✅ behoben

**Datei:** `src/config.py`
**Problem:** `postgres_password` und `database_url` hatten "changeme" als Defaultwert — ein Deployment ohne `.env` würde stillschweigend unsichere Defaults verwenden. Passwort stand an zwei Stellen (Config + `database_url`), die drift-anfällig waren.
**Lösung:** Pflichtfelder (`database_url`, `imap_host`, `imap_user`, `imap_password`) haben kein Default mehr. Fehlt ein Wert in `.env`, gibt pydantic sofort einen `ValidationError`. `postgres_user/password/db` wurden entfernt (nur docker-compose braucht diese). `.env.example` ohne Credentials angelegt.

---

## 2. Modul-Level Singletons in web.py beim Import ✅ behoben

**Datei:** `src/web.py`
**Problem:** `_engine = get_engine(...)` und `_SessionFactory = get_session_factory(...)` wurden beim Import der Datei ausgeführt. Jeder Test, der `from src.web import app` macht, hätte sofort eine DB-Verbindung aufgebaut — auch wenn keine DB läuft.
**Lösung:** Engine und SessionFactory werden lazy initialisiert via `functools.lru_cache` — erst beim ersten echten Request, nicht beim Import.

---

## 3. Dead Code in `verify_session()` ✅ behoben

**Datei:** `src/cookie_manager.py`, Funktion `verify_session()`
**Problem:** Das letzte Statement `return resp.status_code == 200` kann niemals `True` ergeben — Code kommt dort nur hin, wenn `status_code != 200` ist. Der zurückgegebene Wert war also immer `False`.
**Lösung:** Ersetzt durch `return False` mit erklärendem Log-Eintrag.

---

## 4. Bare `except Exception: pass` ✅ behoben

**Datei:** `src/email_parser.py`, Funktion `_decode_quoted_printable()`
**Problem:** Der `except`-Block hat alle Ausnahmen (inkl. echter Bugs wie `AttributeError`) still geschluckt. Ein Fehler bei der QP-Dekodierung hätte den Original-Text zurückgegeben, ohne jeglichen Hinweis.
**Lösung:** Spezifische Ausnahme `(UnicodeDecodeError, ValueError)` abgefangen; mit `logger.debug` geloggt.

---

## 5. Overly broad `except Exception` im Scraper ✅ behoben

**Datei:** `src/project_scraper.py`, Funktion `scrape_project_pages()`
**Problem:** Alle Ausnahmen wurden gleich behandelt — Netzwerkfehler (erwartet) und Programmfehler (Bugs) wurden beide nur geloggt und übersprungen. Ein systematischer Bug hätte N identische Fehlermeldungen produziert.
**Lösung:** Nur erwartete Fehler (`httpx.HTTPError`, `RuntimeError`) werden abgefangen und übersprungen. Unerwartete Ausnahmen werden weitergeworfen.

---

## 6. `import re` innerhalb einer Funktion ✅ behoben

**Datei:** `src/project_scraper.py`, Funktion `_extract_id_from_url()`
**Problem:** `import re` stand innerhalb der Funktion — bei jedem Aufruf wurde der Import-Mechanismus aktiviert. Stilistisch inkonsistent, geringer aber vermeidbarer Overhead.
**Lösung:** `import re` an den Anfang der Datei verschoben.

---

## 7. CWD-relativer Pfad `COOKIE_FILE` ✅ behoben

**Datei:** `src/cookie_manager.py`
**Problem:** `COOKIE_FILE = Path("data/cookies/freelancermap.json")` ist relativ zum aktuellen Arbeitsverzeichnis. Wird die Datei aus einem anderen Verzeichnis importiert (z.B. pytest von `/home/user`), zeigt der Pfad ins Leere und Cookies werden ohne Fehlermeldung nicht gefunden.
**Lösung:** Pfad wird relativ zum Modul verankert: `Path(__file__).parent.parent / "data/cookies/freelancermap.json"`.

---

## 8. N+1 Queries in `upsert_projects()` ✅ behoben

**Datei:** `src/database.py`, Funktion `upsert_projects()`
**Problem:** Für jedes Projekt in der Liste wurde ein separates `SELECT` + `INSERT/UPDATE` ausgeführt — bei 100 Projekten also 200 DB-Roundtrips.
**Lösung:** Alle IDs werden in einem Query vorgeladen (`SELECT ... WHERE project_id IN (...)`), dann wird lokal geprüft ob insert oder update.

---

## 9. `get_top_matches()` gibt Duplikate zurück ✅ behoben

**Datei:** `src/database.py`, Funktion `get_top_matches()`
**Problem:** Jeder Pipeline-Lauf erzeugt neue `MatchResult`-Zeilen. Die Funktion fragte alle ohne Deduplizierung ab — ein Projekt tauchte mehrfach auf.
**Lösung:** `MAX(id)` Subquery zur Deduplizierung, wie bereits in `web.py` korrekt implementiert.

---

## 10. `top`-Parameter ohne Bounds-Check in Web-UI ✅ behoben

**Datei:** `src/web.py`, Route `GET /`
**Problem:** `/?top=9999999` würde alle Rows der DB laden und rendern. `/?top=0` liefert eine leere Tabelle ohne Hinweis.
**Lösung:** `top = max(1, min(top, 500))` — Clamp auf 1–500.

---

## 11. God Function `run()` ✅ behoben

**Datei:** `scripts/run_pipeline.py`
**Problem:** Die `run()`-Funktion war ca. 130 Zeilen lang und führte 5 Phasen aus: E-Mail-Abruf, Scraping, DB-Speichern, Matching/Scoring, Ausgabe. Keine Phase war einzeln testbar.
**Lösung:** Jede Phase in eine eigene Funktion ausgelagert: `_phase_fetch_emails()`, `_phase_scrape()`, `_phase_save_to_db()`, `_phase_match_and_score()`. `run()` orchestriert nur noch.

---

## 12. Sinnlose Test-Assertion `>= 0` ✅ behoben

**Datei:** `tests/test_matcher.py`, `TestMatchSkills.test_fuzzy_match()`
**Problem:** `assert len(matched) >= 0` ist für jede Liste immer `True`. Der Kommentar "Mindestens einer sollte fuzzy matchen" war nicht implementiert.
**Lösung:** Assertion durch `assert not_crashed` Kommentar + tatsächliche Prüfung ersetzt: Fuzzy-Matching auf bekannte Kandidaten geprüft.

---

## 13. Inkonsistentes Rollback-Pattern ✅ behoben

**Datei:** `scripts/run_pipeline.py`, `rank()`-Kommando
**Problem:** `run()` hatte explizites `session.rollback()` im `except`-Block, `rank()` nicht. Zwar rollt SQLAlchemy beim `close()` implizit zurück, aber das Muster war inkonsistent.
**Lösung:** `rank()` hat jetzt dasselbe explizite Rollback-Pattern wie `run()`.
