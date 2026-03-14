"""Projektseiten-Scraper — lädt Detailseiten von freelancermap.de."""

import logging
import re
import time
from pathlib import Path

import httpx

from src.cookie_manager import get_authenticated_cookies

logger = logging.getLogger(__name__)

DEFAULT_DELAY = 5.0  # Sekunden zwischen Requests


def scrape_project_page(
    url: str,
    cookies: httpx.Cookies | None = None,
    timeout: float = 30.0,
) -> str:
    """Lädt eine einzelne Projektseite und gibt das HTML zurück.

    Args:
        url: URL der Projektdetailseite.
        cookies: httpx-Cookies. Wenn None, werden sie aus Firefox geladen.
        timeout: HTTP-Timeout in Sekunden.

    Returns:
        HTML-Inhalt der Seite.

    Raises:
        httpx.HTTPStatusError: Bei HTTP-Fehlern.
        RuntimeError: Wenn ein Login-Redirect erkannt wird.
    """
    if cookies is None:
        cookies = get_authenticated_cookies()

    with httpx.Client(
        cookies=cookies, follow_redirects=False, timeout=timeout
    ) as client:
        resp = client.get(url)

    if resp.status_code in (301, 302):
        location = resp.headers.get("location", "")
        if "login" in location.lower():
            raise RuntimeError(f"Session ungültig — Redirect zu {location}")
        # Normaler Redirect: folgen
        with httpx.Client(
            cookies=cookies, follow_redirects=True, timeout=timeout
        ) as client:
            resp = client.get(url)

    resp.raise_for_status()
    logger.debug("Seite geladen: %s (%d Bytes)", url, len(resp.text))
    return resp.text


def scrape_project_pages(
    urls: list[str],
    cookies: httpx.Cookies | None = None,
    delay: float = DEFAULT_DELAY,
    cache_dir: str | Path | None = None,
) -> dict[str, str]:
    """Lädt mehrere Projektseiten mit Verzögerung zwischen Requests.

    Args:
        urls: Liste von Projekt-URLs.
        cookies: httpx-Cookies. Wenn None, werden sie aus Firefox geladen.
        delay: Wartezeit zwischen Requests in Sekunden.
        cache_dir: Wenn gesetzt, wird HTML dort zwischengespeichert.

    Returns:
        Dict URL → HTML-Inhalt. Fehlgeschlagene URLs werden übersprungen.
    """
    if cookies is None:
        cookies = get_authenticated_cookies()

    if cache_dir:
        cache_path = Path(cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)

    results: dict[str, str] = {}

    for i, url in enumerate(urls):
        # Cache prüfen
        if cache_dir:
            project_id = _extract_id_from_url(url)
            cached_file = cache_path / f"{project_id}.html"
            if cached_file.exists():
                logger.info("Cache-Hit: %s", cached_file.name)
                results[url] = cached_file.read_text(encoding="utf-8")
                continue

        # Rate-Limiting
        if i > 0:
            logger.debug("Warte %s Sekunden...", delay)
            time.sleep(delay)

        try:
            html = scrape_project_page(url, cookies=cookies)
            results[url] = html

            # Cache schreiben
            if cache_dir:
                project_id = _extract_id_from_url(url)
                cached_file = cache_path / f"{project_id}.html"
                cached_file.write_text(html, encoding="utf-8")
                logger.debug("Cache gespeichert: %s", cached_file.name)

            logger.info("[%d/%d] OK: %s", i + 1, len(urls), url)

        except (httpx.HTTPError, RuntimeError):
            logger.exception("[%d/%d] Fehler bei %s", i + 1, len(urls), url)

    logger.info("Scraping fertig: %d/%d erfolgreich", len(results), len(urls))
    return results


def _extract_id_from_url(url: str) -> str:
    """Extrahiert die Projekt-ID aus der URL als String."""
    match = re.search(r"/nproj/(\d+)\.html", url)
    return match.group(1) if match else url.split("/")[-1]
