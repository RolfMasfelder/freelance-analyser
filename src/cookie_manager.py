"""Cookie-Management — Browser-Cookies für freelancermap.de auslesen."""

import json
import logging
from http.cookiejar import CookieJar
from pathlib import Path

import browser_cookie3
import httpx

logger = logging.getLogger(__name__)

FREELANCERMAP_DOMAIN = "freelancermap.de"
AUTH_CHECK_URL = "https://www.freelancermap.de/projekte"
COOKIE_FILE = Path(__file__).parent.parent / "data/cookies/freelancermap.json"


def get_firefox_cookies(domain: str = FREELANCERMAP_DOMAIN) -> CookieJar:
    """Liest Cookies für eine Domain aus Firefox.

    Args:
        domain: Domain-Filter für die Cookies.

    Returns:
        CookieJar mit den gefundenen Cookies.

    Raises:
        RuntimeError: Wenn keine Cookies gefunden werden.
    """
    cj = browser_cookie3.firefox(domain_name=domain)
    count = sum(1 for _ in cj)
    if count == 0:
        raise RuntimeError(f"Keine Firefox-Cookies für {domain} gefunden")
    logger.info("Firefox-Cookies geladen: %d Cookies für %s", count, domain)
    return cj


def cookiejar_to_httpx(cj: CookieJar) -> httpx.Cookies:
    """Konvertiert ein CookieJar in httpx.Cookies."""
    cookies = httpx.Cookies()
    for cookie in cj:
        cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
    return cookies


def verify_session(cookies: httpx.Cookies | CookieJar | None = None) -> bool:
    """Prüft ob die Cookies eine gültige Session darstellen.

    Macht einen Request auf die Projektbörse und prüft ob ein Redirect
    zum Login erfolgt (= nicht authentifiziert) oder die Seite geladen wird.

    Args:
        cookies: Cookies zum Testen. Wenn None, werden sie aus Firefox geladen.

    Returns:
        True wenn die Session gültig ist.
    """
    if cookies is None:
        cj = get_firefox_cookies()
        cookies = cookiejar_to_httpx(cj)
    elif isinstance(cookies, CookieJar):
        cookies = cookiejar_to_httpx(cookies)

    with httpx.Client(cookies=cookies, follow_redirects=False, timeout=30) as client:
        resp = client.get(AUTH_CHECK_URL)

    if resp.status_code == 200:
        logger.info("Session gültig (Status 200)")
        return True

    if resp.status_code in (301, 302):
        location = resp.headers.get("location", "")
        if "login" in location.lower():
            logger.warning("Session ungültig — Redirect zu Login: %s", location)
            return False

    logger.warning("Session-Check: unerwarteter Status %d", resp.status_code)
    return False


def get_authenticated_cookies() -> httpx.Cookies:
    """Liefert verifizierte httpx-Cookies für freelancermap.de.

    Versucht zuerst die Cookie-Datei zu laden (für Container-Betrieb),
    fällt auf Browser-Cookies zurück (für Host-Betrieb).

    Raises:
        RuntimeError: Wenn keine gültige Session gefunden wird.

    Returns:
        httpx.Cookies mit gültiger Session.
    """
    # 1. Cookie-Datei vorhanden? (Container-Modus)
    if COOKIE_FILE.exists():
        logger.info("Lade Cookies aus %s", COOKIE_FILE)
        cookies = load_cookies_from_file(COOKIE_FILE)
        if verify_session(cookies):
            return cookies
        logger.warning("Cookie-Datei vorhanden aber Session ungültig")

    # 2. Browser-Cookies (Host-Modus)
    try:
        cj = get_firefox_cookies()
        cookies = cookiejar_to_httpx(cj)
        if verify_session(cookies):
            return cookies
    except Exception as e:
        logger.warning("Browser-Cookies nicht verfügbar: %s", e)

    raise RuntimeError(
        "Keine gültige Session gefunden. "
        "Im Container: 'python scripts/export_cookies.py' auf dem Host ausführen. "
        "Auf dem Host: Im Browser bei freelancermap.de einloggen."
    )


def export_cookies_to_file(path: Path = COOKIE_FILE) -> Path:
    """Exportiert Firefox-Cookies in eine JSON-Datei.

    Zum Ausführen auf dem Host, damit der Container die Cookies nutzen kann.

    Returns:
        Pfad zur geschriebenen Datei.
    """
    cj = get_firefox_cookies()
    cookies_list = [
        {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
        for c in cj
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cookies_list, indent=2), encoding="utf-8")
    logger.info("%d Cookies nach %s exportiert", len(cookies_list), path)
    return path


def load_cookies_from_file(path: Path = COOKIE_FILE) -> httpx.Cookies:
    """Lädt Cookies aus einer JSON-Datei.

    Returns:
        httpx.Cookies mit den geladenen Cookies.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    cookies = httpx.Cookies()
    for entry in data:
        cookies.set(
            entry["name"],
            entry["value"],
            domain=entry.get("domain", ""),
            path=entry.get("path", "/"),
        )
    logger.info("%d Cookies aus %s geladen", len(data), path)
    return cookies
