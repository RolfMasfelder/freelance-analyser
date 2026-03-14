"""Tests für src/web.py — FastAPI Web-UI."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import MatchResult, Project, create_tables
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
