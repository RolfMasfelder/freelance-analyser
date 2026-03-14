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
    func,
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
    first_seen = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class MatchResult(Base):
    """Ergebnis des CV-Matchings für ein Projekt."""

    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False, index=True)
    score = Column(Float, nullable=False, default=0.0)
    matched_skills = Column(JSON, nullable=False, default=list)
    missing_skills = Column(JSON, nullable=False, default=list)
    notes = Column(Text, nullable=False, default="")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


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


def ensure_project_exists(session: Session, project_data: dict) -> tuple[Project, bool]:
    """Stellt sicher, dass ein Projekt in der DB existiert.

    Für neue Projekte: Anlegen mit den übergebenen Daten.
    Für bestehende Projekte: Nur last_seen aktualisieren (keine Daten überschreiben).

    Returns:
        Tuple aus (Project, is_new).
    """
    project_id = project_data["project_id"]
    now = datetime.now(timezone.utc)

    existing = session.get(Project, project_id)
    if existing:
        existing.last_seen = now
        logger.debug("Projekt %d existiert bereits, last_seen aktualisiert", project_id)
        return existing, False

    project = Project(**project_data, first_seen=now, last_seen=now)
    session.add(project)
    logger.debug("Projekt %d neu angelegt (aus E-Mail)", project_id)
    return project, True


def upsert_projects(session: Session, projects: list[dict]) -> list[Project]:
    """Speichert mehrere Projekte (Batch-Upsert).

    Lädt alle betroffenen Projekte in einem Query, um N+1-Queries zu vermeiden.
    """
    if not projects:
        return []
    ids = [p["project_id"] for p in projects]
    existing_map = {
        p.project_id: p
        for p in session.query(Project).filter(Project.project_id.in_(ids)).all()
    }
    now = datetime.now(timezone.utc)
    results = []
    for project_data in projects:
        pid = project_data["project_id"]
        if pid in existing_map:
            proj = existing_map[pid]
            for key, value in project_data.items():
                if key != "project_id":
                    setattr(proj, key, value)
            proj.last_seen = now
        else:
            proj = Project(**project_data, first_seen=now, last_seen=now)
            session.add(proj)
        results.append(proj)
    session.flush()
    return results


def save_match_result(
    session: Session,
    project_id: int,
    score: float,
    matched_skills: list[str],
    missing_skills: list[str],
    notes: str = "",
) -> MatchResult:
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
    """Holt die Top-N Match-Ergebnisse nach Score, je Projekt nur das neueste."""
    subq = (
        session.query(func.max(MatchResult.id).label("max_id"))
        .group_by(MatchResult.project_id)
        .subquery()
    )
    return list(
        session.query(MatchResult)
        .join(subq, MatchResult.id == subq.c.max_id)
        .order_by(MatchResult.score.desc())
        .limit(limit)
        .all()
    )
