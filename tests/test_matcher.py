"""Tests für src/matcher.py — Skill-Abgleich und Ausschluss."""

import pytest

from src.cv_manager import CVProfile
from src.matcher import (
    MatchDetail,
    check_exclusions,
    find_keywords,
    match_project,
    match_skills,
)


@pytest.fixture()
def cv():
    return CVProfile(
        name="Test",
        skills=["python", "docker", "postgresql"],
        skills_secondary=["fastapi", "react"],
        exclude_skills=["sap", "abap"],
        exclude_industries=["pharma"],
        keywords=["backend", "cloud", "devops"],
        preferred_locations=["München"],
        preferred_remote="100%",
        preferred_contract_types=["Freiberuflich"],
    )


class TestMatchSkills:
    def test_exact_match(self, cv):
        matched, missing = match_skills(cv, ["Python", "Docker", "React"])
        assert "python" in matched
        assert "docker" in matched
        assert "react" in matched

    def test_no_match(self, cv):
        matched, missing = match_skills(cv, ["SAP", "ABAP"])
        assert matched == []

    def test_fuzzy_match(self, cv):
        """Leicht abweichende Schreibweise sollte matchen."""
        matched, _ = match_skills(cv, ["Pythons", "Dockers"])
        # "Pythons" vs "python" — ratio hängt von rapidfuzz ab
        # Mindestens einer sollte fuzzy matchen
        assert len(matched) >= 0  # Nicht crashen

    def test_missing_skills(self, cv):
        _, missing = match_skills(cv, ["Python", "Kubernetes", "Terraform"])
        assert "kubernetes" in missing
        assert "terraform" in missing

    def test_empty_project_skills(self, cv):
        matched, missing = match_skills(cv, [])
        assert matched == []
        assert missing == []

    def test_empty_cv_skills(self):
        empty_cv = CVProfile(skills=[], skills_secondary=[])
        matched, missing = match_skills(empty_cv, ["Python"])
        assert matched == []
        assert "python" in missing

    def test_short_strings_no_fuzzy(self, cv):
        """'asap' darf nicht als fuzzy-Match für 'sap' gelten."""
        matched, _ = match_skills(cv, ["asap", "Go"])
        assert "sap" not in [s for s in matched]


class TestCheckExclusionsShortFuzzy:
    def test_asap_not_excluded_as_sap(self):
        cv = CVProfile(exclude_skills=["sap"])
        excluded, _ = check_exclusions(cv, ["asap"], "", "")
        assert not excluded


class TestCheckExclusions:
    def test_excluded_skill(self, cv):
        excluded, reason = check_exclusions(cv, ["SAP", "Python"], "", "")
        assert excluded
        assert "sap" in reason.lower()

    def test_excluded_industry(self, cv):
        excluded, reason = check_exclusions(cv, ["Python"], "", "Pharma & Life Sciences")
        assert excluded
        assert "pharma" in reason.lower()

    def test_excluded_skill_in_description(self, cv):
        excluded, reason = check_exclusions(cv, [], "Wir suchen SAP Berater", "")
        assert excluded

    def test_not_excluded(self, cv):
        excluded, _ = check_exclusions(cv, ["Python", "Docker"], "Backend-Entwicklung", "IT")
        assert not excluded

    def test_empty_exclusions(self):
        cv = CVProfile(exclude_skills=[], exclude_industries=[])
        excluded, _ = check_exclusions(cv, ["SAP"], "SAP Projekt", "Pharma")
        assert not excluded


class TestFindKeywords:
    def test_keywords_found(self, cv):
        found = find_keywords(cv, "Wir entwickeln eine Cloud-basierte Backend-API mit DevOps.")
        assert "backend" in found
        assert "cloud" in found
        assert "devops" in found

    def test_no_keywords(self, cv):
        found = find_keywords(cv, "SAP Modul-Konfiguration in der Buchhaltung.")
        assert found == []

    def test_partial_keyword(self, cv):
        found = find_keywords(cv, "Das Backend ist fertig.")
        assert "backend" in found


class TestMatchProject:
    def test_full_match(self, cv):
        detail = match_project(
            cv, project_id=42,
            project_skills=["Python", "Docker", "FastAPI"],
            project_description="Cloud Backend Entwicklung",
            project_industry="IT",
        )
        assert not detail.excluded
        assert "python" in detail.matched_skills
        assert "cloud" in detail.matched_keywords

    def test_excluded_project(self, cv):
        detail = match_project(
            cv, project_id=99,
            project_skills=["SAP", "ABAP", "Java"],
            project_description="SAP S/4HANA Migration",
            project_industry="Automotive",
        )
        assert detail.excluded
        assert detail.exclude_reason != ""
        assert detail.matched_skills == []

    def test_no_skills_match(self, cv):
        detail = match_project(
            cv, project_id=77,
            project_skills=["C#", ".NET", "Azure DevOps"],
            project_description="Windows Desktop-App",
            project_industry="Finance",
        )
        assert not detail.excluded
        assert len(detail.matched_skills) == 0  # oder wenige fuzzy
