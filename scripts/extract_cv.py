#!/usr/bin/env python3
"""CV-Extraktion — liest einen Lebenslauf (ODT) und generiert cv.yaml per LLM."""

import logging
import re
from pathlib import Path

import click
import yaml
from odf import teletype
from odf.opendocument import load as load_odt
from odf.text import P
from openai import OpenAI

from src.config import Settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Du bist ein Experte für die Analyse von Lebensläufen (CVs) im IT-Bereich. \
Deine Aufgabe ist es, aus einem gegebenen Lebenslauf strukturierte Daten \
zu extrahieren. Antworte ausschließlich mit validem YAML — kein Markdown, \
keine Erklärungen, keine Code-Fences.

Das YAML muss exakt folgende Struktur haben:

name: "Vollständiger Name"
title: "Berufsbezeichnung / Titel"
experience_years: <Zahl>

skills:
  - Skill1
  - Skill2

skills_secondary:
  - Skill1
  - Skill2

experience:
  - role: "Tatsächliche Rolle im Projekt"
    project: "Projektname oder -beschreibung"
    company: "Unternehmen / Kunde"
    period: "JJJJ–JJJJ"
    description: "Konkrete Tätigkeiten und Aufgaben im Projekt."
    skills:
      - Skill1
      - Skill2

preferred_locations:
  - Ort1
  - Remote
preferred_remote: "100%"
preferred_contract_types:
  - Freiberuflich
  - Contracting
min_duration_months: 3

exclude_skills:
  - SAP
  - ABAP
  - Cobol
  - Mainframe
  - .NET
exclude_industries: []

keywords:
  - keyword1
  - keyword2

Regeln:
- "skills" = primäre Skills aus dem aktuellen Schwerpunkt und jüngsten Projekten \
(max. 15-20). Das sind die Skills mit denen der Freelancer aktiv arbeitet.
- "skills_secondary" = alle weiteren genannten Skills, Technologien, Tools.
- "experience_years" = berechne aus dem frühesten genannten Berufsjahr bis heute (2026).
- "experience" = Projekthistorie / Berufserfahrung. WICHTIG:
  - "role" muss die TATSÄCHLICHE Rolle im Projekt sein \
(z.B. "Entwickler", "Berater", "Tester"), NICHT die gewünschte oder vermutete.
  - Wenn im CV nur "Mitarbeit" oder ähnlich steht, NICHT "Projektleiter" daraus machen.
  - "description" = die konkreten Tätigkeiten, die im CV für dieses Projekt genannt werden.
  - "skills" = die im Projekt eingesetzten Technologien/Skills.
  - Extrahiere die letzten 5–10 relevantesten Projekte.
