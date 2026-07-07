"""Antwortschreiben-Generator — erstellt Bewerbungsschreiben per LLM."""

import logging
import re
from dataclasses import dataclass

from openai import OpenAI

from src.config import Settings
from src.cv_manager import CVProfile, ExperienceEntry
from src.database import Project

log = logging.getLogger(__name__)

_LANGUAGE_LABELS = {"de": "Deutsch", "en": "Englisch"}


def _language_label(code: str) -> str:
    """Wandelt ISO-639-1 Sprachcode in lesbaren Namen."""
    return _LANGUAGE_LABELS.get(code, "Deutsch")


SYSTEM_PROMPT = """\
Du bist ein erfahrener Freelance-Berater, der professionelle Antwortschreiben \
auf Projektausschreibungen verfasst. Du schreibst sachlich und \
überzeugend. Das Schreiben soll:
- Die relevanten Skills und Erfahrungen des Freelancers hervorheben, \
die zum Projekt passen
- Konkret auf die Projektanforderungen eingehen
- Kurz und prägnant sein (max. 350 Wörter)
- Professionell aber nicht übertrieben förmlich klingen

WICHTIG — Strenge Regeln für Erfahrungsangaben:
- Verwende AUSSCHLIESSLICH die unter "RELEVANTE PROJEKTERFAHRUNG" \
aufgeführten Erfahrungen als Grundlage.
- Erwähne NUR die dort genannte Rolle (z.B. "Entwickler", "Berater"). \
Erfinde KEINE höherwertigen Rollen (z.B. "Projektleiter", "Architekt"), \
wenn diese nicht explizit in den Erfahrungen stehen.
- Übertreibe NICHT den Umfang oder die Komplexität der früheren Tätigkeiten.
- Wenn keine passende Projekterfahrung vorhanden ist, erwähne nur \
die vorhandenen Skills ohne konkreten Projektzusammenhang.
- Erfinde KEINE Qualifikationen, Zertifikate oder Erfahrungen.

WICHTIG — Sprache:
- Schreibe das Antwortschreiben in {language}.
"""


def _find_relevant_experience(
    experience: list[ExperienceEntry], matched_skills: list[str] | None
) -> list[ExperienceEntry]:
    """Filtert Erfahrungseinträge, die zu den gematchten Skills passen."""
    if not experience or not matched_skills:
        return []
    matched_lower = {s.lower() for s in matched_skills}
    relevant = []
    for entry in experience:
        entry_skills = {s.lower() for s in entry.skills}
        if entry_skills & matched_lower:
            relevant.append(entry)
    return relevant


def _format_experience(entries: list[ExperienceEntry]) -> str:
    """Formatiert Erfahrungseinträge als Text für den Prompt."""
    if not entries:
        return "Keine passende Projekterfahrung vorhanden."
    parts = []
    for entry in entries:
        skills_text = ", ".join(entry.skills) if entry.skills else "–"
        parts.append(
            f"- Projekt: {entry.project}\n"
            f"  Rolle: {entry.role}\n"
            f"  Zeitraum: {entry.period or 'k.A.'}\n"
            f"  Beschreibung: {entry.description}\n"
            f"  Skills: {skills_text}"
        )
    return "\n".join(parts)


def _build_user_prompt(
    project: Project, cv: CVProfile, matched_skills: list[str] | None = None
) -> str:
    """Baut den User-Prompt aus Projektdaten und CV zusammen."""
    skills_text = ", ".join(cv.skills) if cv.skills else "–"
    secondary_text = ", ".join(cv.skills_secondary) if cv.skills_secondary else "–"
    matched_text = ", ".join(matched_skills) if matched_skills else "–"
    project_skills_text = ", ".join(project.skills) if project.skills else "–"

    relevant_exp = _find_relevant_experience(cv.experience, matched_skills)
    experience_text = _format_experience(relevant_exp)

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

## RELEVANTE PROJEKTERFAHRUNG
{experience_text}

Schreibe ein professionelles Antwortschreiben basierend auf den oben \
aufgeführten tatsächlichen Erfahrungen. Verwende NUR Rollen und Tätigkeiten, \
die in der Projekterfahrung explizit genannt werden. Erfinde KEINE Erfahrungen.\
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


def _mask_api_key(key: str) -> str:
    """Maskiert einen API-Key für Log-Ausgaben (zeigt nur die letzten 4 Zeichen)."""
    if not key:
        return "<leer>"
    if len(key) <= 4:
        return "*" * len(key)
    return f"{'*' * (len(key) - 4)}{key[-4:]}"


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

    log.info(
        "LLM-Aufruf: base_url=%s model=%s api_key=%s",
        settings.llm_base_url,
        settings.llm_model,
        _mask_api_key(settings.llm_api_key),
    )

    client = OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
    )

    user_prompt = _build_user_prompt(project, cv, matched_skills)

    log.debug("Sende Chat-Completion-Request an LLM …")
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(
                    language=_language_label(getattr(project, "language", "de")),
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=10000,
    )
    log.debug("Chat-Completion-Request zurückgekehrt, verarbeite Antwort …")

    choice = response.choices[0]
    usage = response.usage
    raw_content = choice.message.content or ""
    log.debug("Antwort verarbeitet (%d Zeichen), baue LetterResult …", len(raw_content))

    result = LetterResult(
        letter=_strip_thinking(raw_content),
        model=response.model,
        prompt_tokens=usage.prompt_tokens if usage else None,
        completion_tokens=usage.completion_tokens if usage else None,
    )
    log.debug("LetterResult fertig, gebe an Aufrufer zurück.")
    return result
