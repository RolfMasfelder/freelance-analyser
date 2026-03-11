"""Tests für project_parser — Unit-Tests + Integration mit gespeichertem HTML."""

from pathlib import Path

import pytest

from src.project_parser import (
    ProjectDetail,
    _get_skills,
    _get_title,
    parse_project_html,
)

SAMPLE_HTML = Path("data/projects/sample_2977008.html")


class TestParseProjectHtmlUnit:
    MINIMAL_HTML = """
    <html><body>
    <div class="project-header">
        <h1>Python Entwickler gesucht</h1>
        <span class="badge">IT</span>
        <span class="location-element">Berlin,</span>
        <span class="location-element">Deutschland</span>
        <span class="element-with-divider">100%Remote</span>
        <span class="element-with-divider">Freiberuflich</span>
        <span class="element-with-divider">Start4/2026</span>
        <span class="element-with-divider">Dauer6Monate</span>
        <span class="element-with-divider">80%Auslastung</span>
    </div>
    <div class="project-body-info">
        <div class="project-body-info-title">Eingestellt von</div>
        <div>Testfirma GmbH</div>
        <div class="project-body-info-title">Ansprechpartner</div>
        <div>Max Mustermann</div>
        <div class="project-body-info-title">Projekt-ID</div>
        <div>12345</div>
    </div>
    <div class="project-body-badges">
        <span>Python</span>
        <span>Django</span>
        <span>PostgreSQL</span>
    </div>
    <div class="project-body-description">
        Wir suchen einen Python Entwickler für ein spannendes Projekt.
    </div>
    </body></html>
    """

    def test_title(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.title == "Python Entwickler gesucht"

    def test_company(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.company == "Testfirma GmbH"

    def test_contact(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.contact == "Max Mustermann"

    def test_project_id(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.project_id == 12345

    def test_skills(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.skills == ["Python", "Django", "PostgreSQL"]

    def test_description(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert "Python Entwickler" in result.description

    def test_location(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.location == "Berlin"
        assert result.country == "Deutschland"

    def test_remote(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert "100%" in result.remote

    def test_contract_type(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.contract_type == "Freiberuflich"

    def test_start(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.start == "4/2026"

    def test_industry(self):
        result = parse_project_html(self.MINIMAL_HTML)
        assert result.industry == "IT"

    def test_url_passthrough(self):
        result = parse_project_html(self.MINIMAL_HTML, url="https://example.com/nproj/12345.html")
        assert result.url == "https://example.com/nproj/12345.html"

    def test_empty_html(self):
        result = parse_project_html("<html></html>")
        assert result.title == ""
        assert result.skills == []
        assert result.project_id == 0


@pytest.mark.skipif(not SAMPLE_HTML.exists(), reason="Sample HTML nicht vorhanden")
class TestParseRealHtml:
    @pytest.fixture
    def project(self):
        html = SAMPLE_HTML.read_text(encoding="utf-8")
        return parse_project_html(html, url="https://www.freelancermap.de/nproj/2977008.html")

    def test_title(self, project):
        assert "CRM" in project.title

    def test_project_id(self, project):
        assert project.project_id == 2977008

    def test_company(self, project):
        assert project.company == "Target Networks GmbH"

    def test_has_description(self, project):
        assert len(project.description) > 100

    def test_has_skills(self, project):
        assert len(project.skills) > 5
        assert "C#" in project.skills

    def test_location(self, project):
        assert project.location == "Berlin"

    def test_remote(self, project):
        assert "100%" in project.remote

    def test_contract_type(self, project):
        assert project.contract_type == "Freiberuflich"

    def test_start(self, project):
        assert "2026" in project.start

    def test_industry(self, project):
        assert project.industry == "Energiewirtschaft"
