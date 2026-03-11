"""Datenbankzugriff — SQLAlchemy-Models und CRUD-Operationen."""

import logging
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Project(Base):
    """Projekt aus freelancermap."""

    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    company = Column(String(300), nullable=False, default="")
    contact = Column(String(300), nullable=False, default="")
    location = Column(String(300), nullable=False, default="")
    country = Column(String(100), nullable=False, default="")
    industry = Column(String(300), nullable=False, default="")
    remote = Column(String(100), nullable=False, default="")
    contract_type = Column(String(100), nullable=False, default="")
    start = Column(String(100), nullable=False, default="")
    duration = Column(String(100), nullable=False, default="")
    utilization = Column(String(100), nullable=False, default="")
    skills = Column(JSON, nullable=False, default=list)
    url = Column(String(500), nullable=False, default="")
    first_seen = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class MatchResult(Base):
    """Ergebnis des CV-Matchings für ein Projekt."""

    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False, index=True)
    score = Column(Float, nullable=False, default=0.0)
    matched_skills = Column(JSON, nullable=False, default=list)
    missing_skills = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


def get_engine(database_url: str):
    """Erstellt eine SQLAlchemy-Engine."""
    return create_engine(database_url)


def get_session_factory(engine) -> sessionmaker:
    """Erstellt eine Session-Factory."""
    return sessionmaker(bind=engine)


def create_tables(engine):
    """Erstellt alle Tabellen (idempotent)."""
    Base.metadata.create_all(engine)


def upsert_project(session: Session, project_data: dict) -> Project:
    """Speichert ein Projekt (Insert oder Update bei gleicher project_id).

    Args:
        session: Aktive DB-Session.
        project_data: Dict mit Projektfeldern (wie ProjectDetail.__dict__).

    Returns:
        Das gespeicherte Project-Objekt.
    """
    project_id = project_data["project_id"]
    now = datetime.now(timezone.utc)

    existing = session.get(Project, project_id)
    if existing:
        for key, value in project_data.items():
            if key != "project_id":
                setattr(existing, key, value)
        existing.last_seen = now
        logger.debug("Projekt %d aktualisiert", project_id)
        return existing

    project = Project(**project_data, first_seen=now, last_seen=now)
    session.add(project)
    logger.debug("Projekt %d neu angelegt", project_id)
    return project


def upsert_projects(session: Session, projects: list[dict]) -> list[Project]:
    """Speichert mehrere Projekte (Batch-Upsert).

    Args:
        session: Aktive DB-Session.
        projects: Liste von Projekt-Dicts.

    Returns:
        Liste der gespeicherten Project-Objekte.
    """
    results = []
    for project_data in projects:
        results.append(upsert_project(session, project_data))
    session.flush()
    return results


def save_match_result(session: Session, project_id: int, score: float,
                      matched_skills: list[str], missing_skills: list[str],
                      notes: str = "") -> MatchResult:
    """Speichert ein Match-Ergebnis."""
    result = MatchResult(
        project_id=project_id,
        score=score,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        notes=notes,
    )
    session.add(result)
    return result


def get_project(session: Session, project_id: int) -> Project | None:
    """Holt ein Projekt anhand der ID."""
    return session.get(Project, project_id)


def get_all_projects(session: Session) -> list[Project]:
    """Holt alle Projekte."""
    return list(session.query(Project).order_by(Project.last_seen.desc()).all())


def get_match_results(session: Session, project_id: int) -> list[MatchResult]:
    """Holt alle Match-Ergebnisse für ein Projekt."""
    return list(
        session.query(MatchResult)
        .filter(MatchResult.project_id == project_id)
        .order_by(MatchResult.created_at.desc())
        .all()
    )


def get_top_matches(session: Session, limit: int = 20) -> list[MatchResult]:
    """Holt die Top-N Match-Ergebnisse nach Score."""
    return list(
        session.query(MatchResult)
        .order_by(MatchResult.score.desc())
        .limit(limit)
        .all()
    )
