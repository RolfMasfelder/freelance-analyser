"""E-Mail-Abruf via IMAP — holt neue freelancermap-Benachrichtigungen."""

import email
import logging
from dataclasses import dataclass, field
from email.message import Message

from imapclient import IMAPClient

from src.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class RawEmail:
    """Eine abgerufene E-Mail mit UID, Betreff und Textinhalt."""

    uid: int
    subject: str
    sender: str
    body: str
    headers: dict[str, str] = field(default_factory=dict)


def _extract_body(msg: Message) -> str:
    """Extrahiert den Text-Body (plain text bevorzugt) aus einer E-Mail."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: erster text/html Part
        for part in msg.walk():
            if part.get_content_type() == "text/html":
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


def fetch_emails(
    settings: Settings | None = None,
    folder: str = "INBOX",
    mark_seen: bool = False,
    search_criteria: list[str] | None = None,
) -> list[RawEmail]:
    """Holt ungelesene E-Mails vom IMAP-Server.

    Args:
        settings: App-Konfiguration (wird aus .env geladen wenn None).
        folder: IMAP-Ordner.
        mark_seen: Wenn True, werden abgerufene Mails als gelesen markiert.
        search_criteria: IMAP-Suchkriterien. Default: UNSEEN + FROM freelancermap.

    Returns:
        Liste von RawEmail-Objekten.
    """
    if settings is None:
        settings = Settings()

    if search_criteria is None:
        search_criteria = ["UNSEEN", "FROM", "freelancermap"]

    results: list[RawEmail] = []

    with IMAPClient(
        host=settings.imap_host,
        port=settings.imap_port,
        ssl=settings.imap_ssl,
        timeout=30,
    ) as client:
        if getattr(settings, "imap_starttls", False) and not settings.imap_ssl:
            client.starttls()
        client.login(settings.imap_user, settings.imap_password)
        client.select_folder(folder, readonly=not mark_seen)

        uids = client.search(search_criteria)
        logger.info("Gefunden: %d E-Mails matching %s", len(uids), search_criteria)

        if not uids:
            return results

        messages = client.fetch(uids, ["RFC822"])

        for uid, data in messages.items():
            raw_bytes = data[b"RFC822"]
            msg = email.message_from_bytes(raw_bytes)

            raw_email = RawEmail(
                uid=uid,
                subject=str(msg.get("Subject", "")),
                sender=str(msg.get("From", "")),
                body=_extract_body(msg),
                headers={
                    "Date": str(msg.get("Date", "")),
                    "Message-ID": str(msg.get("Message-ID", "")),
                },
            )
            results.append(raw_email)
            logger.debug("E-Mail geholt: UID=%d Subject=%s", uid, raw_email.subject)

        if mark_seen:
            client.add_flags(uids, [b"\\Seen"])
            logger.info("%d E-Mails als gelesen markiert", len(uids))

    return results


def list_folders(settings: Settings | None = None) -> list[str]:
    """Listet alle verfügbaren IMAP-Ordner auf (Hilfsfunktion zum Debuggen)."""
    if settings is None:
        settings = Settings()

    with IMAPClient(
        host=settings.imap_host,
        port=settings.imap_port,
        ssl=settings.imap_ssl,
        timeout=30,
    ) as client:
        if getattr(settings, "imap_starttls", False) and not settings.imap_ssl:
            client.starttls()
        client.login(settings.imap_user, settings.imap_password)
        folders = client.list_folders()
        return [folder_name for _flags, _delimiter, folder_name in folders]
