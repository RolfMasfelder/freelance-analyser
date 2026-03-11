"""Scoring — berechnet Relevanz-Score (0–100) für Projekte."""

import logging
from dataclasses import dataclass

from src.cv_manager import CVProfile
from src.matcher import MatchDetail

logger = logging.getLogger(__name__)

# Gewichtung der Score-Komponenten (Summe = 1.0)
WEIGHT_SKILLS = 0.50
WEIGHT_KEYWORDS = 0.15
WEIGHT_REMOTE = 0.15
WEIGHT_LOCATION = 0.10
WEIGHT_CONTRACT = 0.10


@dataclass
class ScoredProject:
    """Projekt mit berechnetem Relevanz-Score."""

    project_id: int
    score: float
    skill_score: float
    keyword_score: float
    remote_score: float
    location_score: float
    contract_score: float
    matched_skills: list[str]
    missing_skills: list[str]
    matched_keywords: list[str]
    excluded: bool = False
    exclude_reason: str = ""
    notes: str = ""


def _calc_skill_score(match: MatchDetail, cv: CVProfile) -> float:
    """Berechnet Skill-Score: Anteil gematchter Skills an Gesamt-CV-Skills (0–100)."""
    total = len(cv.all_skills)
    if total == 0:
        return 0.0
    # Primäre Skills zählen doppelt
    primary_matched = sum(1 for s in match.matched_skills if s in cv.skills)
    secondary_matched = sum(1 for s in match.matched_skills if s in cv.skills_secondary)
    weighted = (
        (primary_matched * 2.0 + secondary_matched)
        / (len(cv.skills) * 2.0 + len(cv.skills_secondary))
        * 100
    )
    return min(weighted, 100.0)


def _calc_keyword_score(match: MatchDetail, cv: CVProfile) -> float:
    """Berechnet Keyword-Score: Anteil gefundener Keywords (0–100)."""
    total = len(cv.keywords)
    if total == 0:
        return 0.0
    return len(match.matched_keywords) / total * 100


def _calc_remote_score(cv: CVProfile, project_remote: str) -> float:
    """Berechnet Remote-Score basierend auf Präferenz (0–100)."""
    if not cv.preferred_remote or not project_remote:
        return 50.0  # Neutral bei fehlender Info

    pref = cv.preferred_remote.replace("%", "").strip()
    proj = project_remote.replace("%", "").strip()

    try:
        pref_val = float(pref)
        proj_val = float(proj)
    except ValueError:
        # Textvergleich
        if "remote" in project_remote.lower() or "100" in project_remote:
            return 100.0
        return 50.0

    if proj_val >= pref_val:
        return 100.0
    # Proportional reduzieren
    return max(0.0, proj_val / pref_val * 100)


def _calc_location_score(cv: CVProfile, project_location: str) -> float:
    """Berechnet Standort-Score (0–100)."""
    if not cv.preferred_locations or not project_location:
        return 50.0

    loc_lower = project_location.lower()
    for pref_loc in cv.preferred_locations:
        if pref_loc.lower() in loc_lower:
            return 100.0
    return 25.0  # Anderer Standort


def _calc_contract_score(cv: CVProfile, project_contract: str) -> float:
    """Berechnet Vertragsart-Score (0–100)."""
    if not cv.preferred_contract_types or not project_contract:
        return 50.0

    contract_lower = project_contract.lower()
    for pref in cv.preferred_contract_types:
        if pref.lower() in contract_lower:
            return 100.0
    return 25.0


def score_project(
    match: MatchDetail,
    cv: CVProfile,
    project_remote: str = "",
    project_location: str = "",
    project_contract: str = "",
) -> ScoredProject:
    """Berechnet den Gesamt-Relevanz-Score für ein Projekt.

    Args:
        match: MatchDetail vom Matcher.
        cv: CV-Profil.
        project_remote: Remote-Anteil des Projekts.
        project_location: Standort des Projekts.
        project_contract: Vertragsart.

    Returns:
        ScoredProject mit Score-Details (0–100).
    """
    if match.excluded:
        return ScoredProject(
            project_id=match.project_id,
            score=0.0,
            skill_score=0.0,
            keyword_score=0.0,
            remote_score=0.0,
            location_score=0.0,
            contract_score=0.0,
            matched_skills=[],
            missing_skills=[],
            matched_keywords=[],
            excluded=True,
            exclude_reason=match.exclude_reason,
        )

    skill_score = _calc_skill_score(match, cv)
    keyword_score = _calc_keyword_score(match, cv)
    remote_score = _calc_remote_score(cv, project_remote)
    location_score = _calc_location_score(cv, project_location)
    contract_score = _calc_contract_score(cv, project_contract)

    total = (
        skill_score * WEIGHT_SKILLS
        + keyword_score * WEIGHT_KEYWORDS
        + remote_score * WEIGHT_REMOTE
        + location_score * WEIGHT_LOCATION
        + contract_score * WEIGHT_CONTRACT
    )

    return ScoredProject(
        project_id=match.project_id,
        score=round(total, 1),
        skill_score=round(skill_score, 1),
        keyword_score=round(keyword_score, 1),
        remote_score=round(remote_score, 1),
        location_score=round(location_score, 1),
        contract_score=round(contract_score, 1),
        matched_skills=match.matched_skills,
        missing_skills=match.missing_skills,
        matched_keywords=match.matched_keywords,
    )


def rank_projects(scored: list[ScoredProject]) -> list[ScoredProject]:
    """Sortiert Projekte nach Score (absteigend)."""
    return sorted(scored, key=lambda p: p.score, reverse=True)
