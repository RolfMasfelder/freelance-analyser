"""Tests für src/scoring.py — Relevanz-Score-Berechnung."""

import pytest

from src.cv_manager import CVProfile
from src.matcher import MatchDetail
from src.scoring import (
    ScoredProject,
    rank_projects,
    score_project,
)


@pytest.fixture()
def cv():
    return CVProfile(
        name="Test",
        skills=["python", "docker", "postgresql"],
        skills_secondary=["fastapi", "react"],
        exclude_skills=["sap"],
        keywords=["backend", "cloud", "devops"],
        preferred_locations=["München"],
        preferred_remote="100%",
        preferred_contract_types=["Freiberuflich"],
    )


@pytest.fixture()
def good_match():
    return MatchDetail(
        project_id=1,
        matched_skills=["python", "docker", "fastapi"],
        missing_skills=["kubernetes"],
        matched_keywords=["backend", "cloud"],
    )


@pytest.fixture()
def poor_match():
    return MatchDetail(
        project_id=2,
        matched_skills=[],
        missing_skills=["c#", ".net"],
        matched_keywords=[],
    )


@pytest.fixture()
def excluded_match():
    return MatchDetail(
        project_id=3,
        excluded=True,
        exclude_reason="Ausgeschlossener Skill: sap",
    )


class TestScoreProject:
    def test_good_match_high_score(self, cv, good_match):
        scored = score_project(
            good_match, cv,
            project_remote="100%",
            project_location="München",
            project_contract="Freiberuflich",
        )
        assert scored.score > 50
        assert scored.skill_score > 0
        assert scored.keyword_score > 0
        assert scored.remote_score == 100.0
        assert scored.location_score == 100.0
        assert scored.contract_score == 100.0
        assert not scored.excluded

    def test_poor_match_low_score(self, cv, poor_match):
        scored = score_project(
            poor_match, cv,
            project_remote="0%",
            project_location="Hamburg",
            project_contract="Festanstellung",
        )
        assert scored.score < 30
        assert scored.skill_score == 0.0

    def test_excluded_zero_score(self, cv, excluded_match):
        scored = score_project(excluded_match, cv)
        assert scored.score == 0.0
        assert scored.excluded
        assert scored.exclude_reason != ""

    def test_remote_scoring_partial(self, cv, good_match):
        scored = score_project(good_match, cv, project_remote="50%")
        assert scored.remote_score == 50.0

    def test_remote_scoring_exceeds(self, cv, good_match):
        scored = score_project(good_match, cv, project_remote="100%")
        assert scored.remote_score == 100.0

    def test_location_no_match(self, cv, good_match):
        scored = score_project(good_match, cv, project_location="Berlin")
        assert scored.location_score == 25.0

    def test_location_match(self, cv, good_match):
        scored = score_project(good_match, cv, project_location="München, Bayern")
        assert scored.location_score == 100.0

    def test_contract_match(self, cv, good_match):
        scored = score_project(good_match, cv, project_contract="Freiberuflich / Contracting")
        assert scored.contract_score == 100.0

    def test_score_within_range(self, cv, good_match):
        scored = score_project(good_match, cv)
        assert 0 <= scored.score <= 100

    def test_empty_cv_preferences(self, good_match):
        empty_cv = CVProfile(skills=["python"], skills_secondary=[])
        scored = score_project(good_match, empty_cv)
        assert 0 <= scored.score <= 100


class TestRankProjects:
    def test_ranking_order(self):
        projects = [
            ScoredProject(project_id=1, score=40.0, skill_score=0, keyword_score=0,
                          remote_score=0, location_score=0, contract_score=0,
                          matched_skills=[], missing_skills=[], matched_keywords=[]),
            ScoredProject(project_id=2, score=90.0, skill_score=0, keyword_score=0,
                          remote_score=0, location_score=0, contract_score=0,
                          matched_skills=[], missing_skills=[], matched_keywords=[]),
            ScoredProject(project_id=3, score=65.0, skill_score=0, keyword_score=0,
                          remote_score=0, location_score=0, contract_score=0,
                          matched_skills=[], missing_skills=[], matched_keywords=[]),
        ]
        ranked = rank_projects(projects)
        assert ranked[0].project_id == 2
        assert ranked[1].project_id == 3
        assert ranked[2].project_id == 1

    def test_ranking_empty(self):
        assert rank_projects([]) == []
