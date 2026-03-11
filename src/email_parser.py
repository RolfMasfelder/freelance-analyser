"""E-Mail-Parser — extrahiert Projekteinträge und Links aus freelancermap-Mails."""

import email
import mailbox
import quopri
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectEntry:
    """Ein aus der E-Mail extrahierter Projekteintrag."""

    title: str
    created: str
    company: str
    location: str
    contract_type: str
    remote: str
    start: str
    url: str
    project_id: int


def _decode_quoted_printable(text: str) -> str:
    """Dekodiert quoted-printable Soft-Line-Breaks und Entities."""
    # Soft line breaks entfernen (=\n)
    text = text.replace("=\n", "")
    # QP-Entities dekodieren (=C3=BC → ü etc.)
    try:
        text = quopri.decodestring(text.encode("ascii", errors="replace")).decode("utf-8", errors="replace")
    except Exception:
        pass
    return text


def _extract_project_id(url: str) -> int:
    """Extrahiert die Projekt-ID aus einer freelancermap-URL."""
    match = re.search(r"/nproj/(\d+)\.html", url)
    return int(match.group(1)) if match else 0


def _clean_url(url: str) -> str:
    """Bereinigt URL — entfernt Tracking-Parameter, behält Basis-URL."""
    match = re.match(r"(https://www\.freelancermap\.de/nproj/\d+\.html)", url)
    return match.group(1) if match else url


def parse_email_body(body: str) -> list[ProjectEntry]:
    """Parst den Textinhalt einer freelancermap-E-Mail in Projekteinträge.

    Args:
        body: Roh-Body der E-Mail (kann noch quoted-printable-kodiert sein).

    Returns:
        Liste von ProjectEntry-Objekten.
    """
    decoded = _decode_quoted_printable(body)

    # Projektblöcke sind durch "----...----" getrennt
    # Erster Block nach der Begrüßung enthält das erste Projekt
    blocks = re.split(r"-{10,}", decoded)

    projects: list[ProjectEntry] = []

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Ein Projektblock muss eine freelancermap-URL enthalten
        url_match = re.search(
            r"(https://www\.freelancermap\.de/nproj/\d+\.html[^\s]*)", block
        )
        if not url_match:
            continue

        url = _clean_url(url_match.group(1))
        project_id = _extract_project_id(url)

        # Felder extrahieren
        lines = block.split("\n")

        title = ""
        created = ""
        company = ""
        location = ""
        contract_type = ""
        remote = ""
        start = ""

        # Titel = alles vor "Erstellt:"
        title_parts = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Erstellt:"):
                created = stripped.removeprefix("Erstellt:").strip()
                break
            if stripped and not stripped.startswith("Hallo") and not stripped.startswith("unser Projektagent"):
                title_parts.append(stripped)
        title = " ".join(title_parts).strip()
        # Trailing whitespace-Marker entfernen
        title = re.sub(r"\s+$", "", title)

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("von:"):
                company = stripped.removeprefix("von:").strip()
            elif stripped.startswith("Ort:"):
                location = stripped.removeprefix("Ort:").strip()
            elif stripped.startswith("Vertragsart:"):
                contract_type = stripped.removeprefix("Vertragsart:").strip()
            elif stripped.startswith("Remote:"):
                remote = stripped.removeprefix("Remote:").strip()
            elif stripped.startswith("Start:"):
                start = stripped.removeprefix("Start:").strip()

        if title and project_id:
            projects.append(
                ProjectEntry(
                    title=title,
                    created=created,
                    company=company,
                    location=location,
                    contract_type=contract_type,
                    remote=remote,
                    start=start,
                    url=url,
                    project_id=project_id,
                )
            )

    return projects


def parse_mbox_file(path: str | Path) -> list[ProjectEntry]:
    """Liest eine mbox-Datei und extrahiert alle Projekteinträge.

    Args:
        path: Pfad zur .mbox-Datei.

    Returns:
        Liste aller Projekteinträge aus allen E-Mails in der mbox.
    """
    mbox = mailbox.mbox(str(path))
    all_projects: list[ProjectEntry] = []

    for msg in mbox:
        body = _extract_text_body(msg)
        if body:
            projects = parse_email_body(body)
            all_projects.extend(projects)

    return all_projects


def _extract_text_body(msg: email.message.Message) -> str:
    """Extrahiert den text/plain-Body aus einer E-Mail-Message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    return ""
