"""Projekt-Parser — extrahiert strukturierte Daten aus freelancermap HTML."""

import re
import logging
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Häufige Wörter für Spracherkennung (Stoppwörter + branchentypische Begriffe)
_EN_MARKERS = frozenset(
    {
        "the",
        "and",
        "for",
        "you",
        "with",
        "are",
        "will",
        "our",
        "your",
        "this",
        "from",
        "that",
        "have",
        "experience",
        "looking",
        "required",
        "responsibilities",
        "requirements",
        "should",
        "must",
    }
)
_DE_MARKERS = frozenset(
    {
        "und",
        "die",
        "der",
        "wir",
        "für",
        "ein",
        "eine",
        "den",
        "des",
        "ist",
        "von",
        "mit",
        "auf",
        "als",
        "sich",
        "suchen",
        "erfahrung",
        "kenntnisse",
        "anforderungen",
        "aufgaben",
    }
)


def _detect_language(text: str) -> str:
    """Erkennt die Sprache eines Textes anhand häufiger Wörter.

    Returns:
        ISO-639-1 Sprachcode ('de' oder 'en'). Default: 'de'.
    """
    words = re.findall(r"[a-zäöüß]+", text.lower())
    if not words:
        return "de"
    en_count = sum(1 for w in words if w in _EN_MARKERS)
    de_count = sum(1 for w in words if w in _DE_MARKERS)
    return "en" if en_count > de_count else "de"


@dataclass
class ProjectDetail:
    """Vollständige Projektdaten aus einer Detailseite."""

    project_id: int
    title: str
    description: str
    company: str
    contact: str
    location: str
    country: str
    industry: str
    remote: str
    contract_type: str
    start: str
    duration: str
    utilization: str
    skills: list[str] = field(default_factory=list)
    language: str = "de"
    url: str = ""


def parse_project_html(html: str, url: str = "") -> ProjectDetail:
    """Parst eine freelancermap-Projektdetailseite.

    Args:
        html: HTML-Inhalt der Seite.
        url: URL der Seite (optional, für Referenz).

    Returns:
        ProjectDetail mit allen extrahierten Feldern.
    """
    soup = BeautifulSoup(html, "lxml")

    title = _get_title(soup)
    description = _get_description(soup)
    company, contact, project_id = _get_body_info(soup)
    skills = _get_skills(soup)
    location, country, industry, remote, contract_type, start, duration, utilization = (
        _get_header_info(soup)
    )
    language = _detect_language(title + " " + description)

    # Projekt-ID aus URL als Fallback
    if not project_id and url:
        match = re.search(r"/nproj/(\d+)\.html", url)
        if match:
            project_id = int(match.group(1))

    return ProjectDetail(
        project_id=project_id,
        title=title,
        description=description,
        company=company,
        contact=contact,
        location=location,
        country=country,
        industry=industry,
        remote=remote,
        contract_type=contract_type,
        start=start,
        duration=duration,
        utilization=utilization,
        skills=skills,
        language=language,
        url=url,
    )


def _get_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    return h1.get_text(strip=True) if h1 else ""


def _get_description(soup: BeautifulSoup) -> str:
    desc_div = soup.find("div", class_="project-body-description")
    if desc_div:
        return desc_div.get_text(separator="\n", strip=True)
    return ""


def _get_body_info(soup: BeautifulSoup) -> tuple[str, str, int]:
    """Extrahiert Firma, Ansprechpartner und Projekt-ID."""
    company = ""
    contact = ""
    project_id = 0

    info_div = soup.find("div", class_="project-body-info")
    if not info_div:
        return company, contact, project_id

    for title_div in info_div.find_all("div", class_="project-body-info-title"):
        label = title_div.get_text(strip=True)
        sibling = title_div.find_next_sibling()
        value = sibling.get_text(strip=True) if sibling else ""

        if "Eingestellt von" in label:
            company = value
        elif "Ansprechpartner" in label:
            contact = value
        elif "Projekt-ID" in label:
            try:
                project_id = int(value)
            except ValueError:
                pass

    return company, contact, project_id


def _get_skills(soup: BeautifulSoup) -> list[str]:
    badges_div = soup.find("div", class_="project-body-badges")
    if not badges_div:
        return []
    return [
        el.get_text(strip=True)
        for el in badges_div.find_all(class_="badge-grey")
        if el.get_text(strip=True)
    ]


def _get_header_info(
    soup: BeautifulSoup,
) -> tuple[str, str, str, str, str, str, str, str]:
    """Extrahiert Ort, Land, Branche, Remote, Vertragsart, Start, Dauer, Auslastung."""
    location = ""
    country = ""
    industry = ""
    remote = ""
    contract_type = ""
    start = ""
    duration = ""
    utilization = ""

    header = soup.find("div", class_="project-header")
    if not header:
        return (
            location,
            country,
            industry,
            remote,
            contract_type,
            start,
            duration,
            utilization,
        )

    # Branche
    badge = header.find("span", class_="badge")
    if badge:
        industry = badge.get_text(strip=True)

    # Ort-Elemente
    loc_elements = header.find_all("span", class_="location-element")
    if loc_elements:
        parts = [el.get_text(strip=True).rstrip(",") for el in loc_elements]
        if len(parts) >= 2:
            location = parts[0]
            country = parts[1]
        elif len(parts) == 1:
            location = parts[0]

    # Elemente mit Divider (Remote, Vertragsart, Start, Dauer, Auslastung)
    for span in header.find_all("span", class_="element-with-divider"):
        text = span.get_text(strip=True)
        if "Remote" in text:
            remote = text
        elif "Start" in text:
            start = text.removeprefix("Start").strip()
        elif "Dauer" in text:
            duration = text.removeprefix("Dauer").strip()
        elif "Auslastung" in text:
            utilization = text.removeprefix("Auslastung").strip()
        elif text in ("Freiberuflich", "Festanstellung", "Arbeitnehmerüberlassung"):
            contract_type = text
        elif not contract_type and "%" not in text and "Start" not in text:
            contract_type = text

    return (
        location,
        country,
        industry,
        remote,
        contract_type,
        start,
        duration,
        utilization,
    )
