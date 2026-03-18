"""CV-Manager — Lebenslauf laden, strukturieren und Skills extrahieren."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ExperienceEntry:
    """Ein Eintrag aus der Projekthistorie / Berufserfahrung."""

    role: str
    project: str
    description: str
    skills: list[str] = field(default_factory=list)
    company: str = ""
    period: str = ""


@dataclass
class CVProfile:
    """Strukturierter Lebenslauf mit Skills und Präferenzen."""

    name: str = ""
    title: str = ""
    phone: str | None = None
    email: str | None = None
    skills: list[str] = field(default_factory=list)
    skills_secondary: list[str] = field(default_factory=list)
    experience_years: int = 0
    experience: list[ExperienceEntry] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    preferred_remote: str = ""
    preferred_contract_types: list[str] = field(default_factory=list)
    exclude_skills: list[str] = field(default_factory=list)
    exclude_industries: list[str] = field(default_factory=list)
    min_duration_months: int = 0
    keywords: list[str] = field(default_factory=list)

    @property
    def all_skills(self) -> list[str]:
        """Alle Skills (primär + sekundär)."""
        return self.skills + self.skills_secondary


def load_cv(path: str | Path) -> CVProfile:
    """Lädt einen Lebenslauf aus einer YAML-Datei.

    Args:
        path: Pfad zur YAML-Datei.

    Returns:
        CVProfile mit allen geladenen Daten.

    Raises:
        FileNotFoundError: Wenn die Datei nicht existiert.
        ValueError: Wenn die YAML-Datei ungültig ist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"CV-Datei nicht gefunden: {path}")

    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    if not isinstance(data, dict):
        raise ValueError(f"Ungültiges CV-Format in {path}: Erwartet ein YAML-Dict")

    logger.info("CV geladen: %s (%d Skills)", path.name, len(data.get("skills", [])))

    experience_entries = []
    for entry in data.get("experience", []):
        experience_entries.append(
            ExperienceEntry(
                role=entry.get("role", ""),
                project=entry.get("project", ""),
                description=entry.get("description", ""),
                skills=[s.lower() for s in entry.get("skills", [])],
                company=entry.get("company", ""),
                period=entry.get("period", ""),
            )
        )

    return CVProfile(
        name=data.get("name", ""),
        title=data.get("title", ""),
        skills=[s.lower() for s in data.get("skills", [])],
        skills_secondary=[s.lower() for s in data.get("skills_secondary", [])],
        experience_years=data.get("experience_years", 0),
        experience=experience_entries,
        preferred_locations=data.get("preferred_locations", []),
        preferred_remote=data.get("preferred_remote", ""),
        preferred_contract_types=data.get("preferred_contract_types", []),
        exclude_skills=[s.lower() for s in data.get("exclude_skills", [])],
        exclude_industries=[s.lower() for s in data.get("exclude_industries", [])],
        min_duration_months=data.get("min_duration_months", 0),
        keywords=[k.lower() for k in data.get("keywords", [])],
    )
