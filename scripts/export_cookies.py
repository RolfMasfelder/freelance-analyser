#!/usr/bin/env python3
"""Exportiert Firefox-Cookies für freelancermap.de in eine JSON-Datei.

Dieses Script auf dem HOST ausführen (nicht im Container),
damit der Container die Cookies nutzen kann.

Verwendung:
    python scripts/export_cookies.py
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cookie_manager import (
    export_cookies_to_file,
    load_cookies_from_file,
    verify_session,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    print("Exportiere Firefox-Cookies für freelancermap.de...")
    try:
        path = export_cookies_to_file()
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        print("Bitte im Firefox bei freelancermap.de einloggen.", file=sys.stderr)
        sys.exit(1)

    print(f"Cookies exportiert nach: {path}")

    # Verifizieren
    cookies = load_cookies_from_file(path)
    if verify_session(cookies):
        print("Session gültig — Container kann jetzt scrapen.")
    else:
        print("WARNUNG: Session ungültig — bitte im Browser neu einloggen.")
        sys.exit(1)


if __name__ == "__main__":
    main()
