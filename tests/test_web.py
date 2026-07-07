"""Tests für src/web.py — FastAPI Web-UI."""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import MatchResult, Project, ProjectStatus, create_tables
from src.letter_generator import LetterResult
from src.web import app, get_db

SAMPLE_PROJECT = {
    "project_id": 1001,
    "title": "Senior Python Entwickler",
    "description": "Entwicklung einer Microservice-Architektur",
    "company": "Test GmbH",
    "contact": "",
    "location": "München",
    "country": "Deutschland",
    "industry": "IT",
    "remote": "100%",
    "contract_type": "Freiberuflich",
    "start": "sofort",
    "duration": "6 Monate",
    "utilization": "100%",
    "skills": ["Python", "FastAPI", "Docker"],
    "url": "https://www.freelancermap.de/projektmarkt/detail/1001",
}


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_tables(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _add_project_with_match(session, score: float = 75.0) -> Project:
    proj = Project(
        **SAMPLE_PROJECT, first_seen=datetime.now(UTC), last_seen=datetime.now(UTC)
    )
    session.add(proj)
    session.flush()
    match = MatchResult(
        project_id=SAMPLE_PROJECT["project_id"],
        score=score,
        matched_skills=["Python", "Docker"],
        missing_skills=["Kubernetes"],
        notes="",
        created_at=datetime.now(UTC),
    )
    session.add(match)
    session.commit()
    return proj


def _wait_for_job(client, project_id: int, job_id: str, timeout: float = 2.0) -> dict:
    """Pollt den Job-Status, bis er nicht mehr 'pending' ist (Hintergrund-Thread)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/project/{project_id}/letter/status/{job_id}")
        job = response.json()
        if job["status"] != "pending":
            return job
        time.sleep(0.02)
    raise AssertionError("Job wurde nicht rechtzeitig fertig")


class TestRankingPage:
    def test_empty_db_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_empty_db_shows_hint(self, client):
        response = client.get("/")
        assert "run_pipeline.py" in response.text

    def test_with_data_shows_project(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/")
        assert response.status_code == 200
        assert "Senior Python Entwickler" in response.text

    def test_score_is_displayed(self, client, db_session):
        _add_project_with_match(db_session, score=75.0)
        response = client.get("/")
        assert "75.0" in response.text

    def test_top_param_accepted(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/?top=10")
        assert response.status_code == 200

    def test_matched_skills_shown(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/")
        assert "Python" in response.text


class TestProjectDetailPage:
    def test_existing_project_returns_200(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/project/1001")
        assert response.status_code == 200

    def test_nonexistent_project_returns_404(self, client):
        response = client.get("/project/9999")
        assert response.status_code == 404

    def test_project_details_shown(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/project/1001")
        assert "Senior Python Entwickler" in response.text
        assert "München" in response.text
        assert "Test GmbH" in response.text

    def test_matched_skills_shown(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/project/1001")
        assert "Python" in response.text
        assert "Docker" in response.text

    def test_missing_skills_shown(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/project/1001")
        assert "Kubernetes" in response.text

    def test_back_link_present(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/project/1001")
        assert 'href="/"' in response.text

    def test_project_without_match_shows_warning(self, client, db_session):
        proj = Project(
            **SAMPLE_PROJECT, first_seen=datetime.now(UTC), last_seen=datetime.now(UTC)
        )
        db_session.add(proj)
        db_session.commit()
        response = client.get("/project/1001")
        assert response.status_code == 200
        assert "Kein Match-Ergebnis" in response.text

    def test_generate_letter_button_shown(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/project/1001")
        assert "Antwortschreiben generieren" in response.text


class TestLetterGeneration:
    @patch("src.web.generate_letter")
    @patch("src.web.load_cv")
    def test_start_returns_job_id(self, mock_cv, mock_gen, client, db_session):
        _add_project_with_match(db_session)
        mock_cv.return_value = MagicMock()
        mock_gen.return_value = LetterResult(
            letter="Sehr geehrte Damen und Herren...",
            model="llama3.1:8b",
        )
        response = client.post("/project/1001/letter/start")
        assert response.status_code == 200
        assert "job_id" in response.json()

    @patch("src.web.generate_letter")
    @patch("src.web.load_cv")
    def test_status_shows_completed_letter(self, mock_cv, mock_gen, client, db_session):
        _add_project_with_match(db_session)
        mock_cv.return_value = MagicMock()
        mock_gen.return_value = LetterResult(
            letter="Sehr geehrte Damen und Herren...",
            model="llama3.1:8b",
        )
        job_id = client.post("/project/1001/letter/start").json()["job_id"]
        job = _wait_for_job(client, 1001, job_id)
        assert job["status"] == "done"
        assert "Sehr geehrte Damen und Herren" in job["letter"]

    @patch("src.web.generate_letter")
    @patch("src.web.load_cv")
    def test_status_shows_model(self, mock_cv, mock_gen, client, db_session):
        _add_project_with_match(db_session)
        mock_cv.return_value = MagicMock()
        mock_gen.return_value = LetterResult(letter="Text", model="test-model")
        job_id = client.post("/project/1001/letter/start").json()["job_id"]
        job = _wait_for_job(client, 1001, job_id)
        assert job["model"] == "test-model"

    @patch(
        "src.web.generate_letter", side_effect=ConnectionError("LLM nicht erreichbar")
    )
    @patch("src.web.load_cv")
    def test_status_shows_error(self, mock_cv, mock_gen, client, db_session):
        _add_project_with_match(db_session)
        mock_cv.return_value = MagicMock()
        job_id = client.post("/project/1001/letter/start").json()["job_id"]
        job = _wait_for_job(client, 1001, job_id)
        assert job["status"] == "error"
        assert "LLM nicht erreichbar" in job["error"]

    def test_start_nonexistent_project(self, client):
        response = client.post("/project/9999/letter/start")
        assert response.status_code == 404

    def test_status_unknown_job(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/project/1001/letter/status/unknown-job-id")
        assert response.status_code == 404


class TestProjectStatus:
    def test_status_badge_shown_in_ranking(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/")
        assert "neu" in response.text

    def test_status_dropdown_shown_in_detail(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/project/1001")
        assert 'name="status"' in response.text

    def test_update_status(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.post(
            "/project/1001/status",
            data={"status": "beworben"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        proj = db_session.get(Project, 1001)
        assert proj.status == ProjectStatus.beworben

    def test_update_status_invalid(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.post(
            "/project/1001/status",
            data={"status": "ungueltig"},
        )
        assert response.status_code == 400

    def test_update_status_nonexistent_project(self, client, db_session):
        response = client.post(
            "/project/9999/status",
            data={"status": "gesehen"},
        )
        assert response.status_code == 404


class TestAgeFilter:
    def test_old_projects_hidden_by_default(self, client, db_session):
        """Projekte älter als 30 Tage werden standardmäßig ausgeblendet."""
        old_date = datetime.now(UTC) - timedelta(days=45)
        proj = Project(**SAMPLE_PROJECT, first_seen=old_date, last_seen=old_date)
        db_session.add(proj)
        db_session.flush()
        match = MatchResult(
            project_id=SAMPLE_PROJECT["project_id"],
            score=80.0,
            matched_skills=["Python"],
            missing_skills=[],
            notes="",
            created_at=datetime.now(UTC),
        )
        db_session.add(match)
        db_session.commit()
        response = client.get("/")
        assert response.status_code == 200
        assert "Senior Python Entwickler" not in response.text

    def test_old_projects_shown_with_filter(self, client, db_session):
        """Alte Projekte werden mit include_old=true angezeigt."""
        old_date = datetime.now(UTC) - timedelta(days=45)
        proj = Project(**SAMPLE_PROJECT, first_seen=old_date, last_seen=old_date)
        db_session.add(proj)
        db_session.flush()
        match = MatchResult(
            project_id=SAMPLE_PROJECT["project_id"],
            score=80.0,
            matched_skills=["Python"],
            missing_skills=[],
            notes="",
            created_at=datetime.now(UTC),
        )
        db_session.add(match)
        db_session.commit()
        response = client.get("/?include_old=true")
        assert response.status_code == 200
        assert "Senior Python Entwickler" in response.text

    def test_recent_projects_always_shown(self, client, db_session):
        """Aktuelle Projekte werden immer angezeigt."""
        _add_project_with_match(db_session)
        response = client.get("/")
        assert "Senior Python Entwickler" in response.text

    def test_filter_toggle_button_present(self, client, db_session):
        response = client.get("/")
        assert "include_old=true" in response.text

    def test_old_first_seen_recent_last_seen_shown(self, client, db_session):
        """Projekte mit altem first_seen aber aktuellem last_seen werden angezeigt."""
        old_date = datetime.now(UTC) - timedelta(days=45)
        proj = Project(
            **SAMPLE_PROJECT, first_seen=old_date, last_seen=datetime.now(UTC)
        )
        db_session.add(proj)
        db_session.flush()
        match = MatchResult(
            project_id=SAMPLE_PROJECT["project_id"],
            score=80.0,
            matched_skills=["Python"],
            missing_skills=[],
            notes="",
            created_at=datetime.now(UTC),
        )
        db_session.add(match)
        db_session.commit()
        response = client.get("/")
        assert response.status_code == 200
        assert "Senior Python Entwickler" in response.text

    def test_last_week_hides_projects_older_than_7_days(self, client, db_session):
        """Mit last_week=true werden Projekte älter als 7 Tage ausgeblendet."""
        old_date = datetime.now(UTC) - timedelta(days=10)
        proj = Project(**SAMPLE_PROJECT, first_seen=old_date, last_seen=old_date)
        db_session.add(proj)
        db_session.flush()
        match = MatchResult(
            project_id=SAMPLE_PROJECT["project_id"],
            score=80.0,
            matched_skills=["Python"],
            missing_skills=[],
            notes="",
            created_at=datetime.now(UTC),
        )
        db_session.add(match)
        db_session.commit()
        response = client.get("/?last_week=true")
        assert response.status_code == 200
        assert "Senior Python Entwickler" not in response.text

    def test_last_week_shows_recent_projects(self, client, db_session):
        """Mit last_week=true werden Projekte der letzten 7 Tage angezeigt."""
        _add_project_with_match(db_session)
        response = client.get("/?last_week=true")
        assert response.status_code == 200
        assert "Senior Python Entwickler" in response.text

    def test_last_week_toggle_button_present(self, client, db_session):
        response = client.get("/")
        assert "last_week=true" in response.text

    def test_last_week_overrides_include_old(self, client, db_session):
        """last_week=true schränkt auch dann auf 7 Tage ein, wenn include_old gesetzt ist."""
        old_date = datetime.now(UTC) - timedelta(days=45)
        proj = Project(**SAMPLE_PROJECT, first_seen=old_date, last_seen=old_date)
        db_session.add(proj)
        db_session.flush()
        match = MatchResult(
            project_id=SAMPLE_PROJECT["project_id"],
            score=80.0,
            matched_skills=["Python"],
            missing_skills=[],
            notes="",
            created_at=datetime.now(UTC),
        )
        db_session.add(match)
        db_session.commit()
        response = client.get("/?include_old=true&last_week=true")
        assert response.status_code == 200
        assert "Senior Python Entwickler" not in response.text


class TestStatusFilter:
    def test_default_shows_only_neu(self, client, db_session):
        """Default-Filter zeigt nur Projekte mit Status 'neu'."""
        _add_project_with_match(db_session)
        proj = db_session.get(Project, SAMPLE_PROJECT["project_id"])
        proj.status = ProjectStatus.gesehen
        db_session.commit()
        response = client.get("/")
        assert "Senior Python Entwickler" not in response.text

    def test_default_shows_neu_projects(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/")
        assert "Senior Python Entwickler" in response.text

    def test_filter_gesehen(self, client, db_session):
        _add_project_with_match(db_session)
        proj = db_session.get(Project, SAMPLE_PROJECT["project_id"])
        proj.status = ProjectStatus.gesehen
        db_session.commit()
        response = client.get("/?status=gesehen")
        assert "Senior Python Entwickler" in response.text

    def test_filter_abgelehnt_hides_from_default(self, client, db_session):
        _add_project_with_match(db_session)
        proj = db_session.get(Project, SAMPLE_PROJECT["project_id"])
        proj.status = ProjectStatus.abgelehnt
        db_session.commit()
        response = client.get("/")
        assert "Senior Python Entwickler" not in response.text

    def test_filter_alle_shows_all(self, client, db_session):
        _add_project_with_match(db_session)
        proj = db_session.get(Project, SAMPLE_PROJECT["project_id"])
        proj.status = ProjectStatus.abgelehnt
        db_session.commit()
        response = client.get("/?status=alle")
        assert "Senior Python Entwickler" in response.text

    def test_status_buttons_present(self, client, db_session):
        response = client.get("/")
        assert "status=alle" in response.text
        assert "status=neu" in response.text
        assert "status=abgelehnt" in response.text

    def test_invalid_status_ignored(self, client, db_session):
        _add_project_with_match(db_session)
        response = client.get("/?status=ungueltig")
        assert response.status_code == 200
