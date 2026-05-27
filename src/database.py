"""Datenbankzugriff — SQLAlchemy-Models und CRUD-Operationen."""

import enum
import logging
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


class ProjectStatus(enum.Enum):
    """Status eines Projekts im Bearbeitungsprozess."""

    neu = "neu"
    gesehen = "gesehen"
    beworben = "beworben"
    abgelehnt = "abgelehnt"


class Base(DeclarativeBase):
    pass


class Project(Base):
    """Projekt aus freelancermap."""

    __tablename__ = "projects"

    project_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    company: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    contact: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    industry: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    remote: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    contract_type: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    start: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    duration: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    utilization: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="de")
    url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), nullable=False, default=ProjectStatus.neu
    )
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class MatchResult(Base):
    """Ergebnis des CV-Matchings für ein Projekt."""

    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matched_skills: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    missing_skills: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
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


def update_project_status(
    session: Session, project_id: int, status: ProjectStatus
) -> Project | None:
    """Aktualisiert den Status eines Projekts."""
    project = session.get(Project, project_id)
    if project:
        project.status = status
        logger.debug("Projekt %d Status → %s", project_id, status.value)
    return project


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
