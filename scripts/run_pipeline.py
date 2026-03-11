#!/usr/bin/env python3
"""Freelance-Analyser Pipeline — Einstiegspunkt.

Verwendung:
    python scripts/run_pipeline.py --help
    python scripts/run_pipeline.py run --cv data/cv.yaml --mbox data/raw_emails/freelancermap.mbox
    python scripts/run_pipeline.py run --cv data/cv.yaml --mbox data/raw_emails/freelancermap.mbox --scrape
    python scripts/run_pipeline.py run --cv data/cv.yaml --db-only
    python scripts/run_pipeline.py rank --cv data/cv.yaml --top 10
"""

import logging
import sys
from dataclasses import asdict
from pathlib import Path

import click

from src.config import Settings
from src.cv_manager import load_cv
from src.database import (
    create_tables,
    get_all_projects,
    get_engine,
    get_session_factory,
    save_match_result,
    upsert_project,
)
from src.email_parser import parse_mbox_file
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
@click.option("--cv", "cv_path", required=True, type=click.Path(exists=True), help="Pfad zur CV YAML-Datei.")
@click.option("--mbox", "mbox_path", type=click.Path(exists=True), help="Pfad zur mbox-Datei.")
@click.option("--scrape", is_flag=True, help="Projektseiten scrapen (benötigt Cookies).")
@click.option("--db-url", default=None, help="Database-URL (überschreibt .env).")
@click.option("--top", default=20, help="Anzahl Top-Ergebnisse.", show_default=True)
@click.option("--log-level", default="INFO", help="Log-Level.", show_default=True)
def run(cv_path, mbox_path, scrape, db_url, top, log_level):
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

    # --- Phase 1: E-Mails parsen ---
    projects_from_email = []
    if mbox_path:
        logger.info("Lese mbox: %s", mbox_path)
        projects_from_email = parse_mbox_file(mbox_path)
        logger.info("%d Projekte aus E-Mails extrahiert", len(projects_from_email))

    # --- Phase 2: Scrapen (optional) ---
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
            detail = parse_project_html(html, url=url)
            scraped_details.append(detail)
    elif not scrape and projects_from_email:
        # Gecachte HTML-Dateien aus data/projects/ laden
        cache_dir = Path("data/projects")
        if cache_dir.exists():
            for entry in projects_from_email:
                html_file = cache_dir / f"sample_{entry.project_id}.html"
                if not html_file.exists():
                    html_file = cache_dir / f"{entry.project_id}.html"
                if html_file.exists():
                    html = html_file.read_text(encoding="utf-8")
                    detail = parse_project_html(html, url=entry.url)
                    scraped_details.append(detail)

    # --- Phase 3: DB speichern ---
    session = session_factory()
    stored_count = 0
    try:
        for detail in scraped_details:
            data = asdict(detail)
            upsert_project(session, data)
            stored_count += 1
        session.commit()
        logger.info("%d Projekte in DB gespeichert", stored_count)
    except Exception:
        session.rollback()
        logger.exception("Fehler beim DB-Speichern")
        raise
    finally:
        session.close()

    # --- Phase 4: Matching & Scoring ---
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
                match, cv,
                project_remote=proj.remote,
                project_location=proj.location,
                project_contract=proj.contract_type,
            )
            scored_list.append(scored)

            # Match in DB speichern
            save_match_result(
                session,
                project_id=proj.project_id,
                score=scored.score,
                matched_skills=scored.matched_skills,
                missing_skills=scored.missing_skills,
                notes=scored.exclude_reason if scored.excluded else "",
            )

        session.commit()

        # --- Phase 5: Ranking ausgeben ---
        ranked = rank_projects(scored_list)
        _print_ranking(ranked[:top], all_projects)

    except Exception:
        session.rollback()
        logger.exception("Fehler beim Matching")
        raise
    finally:
        session.close()


@cli.command()
@click.option("--cv", "cv_path", required=True, type=click.Path(exists=True), help="Pfad zur CV YAML-Datei.")
@click.option("--db-url", default=None, help="Database-URL.")
@click.option("--top", default=20, help="Anzahl Top-Ergebnisse.", show_default=True)
@click.option("--log-level", default="INFO", help="Log-Level.", show_default=True)
def rank(cv_path, db_url, top, log_level):
    """Matching & Ranking auf bereits gespeicherte Projekte anwenden."""
    _setup_logging(log_level)
    logger = logging.getLogger("pipeline")
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
                match, cv,
                project_remote=proj.remote,
                project_location=proj.location,
                project_contract=proj.contract_type,
            )
            scored_list.append(scored)

        ranked = rank_projects(scored_list)
        _print_ranking(ranked[:top], all_projects)
    finally:
        session.close()


def _print_ranking(ranked, all_projects):
    """Gibt die Rangliste formatiert aus."""
    projects_by_id = {p.project_id: p for p in all_projects}

    click.echo("\n" + "=" * 80)
    click.echo(f"  Top-{len(ranked)} Projekte nach Relevanz")
    click.echo("=" * 80)

    for i, scored in enumerate(ranked, 1):
        proj = projects_by_id.get(scored.project_id)
        title = proj.title if proj else f"Projekt {scored.project_id}"
        status = "AUSGESCHLOSSEN" if scored.excluded else f"{scored.score:.1f}"

        click.echo(f"\n  {i:2d}. [{status:>6s}]  {title}")
        if proj:
            click.echo(f"      Ort: {proj.location} | Remote: {proj.remote} | Vertrag: {proj.contract_type}")
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
