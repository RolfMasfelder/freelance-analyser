"""Cookie-Management — Browser-Cookies für freelancermap.de auslesen."""

import logging
from http.cookiejar import CookieJar

import browser_cookie3
import httpx

logger = logging.getLogger(__name__)

FREELANCERMAP_DOMAIN = "freelancermap.de"
AUTH_CHECK_URL = "https://www.freelancermap.de/projektboerse.html"


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

    logger.info("Session-Check: Status %d", resp.status_code)
    return resp.status_code == 200


def get_authenticated_cookies() -> httpx.Cookies:
    """Liefert verifizierte httpx-Cookies für freelancermap.de.

    Raises:
        RuntimeError: Wenn keine gültige Session gefunden wird.

    Returns:
        httpx.Cookies mit gültiger Session.
    """
    cj = get_firefox_cookies()
    cookies = cookiejar_to_httpx(cj)

    if not verify_session(cookies):
        raise RuntimeError(
            "Firefox-Cookies für freelancermap.de sind ungültig. "
            "Bitte im Browser einloggen und erneut versuchen."
        )

    return cookies
