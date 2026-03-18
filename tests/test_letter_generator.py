"""Tests für src/letter_generator.py — Antwortschreiben-Generierung."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.cv_manager import CVProfile, ExperienceEntry
from src.database import Project
from src.letter_generator import (
    LetterResult,
    _build_user_prompt,
    _find_relevant_experience,
    _format_experience,
    _strip_thinking,
    generate_letter,
)


@pytest.fixture()
def cv():
    return CVProfile(
        name="Max Mustermann",
        title="Senior Entwickler",
        experience_years=15,
        skills=["python", "docker", "postgresql"],
        skills_secondary=["fastapi", "react"],
        exclude_skills=["sap"],
        keywords=["backend", "cloud"],
        preferred_locations=["München"],
        preferred_remote="100%",
        preferred_contract_types=["Freiberuflich"],
        experience=[
            ExperienceEntry(
                role="Backend-Entwickler",
                project="REST-API-Plattform",
                company="Test GmbH",
                period="2021–2023",
                description="Entwicklung von REST-APIs mit Python/Django. Docker-Deployment.",
                skills=["python", "docker", "rest"],
            ),
            ExperienceEntry(
                role="Datenbankentwickler",
                project="PostgreSQL-Migration",
                company="DB Corp",
                period="2019–2021",
                description="Mitarbeit bei der Migration von MySQL auf PostgreSQL.",
                skills=["postgresql", "sql", "migration"],
            ),
        ],
    )


@pytest.fixture()
def project():
    return Project(
        project_id=42,
        title="Python Backend Entwickler",
        description="Wir suchen einen erfahrenen Python-Entwickler",
        company="Test GmbH",
        location="München",
        remote="100%",
        contract_type="Freiberuflich",
        start="sofort",
        duration="6 Monate",
        skills=["Python", "Docker", "Kubernetes"],
        url="https://example.com/project/42",
        first_seen=datetime.now(UTC),
        last_seen=datetime.now(UTC),
    )


class TestStripThinking:
    def test_removes_think_block(self):
        text = "<think>Reasoning here...</think>\nSehr geehrte Damen und Herren"
        assert _strip_thinking(text) == "Sehr geehrte Damen und Herren"

    def test_removes_multiline_think_block(self):
        text = "<think>\n1. Analyze\n2. Draft\n3. Review\n</think>\n\nAntwort"
        assert _strip_thinking(text) == "Antwort"

    def test_no_think_block_unchanged(self):
        text = "Sehr geehrte Damen und Herren"
        assert _strip_thinking(text) == text

    def test_empty_string(self):
        assert _strip_thinking("") == ""

    def test_multiple_think_blocks(self):
        text = "<think>A</think>Text<think>B</think>"
        assert _strip_thinking(text) == "Text"


class TestBuildUserPrompt:
    def test_contains_project_title(self, project, cv):
        prompt = _build_user_prompt(project, cv)
        assert "Python Backend Entwickler" in prompt

    def test_contains_cv_name(self, project, cv):
        prompt = _build_user_prompt(project, cv)
        assert "Max Mustermann" in prompt

    def test_contains_project_skills(self, project, cv):
        prompt = _build_user_prompt(project, cv)
        assert "Python" in prompt
        assert "Docker" in prompt

    def test_contains_cv_skills(self, project, cv):
        prompt = _build_user_prompt(project, cv)
        assert "python" in prompt
        assert "docker" in prompt
        assert "postgresql" in prompt

    def test_contains_matched_skills(self, project, cv):
        prompt = _build_user_prompt(project, cv, matched_skills=["Python", "Docker"])
        assert "Python, Docker" in prompt

    def test_no_matched_skills_shows_dash(self, project, cv):
        prompt = _build_user_prompt(project, cv, matched_skills=None)
        # "Passende Skills (CV ∩ Projekt): –"
        assert "–" in prompt

    def test_missing_company(self, project, cv):
        project.company = None
        prompt = _build_user_prompt(project, cv)
        assert "nicht angegeben" in prompt

    def test_contains_experience_years(self, project, cv):
        prompt = _build_user_prompt(project, cv)
        assert "15" in prompt

    def test_contains_description(self, project, cv):
        prompt = _build_user_prompt(project, cv)
        assert "erfahrenen Python-Entwickler" in prompt


class TestGenerateLetter:
    @patch("src.letter_generator.OpenAI")
    def test_returns_letter_result(self, mock_openai_cls, project, cv):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 200
        mock_usage.completion_tokens = 150

        mock_choice = MagicMock()
        mock_choice.message.content = "Sehr geehrte Damen und Herren..."

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "llama3.1:8b"
        mock_response.usage = mock_usage

        mock_client.chat.completions.create.return_value = mock_response

        settings = MagicMock()
        settings.llm_base_url = "http://localhost:11434/v1"
        settings.llm_api_key = "ollama"
        settings.llm_model = "llama3.1:8b"

        result = generate_letter(project, cv, ["Python", "Docker"], settings)

        assert isinstance(result, LetterResult)
        assert result.letter == "Sehr geehrte Damen und Herren..."
        assert result.model == "llama3.1:8b"
        assert result.prompt_tokens == 200
        assert result.completion_tokens == 150

    @patch("src.letter_generator.OpenAI")
    def test_calls_openai_with_correct_params(self, mock_openai_cls, project, cv):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Antwort"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "test-model"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response

        settings = MagicMock()
        settings.llm_base_url = "http://localhost:11434/v1"
        settings.llm_api_key = "test-key"
        settings.llm_model = "test-model"
        settings.llm_timeout = 120

        generate_letter(project, cv, settings=settings)

        mock_openai_cls.assert_called_once_with(
            base_url="http://localhost:11434/v1",
            api_key="test-key",
            timeout=120,
        )
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "test-model"
        assert len(call_kwargs.kwargs["messages"]) == 2
        assert call_kwargs.kwargs["messages"][0]["role"] == "system"
        assert call_kwargs.kwargs["messages"][1]["role"] == "user"

    @patch("src.letter_generator.OpenAI")
    def test_handles_none_usage(self, mock_openai_cls, project, cv):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = "Text"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "m"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response

        settings = MagicMock()
        settings.llm_base_url = "http://localhost:11434/v1"
        settings.llm_api_key = "x"
        settings.llm_model = "m"

        result = generate_letter(project, cv, settings=settings)
        assert result.prompt_tokens is None
        assert result.completion_tokens is None

    @patch("src.letter_generator.OpenAI")
    def test_empty_content_returns_empty_string(self, mock_openai_cls, project, cv):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_choice = MagicMock()
        mock_choice.message.content = None
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "m"
        mock_response.usage = None
        mock_client.chat.completions.create.return_value = mock_response

        settings = MagicMock()
        settings.llm_base_url = "http://localhost:11434/v1"
        settings.llm_api_key = "x"
        settings.llm_model = "m"

        result = generate_letter(project, cv, settings=settings)
        assert result.letter == ""


class TestFindRelevantExperience:
    def test_finds_matching_entries(self, cv):
        result = _find_relevant_experience(cv.experience, ["python", "docker"])
        assert len(result) == 1
        assert result[0].project == "REST-API-Plattform"

    def test_finds_multiple_entries(self, cv):
        result = _find_relevant_experience(cv.experience, ["python", "postgresql"])
        assert len(result) == 2

    def test_no_match_returns_empty(self, cv):
        result = _find_relevant_experience(cv.experience, ["java"])
        assert result == []

    def test_none_skills_returns_empty(self, cv):
        result = _find_relevant_experience(cv.experience, None)
        assert result == []

    def test_empty_experience_returns_empty(self):
        result = _find_relevant_experience([], ["python"])
        assert result == []

    def test_case_insensitive_matching(self, cv):
        result = _find_relevant_experience(cv.experience, ["Python", "Docker"])
        assert len(result) == 1


class TestFormatExperience:
    def test_formats_entries(self, cv):
        text = _format_experience(cv.experience[:1])
        assert "REST-API-Plattform" in text
        assert "Backend-Entwickler" in text
        assert "2021–2023" in text

    def test_empty_returns_no_experience_text(self):
        text = _format_experience([])
        assert "Keine passende Projekterfahrung" in text


class TestBuildUserPromptWithExperience:
    def test_contains_experience_section(self, project, cv):
        prompt = _build_user_prompt(project, cv, matched_skills=["python", "docker"])
        assert "RELEVANTE PROJEKTERFAHRUNG" in prompt
        assert "REST-API-Plattform" in prompt
        assert "Backend-Entwickler" in prompt

    def test_no_match_shows_no_experience(self, project, cv):
        prompt = _build_user_prompt(project, cv, matched_skills=["java"])
        assert "Keine passende Projekterfahrung" in prompt

    def test_contains_no_invention_instruction(self, project, cv):
        prompt = _build_user_prompt(project, cv, matched_skills=["python"])
        assert "Erfinde KEINE Erfahrungen" in prompt
