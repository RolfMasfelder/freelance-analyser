#!/usr/bin/env python3
"""Freelance-Analyser Pipeline — Einstiegspunkt.

Verwendung:
    python scripts/run_pipeline.py --help
    python scripts/run_pipeline.py run
    python scripts/run_pipeline.py run --no-scrape
    python scripts/run_pipeline.py run --no-imap --mbox data/raw_emails/mails.mbox
    python scripts/run_pipeline.py rank --top 10
"""

import logging
from dataclasses import asdict
from pathlib import Path

import click

from src.config import Settings
from src.cv_manager import load_cv
from src.database import (
    create_tables,
    ensure_project_exists,
    get_all_projects,
    get_engine,
    get_session_factory,
    save_match_result,
    upsert_project,
)
from src.email_fetcher import fetch_emails
from src.email_parser import parse_email_body, parse_mbox_file
from src.matcher import match_project
from src.project_parser import parse_project_html
from src.scoring import rank_projects, score_project


def _setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
def cli():
    """Freelance-Analyser — Projektüberwachung & CV-Matching."""
    pass


@cli.command()
@click.option(
    "--cv",
    "cv_path",
    default="data/cv.yaml",
    type=click.Path(exists=True),
    help="Pfad zur CV YAML-Datei.",
    show_default=True,
)
@click.option(
    "--mbox", "mbox_path", type=click.Path(exists=True), help="Pfad zur mbox-Datei."
)
@click.option(
    "--imap/--no-imap",
    default=True,
    help="E-Mails via IMAP abholen.",
    show_default=True,
)
@click.option(
    "--scrape/--no-scrape",
    default=True,
    help="Projektseiten scrapen (benötigt Cookies).",
    show_default=True,
)
@click.option("--db-url", default=None, help="Database-URL (überschreibt .env).")
@click.option("--top", default=20, help="Anzahl Top-Ergebnisse.", show_default=True)
@click.option("--log-level", default="INFO", help="Log-Level.", show_default=True)
def run(cv_path, mbox_path, imap, scrape, db_url, top, log_level):
    """Führt die komplette Pipeline aus: Parse → Scrape → DB → Match → Rank."""
    _setup_logging(log_level)
    logger = logging.getLogger("pipeline")
    settings = Settings()

    db_url = db_url or settings.database_url
    engine = get_engine(db_url)
    create_tables(engine)
    session_factory = get_session_factory(engine)
    cv = load_cv(cv_path)
    logger.info("CV geladen: %s (%d Skills)", cv.name, len(cv.all_skills))

    projects_from_email = _phase_fetch_emails(imap, mbox_path, settings, logger)
    scraped_details = _phase_scrape(scrape, projects_from_email, logger)
    new_project_ids = _phase_save_to_db(
        session_factory, projects_from_email, scraped_details, logger
    )
    _phase_match_and_score(session_factory, cv, top, new_project_ids, logger)


def _phase_fetch_emails(imap: bool, mbox_path, settings, logger) -> list:
    """Phase 1: E-Mails via IMAP oder mbox einlesen."""
    projects = []
    if imap:
        logger.info("Hole neue E-Mails via IMAP...")
        raw_emails = fetch_emails(settings=settings, mark_seen=True)
        logger.info("%d E-Mails abgerufen", len(raw_emails))
        for raw in raw_emails:
            projects.extend(parse_email_body(raw.body))
        logger.info("%d Projekte aus IMAP-Mails extrahiert", len(projects))
    elif mbox_path:
        logger.info("Lese mbox: %s", mbox_path)
        projects = parse_mbox_file(mbox_path)
        logger.info("%d Projekte aus E-Mails extrahiert", len(projects))
    return projects


def _phase_scrape(scrape: bool, projects_from_email: list, logger) -> list:
    """Phase 2: Projektseiten scrapen oder gecachte HTML-Dateien laden."""
    scraped_details = []
    if scrape and projects_from_email:
        from src.cookie_manager import get_authenticated_cookies
        from src.project_scraper import scrape_project_pages

        logger.info("Starte Scraping von %d Projekten...", len(projects_from_email))
        urls = [p.url for p in projects_from_email if p.url]
        cookies = get_authenticated_cookies()
        html_map = scrape_project_pages(urls, cookies)
        logger.info("%d Projektseiten gescraped", len(html_map))
        for url, html in html_map.items():
            scraped_details.append(parse_project_html(html, url=url))
    elif not scrape and projects_from_email:
        cache_dir = Path("data/projects")
        if cache_dir.exists():
            for entry in projects_from_email:
                html_file = cache_dir / f"sample_{entry.project_id}.html"
                if not html_file.exists():
                    html_file = cache_dir / f"{entry.project_id}.html"
                if html_file.exists():
                    html = html_file.read_text(encoding="utf-8")
                    scraped_details.append(parse_project_html(html, url=entry.url))
    return scraped_details


