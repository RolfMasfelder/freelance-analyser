"""Web-UI — FastAPI-App für Projektrankings (FastAPI + Jinja2)."""

import functools
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.config import Settings
from src.cv_manager import load_cv
from src.database import (
    MatchResult,
    Project,
    ProjectStatus,
    get_engine,
    get_session_factory,
    update_project_status,
)
from src.letter_generator import generate_letter

# uvicorn konfiguriert standardmäßig nur seine eigenen Logger ("uvicorn.*"),
# nicht den Root-Logger — ohne dies bleiben log.info()/log.debug() aus src.*
# unsichtbar, selbst wenn LOG_LEVEL=DEBUG in .env gesetzt ist.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

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
async def ranking(
    request: Request,
    session: Session = Depends(get_db),
    top: int = 50,
    include_old: bool = False,
    last_week: bool = False,
    status: str = "neu",
):
    top = max(1, min(top, 500))
    subq = (
        session.query(func.max(MatchResult.id).label("max_id"))
        .group_by(MatchResult.project_id)
        .subquery()
    )
    query = (
        session.query(MatchResult, Project)
        .join(subq, MatchResult.id == subq.c.max_id)
        .join(Project, MatchResult.project_id == Project.project_id)
    )
    if last_week:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        query = query.filter(Project.last_seen >= cutoff)
    elif not include_old:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        query = query.filter(Project.last_seen >= cutoff)
    if status != "alle":
        try:
            query = query.filter(Project.status == ProjectStatus(status))
        except ValueError:
            pass
    all_statuses = [s.value for s in ProjectStatus]
    results = query.order_by(MatchResult.score.desc()).limit(top).all()
    return templates.TemplateResponse(
        "ranking.html",
        {
            "request": request,
            "results": results,
            "top": top,
            "include_old": include_old,
            "last_week": last_week,
            "status": status,
            "all_statuses": all_statuses,
        },
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

# In-Memory Job-Store für laufende Antwortschreiben-Generierungen.
# Bewusst kein einzelner, mehrere Minuten offener HTTP-Request: NAT-Router/
# Firewalls kappen idle TCP-Verbindungen ohne Datenfluss oft nach wenigen
# Minuten stillschweigend, sodass der Browser nie eine Antwort bekommt,
# obwohl das LLM (und der Server) den Request längst fertig verarbeitet
# haben. Start-Request und Status-Polls bleiben dagegen jeweils kurz.
_letter_jobs: dict[str, dict] = {}
_letter_jobs_lock = threading.Lock()


def _project_snapshot(project: Project) -> SimpleNamespace:
    """Kopiert die von generate_letter() benötigten Felder aus `project`.

    Der Hintergrund-Thread darf nicht auf das ORM-Objekt selbst zugreifen:
    Dessen DB-Session wird kurz nach Rückgabe des Start-Requests geschlossen,
    wodurch alle Attribute "expired" werden und ein Zugriff aus einem
    anderen Thread einen DetachedInstanceError auslösen würde.
    """
    return SimpleNamespace(
        title=project.title,
        company=project.company,
        location=project.location,
        remote=project.remote,
        contract_type=project.contract_type,
        start=project.start,
        duration=project.duration,
        skills=list(project.skills) if project.skills else [],
        description=project.description,
        language=getattr(project, "language", "de"),
    )


@app.post("/project/{project_id}/letter/start")
def start_letter_generation(
    project_id: int,
    session: Session = Depends(get_db),
):
    """Startet die Antwortschreiben-Generierung als Hintergrund-Task und
    liefert sofort eine Job-ID zum Abfragen des Fortschritts zurück.
    """
    project = session.get(Project, project_id)
    if project is None:
        return JSONResponse({"error": "Projekt nicht gefunden"}, status_code=404)

    match = (
        session.query(MatchResult)
        .filter(MatchResult.project_id == project_id)
        .order_by(MatchResult.created_at.desc())
        .first()
    )
    matched_skills = match.matched_skills if match else None
    snapshot = _project_snapshot(project)

    job_id = uuid.uuid4().hex
    with _letter_jobs_lock:
        _letter_jobs[job_id] = {
            "status": "pending",
            "letter": None,
            "model": None,
            "error": None,
        }

    def _run_job() -> None:
        try:
            settings = Settings()
            cv = load_cv(settings.cv_path)
            result = generate_letter(snapshot, cv, matched_skills, settings)
            job = {
                "status": "done",
                "letter": result.letter,
                "model": result.model,
                "error": None,
            }
        except Exception as exc:
            log.exception("Fehler bei Antwortschreiben-Generierung (Job %s)", job_id)
            job = {"status": "error", "letter": None, "model": None, "error": str(exc)}
        with _letter_jobs_lock:
            _letter_jobs[job_id] = job

    threading.Thread(target=_run_job, daemon=True).start()
    return JSONResponse({"job_id": job_id})


@app.get("/project/{project_id}/letter/status/{job_id}")
def letter_generation_status(project_id: int, job_id: str):
    """Liefert den aktuellen Status eines Antwortschreiben-Jobs (Polling)."""
    with _letter_jobs_lock:
        job = _letter_jobs.get(job_id)
    if job is None:
        return JSONResponse({"error": "Unbekannter Job"}, status_code=404)
    return JSONResponse(job)


@app.post("/project/{project_id}/status", response_class=HTMLResponse)
async def update_status(
    request: Request,
    project_id: int,
    session: Session = Depends(get_db),
):
    """Aktualisiert den Status eines Projekts."""
    form = await request.form()
    status_value = form.get("status", "")
    try:
        new_status = ProjectStatus(status_value)
    except ValueError:
        return HTMLResponse("Ungültiger Status", status_code=400)

    project = update_project_status(session, project_id, new_status)
    if project is None:
        return HTMLResponse("Projekt nicht gefunden", status_code=404)
    session.commit()

    from starlette.responses import RedirectResponse

    return RedirectResponse(url=f"/project/{project_id}", status_code=303)