- "keywords" = Themengebiete und Buzzwords die der Freelancer abdeckt \
(cloud, devops, backend, api, etc.) — kleingeschrieben.
- "preferred_locations" = wenn Wohnort oder Remote-Präferenz erkennbar.
- Schreibe Skill-Namen so wie in der Branche üblich \
(z.B. "PostgreSQL" nicht "postgres", "CI/CD" nicht "cicd").
- Gib NUR das YAML aus, nichts anderes.\
"""


def extract_text_from_odt(path: Path) -> str:
    """Extrahiert den Volltext aus einer ODT-Datei."""
    doc = load_odt(str(path))
    paragraphs = doc.getElementsByType(P)
    return "\n".join(teletype.extractText(p) for p in paragraphs)


def _strip_thinking(text: str) -> str:
    """Entfernt Reasoning-/Thinking-Blöcke aus der LLM-Antwort."""
    thinking_blocks = re.findall(r"<think>(.*?)</think>", text, flags=re.DOTALL)
    for block in thinking_blocks:
        log.debug("LLM-Thinking:\n%s", block.strip())
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


def _strip_code_fences(text: str) -> str:
    """Entfernt Markdown-Code-Fences falls das LLM welche generiert."""
    cleaned = re.sub(r"^```(?:ya?ml)?\s*\n", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\n```\s*$", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def extract_cv_via_llm(cv_text: str, settings: Settings) -> str:
    """Sendet den Lebenslauf-Text an das LLM und gibt das YAML zurück."""
    client = OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.llm_timeout,
    )
    # ┌─────────────────────┬──────────────┬──────────────────────────────────────────────┐
    # │ Parameter           │ Wertebereich │ Wirkung                                      │
    # ├─────────────────────┼──────────────┼──────────────────────────────────────────────┤
    # │ temperature         │ 0.0 – 2.0    │ Zufälligkeit der Token-Auswahl               │
    # │ max_tokens          │ 1 – ∞        │ Maximale Länge der Antwort in Tokens         │
    # │ frequency_penalty   │ -2.0 – 2.0   │ Bestraft häufig wiederholte Tokens           │
    # │ presence_penalty    │ -2.0 – 2.0   │ Bestraft bereits verwendete Tokens           │
    # │ top_p               │ 0.0 – 1.0    │ Nucleus Sampling (nicht mit temp variieren)  │
    # │ stop                │ [str, ...]   │ Stoppt bei Auftreten eines der Strings       │
    # │ n                   │ 1 – ∞        │ Anzahl alternativer Antworten                │
    # │ seed                │ int          │ Reproduzierbare Ergebnisse                   │
    # └─────────────────────┴──────────────┴──────────────────────────────────────────────┘
    #
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analysiere diesen Lebenslauf:\n\n{cv_text}"},
        ],
        temperature=0.3,
        max_tokens=8000,
        frequency_penalty=0.5,
    )

    raw = response.choices[0].message.content or ""
    cleaned = _strip_thinking(raw)
    cleaned = _strip_code_fences(cleaned)
    return cleaned


def validate_cv_yaml(yaml_text: str) -> dict:
    """Validiert das generierte YAML auf Pflichtfelder."""
    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict):
        raise ValueError("LLM-Ausgabe ist kein gültiges YAML-Dict")

    required = ["name", "skills"]
    missing = [f for f in required if f not in data or not data[f]]
    if missing:
        raise ValueError(f"Pflichtfelder fehlen im generierten YAML: {missing}")

    return data


@click.command()
@click.argument("odt_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("data/cv.yaml"),
    help="Ausgabepfad für die erzeugte cv.yaml.",
)
@click.option("--dry-run", is_flag=True, help="YAML nur anzeigen, nicht schreiben.")
def main(odt_path: Path, output: Path, dry_run: bool):
    """Extrahiert Skills aus einem Lebenslauf (ODT) und erzeugt cv.yaml.

    Beispiel:

        python scripts/extract_cv.py data/rma-Lebenslauf-2026.odt
        python scripts/extract_cv.py data/rma-Lebenslauf-2026.odt --dry-run
        python scripts/extract_cv.py data/rma-Lebenslauf-2026.odt -o data/cv_neu.yaml
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(message)s",
    )

    log.info("Lese ODT-Datei: %s", odt_path)
    cv_text = extract_text_from_odt(odt_path)
    log.info("Text extrahiert: %d Zeichen", len(cv_text))

    settings = Settings()
    log.info("Sende an LLM (%s @ %s) …", settings.llm_model, settings.llm_base_url)
    yaml_text = extract_cv_via_llm(cv_text, settings)

    data = validate_cv_yaml(yaml_text)
    skill_count = len(data.get("skills", [])) + len(data.get("skills_secondary", []))
    exp_count = len(data.get("experience", []))
    log.info(
        "Erkannte Skills: %d (primär: %d, sekundär: %d), Projekterfahrungen: %d",
        skill_count,
        len(data.get("skills", [])),
        len(data.get("skills_secondary", [])),
        exp_count,
    )

    if dry_run:
        click.echo("\n--- Generiertes YAML (dry-run) ---\n")
        click.echo(yaml_text)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml_text, encoding="utf-8")
    log.info("cv.yaml geschrieben: %s", output)


if __name__ == "__main__":
    main()