def _phase_save_to_db(
    session_factory, projects_from_email: list, scraped_details: list, logger
) -> set[int]:
    """Phase 3: Projekte in DB speichern. Gibt IDs neuer Projekte zurück."""
    session = session_factory()
    new_project_ids: set[int] = set()
    new_count = 0
    updated_count = 0
    try:
        for entry in projects_from_email:
            email_data = {
                "project_id": entry.project_id,
                "title": entry.title,
                "company": entry.company,
                "location": entry.location,
                "contract_type": entry.contract_type,
                "remote": entry.remote,
                "start": entry.start,
                "url": entry.url,
            }
            _, is_new = ensure_project_exists(session, email_data)
            if is_new:
                new_count += 1
                new_project_ids.add(entry.project_id)
            else:
                updated_count += 1
        for detail in scraped_details:
            upsert_project(session, asdict(detail))
        session.commit()
        logger.info(
            "%d neue Projekte in DB, %d aktualisiert, %d mit Details",
            new_count,
            updated_count,
            len(scraped_details),
        )
    except Exception:
        session.rollback()
        logger.exception("Fehler beim DB-Speichern")
        raise
    finally:
        session.close()
    return new_project_ids


def _phase_match_and_score(
    session_factory, cv, top: int, new_project_ids: set[int], logger
):
    """Phase 4+5: Matching, Scoring und Ranking ausgeben."""
    session = session_factory()
    try:
        all_projects = get_all_projects(session)
        logger.info("%d Projekte in DB für Matching", len(all_projects))
        scored_list = []
        for proj in all_projects:
            match = match_project(
                cv,
                project_id=proj.project_id,
                project_skills=proj.skills or [],
                project_description=proj.description,
                project_industry=proj.industry,
            )
            scored = score_project(
                match,
                cv,
                project_remote=proj.remote,
                project_location=proj.location,
                project_contract=proj.contract_type,
            )
            scored_list.append(scored)
            save_match_result(
                session,
                project_id=proj.project_id,
                score=scored.score,
                matched_skills=scored.matched_skills,
                missing_skills=scored.missing_skills,
                notes=scored.exclude_reason if scored.excluded else "",
            )
        session.commit()
        ranked = rank_projects(scored_list)
        _print_ranking(ranked[:top], all_projects, new_project_ids=new_project_ids)
    except Exception:
        session.rollback()
        logger.exception("Fehler beim Matching")
        raise
    finally:
        session.close()


@cli.command()
@click.option(
    "--cv",
    "cv_path",
    default="data/cv.yaml",
    type=click.Path(exists=True),
    help="Pfad zur CV YAML-Datei.",
    show_default=True,
)
@click.option("--db-url", default=None, help="Database-URL.")
@click.option("--top", default=20, help="Anzahl Top-Ergebnisse.", show_default=True)
@click.option("--log-level", default="INFO", help="Log-Level.", show_default=True)
def rank(cv_path, db_url, top, log_level):
    """Matching & Ranking auf bereits gespeicherte Projekte anwenden."""
    _setup_logging(log_level)
    settings = Settings()

    db_url = db_url or settings.database_url
    engine = get_engine(db_url)
    session_factory = get_session_factory(engine)
    cv = load_cv(cv_path)

    session = session_factory()
    try:
        all_projects = get_all_projects(session)
        if not all_projects:
            click.echo("Keine Projekte in der Datenbank.")
            return

        scored_list = []
        for proj in all_projects:
            match = match_project(
                cv,
                project_id=proj.project_id,
                project_skills=proj.skills or [],
                project_description=proj.description,
                project_industry=proj.industry,
            )
            scored = score_project(
                match,
                cv,
                project_remote=proj.remote,
                project_location=proj.location,
                project_contract=proj.contract_type,
            )
            scored_list.append(scored)

        ranked = rank_projects(scored_list)
        _print_ranking(ranked[:top], all_projects)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _print_ranking(ranked, all_projects, new_project_ids: set[int] | None = None):
    """Gibt die Rangliste formatiert aus."""
    projects_by_id = {p.project_id: p for p in all_projects}
    new_ids = new_project_ids or set()

    click.echo("\n" + "=" * 80)
    click.echo(f"  Top-{len(ranked)} Projekte nach Relevanz")
    click.echo("=" * 80)

    for i, scored in enumerate(ranked, 1):
        proj = projects_by_id.get(scored.project_id)
        title = proj.title if proj else f"Projekt {scored.project_id}"
        status = "AUSGESCHLOSSEN" if scored.excluded else f"{scored.score:.1f}"
        neu_tag = " ★NEU" if scored.project_id in new_ids else ""

        click.echo(f"\n  {i:2d}. [{status:>6s}]  {title}{neu_tag}")
        if proj:
            click.echo(
                f"      Ort: {proj.location} | Remote: {proj.remote} | Vertrag: {proj.contract_type}"
            )
            click.echo(f"      URL: {proj.url}")
        if scored.matched_skills:
            click.echo(f"      Skills ✓: {', '.join(scored.matched_skills)}")
        if scored.missing_skills:
            click.echo(f"      Skills ✗: {', '.join(scored.missing_skills[:5])}")
        if scored.matched_keywords:
            click.echo(f"      Keywords: {', '.join(scored.matched_keywords)}")
        if scored.excluded:
            click.echo(f"      Grund: {scored.exclude_reason}")

    click.echo("\n" + "=" * 80)


if __name__ == "__main__":
    cli()
