"""Web-UI — FastAPI-App für Projektrankings (FastAPI + Jinja2)."""

import functools
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import Settings
from src.cv_manager import load_cv
from src.database import MatchResult, Project, get_engine, get_session_factory
from src.letter_generator import generate_letter

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@functools.lru_cache(maxsize=1)
def _get_session_factory():
    settings = Settings()
    engine = get_engine(settings.database_url)
    return get_session_factory(engine)


def get_db():
    session = _get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@app.get("/", response_class=HTMLResponse)
async def ranking(request: Request, session: Session = Depends(get_db), top: int = 50):
    top = max(1, min(top, 500))
    subq = (
        session.query(func.max(MatchResult.id).label("max_id"))
        .group_by(MatchResult.project_id)
        .subquery()
    )
    results = (
        session.query(MatchResult, Project)
        .join(subq, MatchResult.id == subq.c.max_id)
        .join(Project, MatchResult.project_id == Project.project_id)
        .order_by(MatchResult.score.desc())
        .limit(top)
        .all()
    )
    return templates.TemplateResponse(
        "ranking.html",
        {"request": request, "results": results, "top": top},
    )


@app.get("/project/{project_id}", response_class=HTMLResponse)
async def project_detail(
    request: Request,
    project_id: int,
    session: Session = Depends(get_db),
):
    project = session.get(Project, project_id)
    if project is None:
        return HTMLResponse("<h1>Projekt nicht gefunden</h1>", status_code=404)
    match = (
        session.query(MatchResult)
        .filter(MatchResult.project_id == project_id)
        .order_by(MatchResult.created_at.desc())
        .first()
    )
    return templates.TemplateResponse(
        "project.html",
        {"request": request, "project": project, "match": match},
    )


log = logging.getLogger(__name__)


@app.post("/project/{project_id}/letter", response_class=HTMLResponse)
async def generate_project_letter(
    request: Request,
    project_id: int,
    session: Session = Depends(get_db),
):
    """Generiert ein Antwortschreiben per LLM für ein Projekt."""
    project = session.get(Project, project_id)
    if project is None:
        return HTMLResponse("<h1>Projekt nicht gefunden</h1>", status_code=404)

    match = (
        session.query(MatchResult)
        .filter(MatchResult.project_id == project_id)
        .order_by(MatchResult.created_at.desc())
        .first()
    )

    matched_skills = match.matched_skills if match else None
    error = None
    letter_result = None

    try:
        cv = load_cv()
        settings = Settings()
        letter_result = generate_letter(project, cv, matched_skills, settings)
    except Exception as exc:
        log.exception("Fehler bei Antwortschreiben-Generierung")
        error = str(exc)

    return templates.TemplateResponse(
        "project.html",
        {
            "request": request,
            "project": project,
            "match": match,
            "letter": letter_result.letter if letter_result else None,
            "letter_model": letter_result.model if letter_result else None,
            "letter_error": error,
        },
    )
