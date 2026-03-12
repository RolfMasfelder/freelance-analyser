"""Tests für src/database.py — SQLAlchemy Models und CRUD."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import (
    create_tables,
    ensure_project_exists,
    get_all_projects,
    get_match_results,
    get_project,
    get_session_factory,
    get_top_matches,
    save_match_result,
    upsert_project,
    upsert_projects,
)


@pytest.fixture()
def engine():
    """SQLite In-Memory-Engine für Tests."""
    eng = create_engine("sqlite:///:memory:")
    create_tables(eng)
    return eng


@pytest.fixture()
def session(engine):
    """Frische DB-Session pro Test."""
    factory = get_session_factory(engine)
    sess = factory()
    yield sess
    sess.close()


SAMPLE_PROJECT = {
    "project_id": 123,
    "title": "Python-Entwickler gesucht",
    "description": "Wir suchen einen Python-Entwickler.",
    "company": "Test GmbH",
    "contact": "Max Mustermann",
    "location": "München",
    "country": "Deutschland",
    "industry": "IT",
    "remote": "100%",
    "contract_type": "Freiberuflich",
    "start": "Ab sofort",
    "duration": "6 Monate",
    "utilization": "Vollzeit",
    "skills": ["Python", "Django", "PostgreSQL"],
    "url": "https://www.freelancermap.de/nproj/123.html",
}


class TestProject:
    def test_insert_project(self, session: Session):
        proj = upsert_project(session, SAMPLE_PROJECT)
        session.commit()
        assert proj.project_id == 123
        assert proj.title == "Python-Entwickler gesucht"
        assert proj.skills == ["Python", "Django", "PostgreSQL"]
        assert proj.first_seen is not None
        assert proj.last_seen is not None

    def test_update_project(self, session: Session):
        upsert_project(session, SAMPLE_PROJECT)
        session.commit()

        updated = {**SAMPLE_PROJECT, "title": "Senior Python-Entwickler"}
        proj = upsert_project(session, updated)
        session.commit()
        assert proj.title == "Senior Python-Entwickler"
        assert proj.project_id == 123

    def test_upsert_preserves_first_seen(self, session: Session):
        proj1 = upsert_project(session, SAMPLE_PROJECT)
        session.commit()
        first_seen = proj1.first_seen

        updated = {**SAMPLE_PROJECT, "title": "Neuer Titel"}
        proj2 = upsert_project(session, updated)
        session.commit()
        assert proj2.first_seen == first_seen

    def test_get_project(self, session: Session):
        upsert_project(session, SAMPLE_PROJECT)
        session.commit()

        proj = get_project(session, 123)
        assert proj is not None
        assert proj.title == "Python-Entwickler gesucht"

    def test_get_project_not_found(self, session: Session):
        assert get_project(session, 999) is None

    def test_get_all_projects(self, session: Session):
        upsert_project(session, SAMPLE_PROJECT)
        proj2 = {**SAMPLE_PROJECT, "project_id": 456, "title": "Java-Entwickler"}
        upsert_project(session, proj2)
        session.commit()

        projects = get_all_projects(session)
        assert len(projects) == 2

    def test_upsert_projects_batch(self, session: Session):
        projects = [
            SAMPLE_PROJECT,
            {**SAMPLE_PROJECT, "project_id": 456, "title": "Java"},
            {**SAMPLE_PROJECT, "project_id": 789, "title": "Go"},
        ]
        results = upsert_projects(session, projects)
        session.commit()
        assert len(results) == 3
        assert len(get_all_projects(session)) == 3


SAMPLE_EMAIL_PROJECT = {
    "project_id": 555,
    "title": "React Frontend Dev",
    "company": "Web GmbH",
    "location": "Berlin",
    "contract_type": "Freiberuflich",
    "remote": "50%",
    "start": "Ab sofort",
    "url": "https://www.freelancermap.de/nproj/555.html",
}


class TestEnsureProjectExists:
    def test_creates_new_project(self, session: Session):
        proj, is_new = ensure_project_exists(session, SAMPLE_EMAIL_PROJECT)
        session.commit()
        assert is_new is True
        assert proj.project_id == 555
        assert proj.title == "React Frontend Dev"
        assert proj.first_seen is not None
        assert proj.description == ""  # default für fehlende Felder

    def test_existing_project_not_overwritten(self, session: Session):
        """Bestehende Projekte behalten ihre Daten, nur last_seen wird aktualisiert."""
        upsert_project(session, SAMPLE_PROJECT)
        session.commit()
        original = get_project(session, 123)
        original_last_seen = original.last_seen

        email_data = {
            "project_id": 123,
            "title": "Anderer Titel",
            "company": "Andere Firma",
            "location": "Berlin",
            "contract_type": "",
            "remote": "",
            "start": "",
            "url": "",
        }
        proj, is_new = ensure_project_exists(session, email_data)
        session.commit()

        assert is_new is False
        # Originaldaten bleiben erhalten
        assert proj.title == "Python-Entwickler gesucht"
        assert proj.description == "Wir suchen einen Python-Entwickler."
        assert proj.skills == ["Python", "Django", "PostgreSQL"]
        assert proj.last_seen >= original_last_seen

    def test_new_then_upsert_enriches(self, session: Session):
        """E-Mail-Projekt anlegen, dann mit gescrapten Details updaten."""
        ensure_project_exists(session, SAMPLE_EMAIL_PROJECT)
        session.flush()

        # Scraped detail mit mehr Daten
        upsert_project(
            session,
            {
                **SAMPLE_EMAIL_PROJECT,
                "description": "Detaillierte Beschreibung",
                "contact": "Anna",
                "country": "DE",
                "industry": "IT",
                "duration": "3 Monate",
                "utilization": "Vollzeit",
                "skills": ["React", "TypeScript"],
            },
        )
        session.commit()

        proj = get_project(session, 555)
        assert proj.description == "Detaillierte Beschreibung"
        assert proj.skills == ["React", "TypeScript"]
        assert proj.title == "React Frontend Dev"


class TestMatchResult:
    def test_save_match_result(self, session: Session):
        result = save_match_result(
            session,
            project_id=123,
            score=85.5,
            matched_skills=["Python", "Django"],
            missing_skills=["React"],
            notes="Guter Match",
        )
        session.commit()
        assert result.id is not None
        assert result.score == 85.5
        assert result.matched_skills == ["Python", "Django"]

    def test_get_match_results(self, session: Session):
        save_match_result(session, 123, 85.0, ["Python"], [], "")
        save_match_result(session, 123, 70.0, ["Django"], ["React"], "")
        session.commit()

        results = get_match_results(session, 123)
        assert len(results) == 2

    def test_get_top_matches(self, session: Session):
        save_match_result(session, 1, 90.0, [], [], "")
        save_match_result(session, 2, 50.0, [], [], "")
        save_match_result(session, 3, 75.0, [], [], "")
        session.commit()

        top = get_top_matches(session, limit=2)
        assert len(top) == 2
        assert top[0].score == 90.0
        assert top[1].score == 75.0

    def test_get_match_results_empty(self, session: Session):
        assert get_match_results(session, 999) == []


class TestIntegration:
    """Integration: Projekt + Match zusammen."""

    def test_project_with_match(self, session: Session):
        upsert_project(session, SAMPLE_PROJECT)
        save_match_result(
            session, 123, 92.0, ["Python", "PostgreSQL"], ["Django"], "Top-Match"
        )
        session.commit()

        proj = get_project(session, 123)
        assert proj is not None
        matches = get_match_results(session, 123)
        assert len(matches) == 1
        assert matches[0].score == 92.0
