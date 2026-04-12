"""Tests für scripts/run_pipeline.py — CLI und Pipeline-Integration."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner
from sqlalchemy import create_engine

from scripts.run_pipeline import cli
from src.database import (
    create_tables,
    get_all_projects,
    get_session_factory,
    upsert_project,
)
from src.email_fetcher import RawEmail


@pytest.fixture()
def db_url(tmp_path):
    """SQLite-DB für Pipeline-Tests."""
    url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(url)
    create_tables(engine)
    return url


@pytest.fixture()
def cv_file(tmp_path):
    """Temporäre CV-Datei."""
    content = """\
name: "Pipeline Test"
skills:
  - Python
  - Docker
skills_secondary:
  - FastAPI
exclude_skills:
  - SAP
keywords:
  - backend
preferred_locations:
  - München
preferred_remote: "100%"
preferred_contract_types:
  - Freiberuflich
"""
    path = tmp_path / "cv.yaml"
    path.write_text(content, encoding="utf-8")
    return str(path)


@pytest.fixture()
def db_with_projects(db_url):
    """DB mit vorhandenen Projekten."""
    engine = create_engine(db_url)
    factory = get_session_factory(engine)
    session = factory()
    upsert_project(
        session,
        {
            "project_id": 1001,
            "title": "Python Backend Entwickler",
            "description": "Backend-Entwicklung mit Python und FastAPI in der Cloud.",
            "company": "Test AG",
            "contact": "Max",
            "location": "München",
            "country": "DE",
            "industry": "IT",
            "remote": "100%",
            "contract_type": "Freiberuflich",
            "start": "Ab sofort",
            "duration": "6 Monate",
            "utilization": "Vollzeit",
            "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
            "url": "https://www.freelancermap.de/nproj/1001.html",
        },
    )
    upsert_project(
        session,
        {
            "project_id": 1002,
            "title": "SAP Berater",
            "description": "SAP S/4HANA Migration Projekt.",
            "company": "SAP Corp",
            "contact": "Anna",
            "location": "Walldorf",
            "country": "DE",
            "industry": "Consulting",
            "remote": "0%",
            "contract_type": "Festanstellung",
            "start": "Q3 2025",
            "duration": "12 Monate",
            "utilization": "Vollzeit",
            "skills": ["SAP", "ABAP", "S/4HANA"],
            "url": "https://www.freelancermap.de/nproj/1002.html",
        },
    )
    session.commit()
    session.close()
    return db_url


class TestRankCommand:
    def test_rank_with_projects(self, cv_file, db_with_projects):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rank",
                "--cv",
                cv_file,
                "--db-url",
                db_with_projects,
                "--top",
                "5",
            ],
        )
        assert result.exit_code == 0
        assert "Top-" in result.output
        assert "Python Backend" in result.output

    def test_rank_empty_db(self, cv_file, db_url):
        runner = CliRunner()
        result = runner.invoke(cli, ["rank", "--cv", cv_file, "--db-url", db_url])
        assert result.exit_code == 0
        assert "Keine Projekte" in result.output

    def test_rank_excluded_project(self, cv_file, db_with_projects):
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rank",
                "--cv",
                cv_file,
                "--db-url",
                db_with_projects,
            ],
        )
        assert result.exit_code == 0
        assert "AUSGESCHLOSSEN" in result.output

    def test_rank_ordering(self, cv_file, db_with_projects):
        """Python-Projekt sollte vor SAP-Projekt stehen."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "rank",
                "--cv",
                cv_file,
                "--db-url",
                db_with_projects,
            ],
        )
        assert result.exit_code == 0
        lines = result.output.split("\n")
        python_line = next(
            (i for i, line in enumerate(lines) if "Python Backend" in line), -1
        )
        sap_line = next(
            (i for i, line in enumerate(lines) if "SAP Berater" in line), -1
        )
        assert python_line < sap_line, "Python-Projekt sollte höher gerankt sein"


