"""Antwortschreiben-Generator — erstellt Bewerbungsschreiben per LLM."""

import logging
import re
from dataclasses import dataclass

from openai import OpenAI

from src.config import Settings
from src.cv_manager import CVProfile
from src.database import Project

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Du bist ein erfahrener Freelance-Berater, der professionelle Antwortschreiben \
auf Projektausschreibungen verfasst. Du schreibst auf Deutsch, sachlich und \
überzeugend. Das Schreiben soll:
- Die relevanten Skills und Erfahrungen des Freelancers hervorheben, \
die zum Projekt passen
- Konkret auf die Projektanforderungen eingehen
- Kurz und prägnant sein (max. 300 Wörter)
- Professionell aber nicht übertrieben förmlich klingen
- Keine erfundenen Qualifikationen oder Erfahrungen enthalten
- Nur Skills erwähnen, die der Freelancer tatsächlich hat
"""


def _build_user_prompt(
    project: Project, cv: CVProfile, matched_skills: list[str] | None = None
) -> str:
    """Baut den User-Prompt aus Projektdaten und CV zusammen."""
    skills_text = ", ".join(cv.skills) if cv.skills else "–"
    secondary_text = ", ".join(cv.skills_secondary) if cv.skills_secondary else "–"
    matched_text = ", ".join(matched_skills) if matched_skills else "–"
    project_skills_text = ", ".join(project.skills) if project.skills else "–"

    return f"""\
Erstelle ein Antwortschreiben für folgendes Freelance-Projekt.

## PROJEKT
- Titel: {project.title}
- Unternehmen: {project.company or "nicht angegeben"}
- Standort: {project.location or "nicht angegeben"}
- Remote: {project.remote or "nicht angegeben"}
- Vertragsart: {project.contract_type or "nicht angegeben"}
- Start: {project.start or "nicht angegeben"}
- Laufzeit: {project.duration or "nicht angegeben"}
- Geforderte Skills: {project_skills_text}
- Beschreibung: {project.description or "keine Beschreibung"}

## FREELANCER
- Name: {cv.name}
- Titel: {cv.title}
- Phone: {cv.phone or "nicht angegeben"}
- Email: {cv.email or "nicht angegeben"}
- Erfahrung: {cv.experience_years} Jahre
- Primäre Skills: {skills_text}
- Sekundäre Skills: {secondary_text}
- Passende Skills (CV ∩ Projekt): {matched_text}

Schreibe ein professionelles Antwortschreiben, das die passenden Skills \
hervorhebt und konkret auf die Projektanforderungen eingeht.\
"""


@dataclass
class LetterResult:
    """Ergebnis der Schreiben-Generierung."""

    letter: str
    model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


def _strip_thinking(text: str) -> str:
    """Entfernt Reasoning-/Thinking-Blöcke aus der LLM-Antwort und loggt sie."""
    thinking_blocks = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL)
    for block in thinking_blocks:
        log.debug("LLM-Thinking:\n%s", block.strip())
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


def generate_letter(
    project: Project,
    cv: CVProfile,
    matched_skills: list[str] | None = None,
    settings: Settings | None = None,
) -> LetterResult:
    """Generiert ein Antwortschreiben per LLM.

    Unterstützt Ollama (lokal), OpenAI, Groq, Google Gemini —
    jeder OpenAI-kompatible Endpunkt funktioniert.
    """
    if settings is None:
        settings = Settings()

    client = OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
    )

    user_prompt = _build_user_prompt(project, cv, matched_skills)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=10000,
    )

    choice = response.choices[0]
    usage = response.usage
    raw_content = choice.message.content or ""

    return LetterResult(
        letter=_strip_thinking(raw_content),
        model=response.model,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
    )
