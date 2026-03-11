#!/usr/bin/env python3
"""Schnelltest: IMAP-Verbindung prüfen und Ordner / E-Mails auflisten."""

import logging
import sys

from src.config import Settings
from src.email_fetcher import fetch_emails, list_folders

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")


def main():
    settings = Settings()
    print(f"IMAP: {settings.imap_user}@{settings.imap_host}:{settings.imap_port}")

    if "--folders" in sys.argv:
        print("\n--- Verfügbare Ordner ---")
        for f in list_folders(settings):
            print(f"  {f}")
        return

    print("\n--- Ungelesene freelancermap-Mails ---")
    emails = fetch_emails(settings=settings)
    if not emails:
        print("  Keine neuen E-Mails gefunden.")
    for mail in emails:
        print(f"  UID={mail.uid} | {mail.subject}")
        print(f"    Von: {mail.sender}")
        print(f"    Body (erste 200 Zeichen): {mail.body[:200]}")
        print()


if __name__ == "__main__":
    main()