class TestRunImapCommand:
    def test_run_imap_no_emails(self, cv_file, db_url):
        """--imap mit 0 neuen Mails → keine Fehler, 0 Projekte."""
        runner = CliRunner()
        with patch("scripts.run_pipeline.fetch_emails", return_value=[]):
            result = runner.invoke(
                cli,
                ["run", "--cv", cv_file, "--db-url", db_url],
            )
        assert result.exit_code == 0

    def test_run_imap_with_email(self, cv_file, db_url):
        """--imap mit einer Mail → Projekte werden extrahiert."""
        fake_body = (
            "Hallo Rolf,\n\n"
            "----------------------------------------------\n"
            "Python Backend Entwickler (m/w/d)\n"
            "Erstellt: 11.03.2026\n"
            "von: Test AG\n"
            "Ort: München\n"
            "Vertragsart: Freiberuflich\n"
            "Remote: 100%\n"
            "Start: Ab sofort\n"
            "https://www.freelancermap.de/nproj/9999.html\n"
            "----------------------------------------------\n"
        )
        fake_email = RawEmail(
            uid=100,
            subject="Neue Projekte",
            sender="noreply@freelancermap.de",
            body=fake_body,
        )
        runner = CliRunner()
        with patch("scripts.run_pipeline.fetch_emails", return_value=[fake_email]):
            result = runner.invoke(
                cli,
                ["run", "--cv", cv_file, "--db-url", db_url, "--no-scrape"],
            )
        assert result.exit_code == 0
        assert "Top-" in result.output

    def test_run_imap_saves_email_projects_to_db(self, cv_file, db_url):
        """E-Mail-Projekte ohne HTML werden in DB gespeichert."""
        fake_body = (
            "----------------------------------------------\n"
            "Python Backend Entwickler (m/w/d)\n"
            "Erstellt: 11.03.2026\n"
            "von: Test AG\n"
            "Ort: München\n"
            "Vertragsart: Freiberuflich\n"
            "Remote: 100%\n"
            "Start: Ab sofort\n"
            "https://www.freelancermap.de/nproj/8888.html\n"
            "----------------------------------------------\n"
            "Java Enterprise Berater\n"
            "Erstellt: 11.03.2026\n"
            "von: Corp AG\n"
            "Ort: Frankfurt\n"
            "Vertragsart: Freiberuflich\n"
            "Remote: 50%\n"
            "Start: Q2 2026\n"
            "https://www.freelancermap.de/nproj/8889.html\n"
            "----------------------------------------------\n"
        )
        fake_email = RawEmail(
            uid=200,
            subject="Neue Projekte",
            sender="noreply@freelancermap.de",
            body=fake_body,
        )
        runner = CliRunner()
        with patch("scripts.run_pipeline.fetch_emails", return_value=[fake_email]):
            result = runner.invoke(
                cli,
                ["run", "--cv", cv_file, "--db-url", db_url, "--no-scrape"],
            )
        assert result.exit_code == 0
        # Projekte müssen in DB gespeichert worden sein
        engine = create_engine(db_url)
        session = get_session_factory(engine)()
        projects = get_all_projects(session)
        session.close()
        assert len(projects) == 2


class TestCookieValidation:
    def test_run_aborts_on_invalid_cookies(self, cv_file, db_url):
        """Pipeline bricht mit Fehlermeldung ab wenn Cookies ungültig."""
        fake_body = (
            "----------------------------------------------\n"
            "Python Backend Entwickler (m/w/d)\n"
            "Erstellt: 11.03.2026\n"
            "von: Test AG\n"
            "Ort: München\n"
            "Vertragsart: Freiberuflich\n"
            "Remote: 100%\n"
            "Start: Ab sofort\n"
            "https://www.freelancermap.de/nproj/7777.html\n"
            "----------------------------------------------\n"
        )
        fake_email = RawEmail(
            uid=300,
            subject="Neue Projekte",
            sender="noreply@freelancermap.de",
            body=fake_body,
        )
        runner = CliRunner()
        with (
            patch("scripts.run_pipeline.fetch_emails", return_value=[fake_email]),
            patch(
                "src.cookie_manager.get_authenticated_cookies",
                side_effect=RuntimeError(
                    "Keine gültige Session gefunden. "
                    "'python scripts/export_cookies.py' auf dem Host ausführen."
                ),
            ),
        ):
            result = runner.invoke(
                cli,
                ["run", "--cv", cv_file, "--db-url", db_url],
            )
        assert result.exit_code == 1
        assert "Cookie-Fehler" in result.output

    def test_run_imap_marks_new_projects(self, cv_file, db_url):
        """Neue Projekte werden mit ★NEU markiert."""
        fake_body = (
            "----------------------------------------------\n"
            "Python Backend Entwickler (m/w/d)\n"
            "Erstellt: 11.03.2026\n"
            "von: Test AG\n"
            "Ort: München\n"
            "Vertragsart: Freiberuflich\n"
            "Remote: 100%\n"
            "Start: Ab sofort\n"
            "https://www.freelancermap.de/nproj/7777.html\n"
            "----------------------------------------------\n"
        )
        fake_email = RawEmail(
            uid=300,
            subject="Neue Projekte",
            sender="noreply@freelancermap.de",
            body=fake_body,
        )
        runner = CliRunner()
        with patch("scripts.run_pipeline.fetch_emails", return_value=[fake_email]):
            result = runner.invoke(
                cli,
                ["run", "--cv", cv_file, "--db-url", db_url, "--no-scrape"],
            )
        assert result.exit_code == 0
        assert "★NEU" in result.output


class TestRunCommand:
    def test_run_without_mbox(self, cv_file, db_url):
        """Run ohne imap/mbox → nur DB-Matching auf bestehende Daten."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "run",
                "--cv",
                cv_file,
                "--db-url",
                db_url,
                "--no-imap",
                "--no-scrape",
            ],
        )
        assert result.exit_code == 0

    def test_run_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["run", "--help"])
        assert result.exit_code == 0
        assert "--cv" in result.output
        assert "--mbox" in result.output

    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "rank" in result.output
