"""Tests für src/cv_manager.py — CV laden und strukturieren."""

import pytest

from src.cv_manager import ExperienceEntry, load_cv


@pytest.fixture()
def cv_yaml(tmp_path):
    """Erstellt eine temporäre CV-YAML-Datei."""
    content = """\
name: "Test User"
title: "Developer"
experience_years: 10
skills:
  - Python
  - Java
  - Docker
skills_secondary:
  - FastAPI
  - React
preferred_locations:
  - München
  - Remote
preferred_remote: "80%"
preferred_contract_types:
  - Freiberuflich
exclude_skills:
  - SAP
  - ABAP
exclude_industries:
  - Pharma
min_duration_months: 3
keywords:
  - backend
  - cloud
experience:
  - role: "Entwickler"
    project: "API-Plattform"
    company: "Firma X"
    period: "2021–2023"
    description: "REST-API-Entwicklung mit Python."
    skills:
      - Python
      - Docker
  - role: "Berater"
    project: "Java-Migration"
    company: "Firma Y"
    period: "2019–2021"
    description: "Mitarbeit an der Migration auf Java 17."
    skills:
      - Java
"""
    path = tmp_path / "cv.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestLoadCV:
    def test_load_basic_fields(self, cv_yaml):
        cv = load_cv(cv_yaml)
        assert cv.name == "Test User"
        assert cv.title == "Developer"
        assert cv.experience_years == 10

    def test_load_skills(self, cv_yaml):
        cv = load_cv(cv_yaml)
        assert cv.skills == ["python", "java", "docker"]
        assert cv.skills_secondary == ["fastapi", "react"]

    def test_all_skills(self, cv_yaml):
        cv = load_cv(cv_yaml)
        assert cv.all_skills == ["python", "java", "docker", "fastapi", "react"]

    def test_load_preferences(self, cv_yaml):
        cv = load_cv(cv_yaml)
        assert cv.preferred_locations == ["München", "Remote"]
        assert cv.preferred_remote == "80%"
        assert cv.preferred_contract_types == ["Freiberuflich"]
        assert cv.min_duration_months == 3

    def test_load_exclusions(self, cv_yaml):
        cv = load_cv(cv_yaml)
        assert cv.exclude_skills == ["sap", "abap"]
        assert cv.exclude_industries == ["pharma"]

    def test_load_keywords(self, cv_yaml):
        cv = load_cv(cv_yaml)
        assert cv.keywords == ["backend", "cloud"]

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_cv("/nonexistent/cv.yaml")

    def test_invalid_yaml(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("just a string", encoding="utf-8")
        with pytest.raises(ValueError, match="Ungültiges CV-Format"):
            load_cv(path)

    def test_empty_yaml(self, tmp_path):
        path = tmp_path / "empty.yaml"
        path.write_text("{}", encoding="utf-8")
        cv = load_cv(path)
        assert cv.name == ""
        assert cv.skills == []

    def test_minimal_yaml(self, tmp_path):
        path = tmp_path / "mini.yaml"
        path.write_text("name: Mini\nskills:\n  - Go\n", encoding="utf-8")
        cv = load_cv(path)
        assert cv.name == "Mini"
        assert cv.skills == ["go"]

    def test_skills_lowercased(self, cv_yaml):
        cv = load_cv(cv_yaml)
        for skill in cv.skills + cv.skills_secondary + cv.exclude_skills:
            assert skill == skill.lower()

    def test_load_experience(self, cv_yaml):
        cv = load_cv(cv_yaml)
        assert len(cv.experience) == 2
        assert isinstance(cv.experience[0], ExperienceEntry)
        assert cv.experience[0].role == "Entwickler"
        assert cv.experience[0].project == "API-Plattform"
        assert cv.experience[0].company == "Firma X"
        assert cv.experience[0].period == "2021–2023"
        assert "python" in cv.experience[0].skills

    def test_experience_skills_lowercased(self, cv_yaml):
        cv = load_cv(cv_yaml)
        for entry in cv.experience:
            for skill in entry.skills:
                assert skill == skill.lower()

    def test_no_experience_field(self, tmp_path):
        path = tmp_path / "no_exp.yaml"
        path.write_text("name: Test\nskills:\n  - Go\n", encoding="utf-8")
        cv = load_cv(path)
        assert cv.experience == []

    def test_real_cv_file(self):
        """Integration: Echte CV-Datei laden."""
        from pathlib import Path

        cv_path = Path("data/cv.yaml")
        if not cv_path.exists():
            pytest.skip("data/cv.yaml nicht vorhanden")
        cv = load_cv(cv_path)
        assert cv.name != ""
        assert len(cv.skills) > 0
