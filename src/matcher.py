"""Matcher — Skill-Abgleich zwischen CV und Projektdaten."""

import logging
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from src.cv_manager import CVProfile

logger = logging.getLogger(__name__)

# Schwelle für Fuzzy-Match (0–100)
FUZZY_THRESHOLD = 80


@dataclass
class MatchDetail:
    """Ergebnis eines Projekt-CV-Abgleichs."""

    project_id: int
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    excluded: bool = False
    exclude_reason: str = ""


def _normalize(text: str) -> str:
    """Normalisiert Text für Vergleiche."""
    return text.strip().lower()


def _fuzzy_match(skill: str, candidates: list[str]) -> str | None:
    """Prüft ob ein Skill fuzzy in einer Kandidatenliste vorkommt.

    Für kurze Strings (≤4 Zeichen) wird kein Fuzzy-Match durchgeführt,
    da z.B. 'sap' vs 'asap' zu False Positives führt.

    Returns:
        Der gematchte Kandidat oder None.
    """
    if len(skill) <= 4:
        return None
    for candidate in candidates:
        if len(candidate) <= 4:
            continue
        if fuzz.ratio(skill, candidate) >= FUZZY_THRESHOLD:
            return candidate
    return None


def check_exclusions(
    cv: CVProfile,
    project_skills: list[str],
    project_description: str,
    project_industry: str,
) -> tuple[bool, str]:
    """Prüft Ausschlusskriterien.

    Returns:
        (excluded, reason) — True + Grund wenn ausgeschlossen.
    """
    desc_lower = _normalize(project_description)
    industry_lower = _normalize(project_industry)
    skills_lower = [_normalize(s) for s in project_skills]

    for excl in cv.exclude_skills:
        if excl in skills_lower:
            return True, f"Ausgeschlossener Skill: {excl}"
        if _fuzzy_match(excl, skills_lower):
            return True, f"Ausgeschlossener Skill (fuzzy): {excl}"
        # Auch in Beschreibung suchen
        if f" {excl} " in f" {desc_lower} ":
            return True, f"Ausgeschlossener Skill in Beschreibung: {excl}"

    for excl_ind in cv.exclude_industries:
        excl_lower = _normalize(excl_ind)
        if excl_lower in industry_lower:
            return True, f"Ausgeschlossene Branche: {excl_ind}"

    return False, ""


def match_skills(
    cv: CVProfile, project_skills: list[str]
) -> tuple[list[str], list[str]]:
    """Gleicht CV-Skills mit Projekt-Skills ab.

    Returns:
        (matched, missing) — gematchte und fehlende CV-Skills.
    """
    proj_lower = [_normalize(s) for s in project_skills]
    matched = []
    missing = []

    for skill in cv.all_skills:
        # Exakter Match
        if skill in proj_lower:
            matched.append(skill)
            continue
        # Fuzzy Match
        fuzzy_hit = _fuzzy_match(skill, proj_lower)
        if fuzzy_hit:
            matched.append(skill)
            continue

    # Missing = Projekt-Skills die nicht im CV sind
    cv_all_lower = cv.all_skills
    for ps in proj_lower:
        if ps not in cv_all_lower and not _fuzzy_match(ps, cv_all_lower):
            missing.append(ps)

    return matched, missing


def find_keywords(cv: CVProfile, description: str) -> list[str]:
    """Findet CV-Keywords in der Projektbeschreibung.

    Returns:
        Liste der gefundenen Keywords.
    """
    desc_lower = _normalize(description)
    found = []
    for kw in cv.keywords:
        if kw in desc_lower:
            found.append(kw)
    return found


def match_project(
    cv: CVProfile,
    project_id: int,
    project_skills: list[str],
    project_description: str,
    project_industry: str,
) -> MatchDetail:
    """Führt den vollständigen Match eines Projekts gegen den CV durch.

    Args:
        cv: Geladenes CV-Profil.
        project_id: Projekt-ID.
        project_skills: Skills des Projekts.
        project_description: Beschreibungstext.
        project_industry: Branche.

    Returns:
        MatchDetail mit allen Match-Informationen.
    """
    # Ausschluss prüfen
    excluded, reason = check_exclusions(
        cv, project_skills, project_description, project_industry
    )
    if excluded:
        logger.debug("Projekt %d ausgeschlossen: %s", project_id, reason)
        return MatchDetail(
            project_id=project_id,
            excluded=True,
            exclude_reason=reason,
        )

    matched, missing = match_skills(cv, project_skills)
    keywords = find_keywords(cv, project_description)

    return MatchDetail(
        project_id=project_id,
        matched_skills=matched,
        missing_skills=missing,
        matched_keywords=keywords,
    )
