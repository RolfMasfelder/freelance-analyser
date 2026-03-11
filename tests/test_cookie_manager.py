"""Tests für cookie_manager — Unit-Tests mit gemocktem Browser + Live-Tests."""

import json
from http.cookiejar import CookieJar
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.cookie_manager import (
    cookiejar_to_httpx,
    export_cookies_to_file,
    get_authenticated_cookies,
    get_firefox_cookies,
    load_cookies_from_file,
    verify_session,
)


def _make_cookie(name: str, value: str, domain: str = ".freelancermap.de") -> MagicMock:
    cookie = MagicMock()
    cookie.name = name
    cookie.value = value
    cookie.domain = domain
    cookie.path = "/"
    return cookie


def _make_cookiejar(*cookies) -> CookieJar:
    cj = CookieJar()
    for c in cookies:
        cj.set_cookie(c)
    return cj


class TestGetFirefoxCookies:
    @patch("src.cookie_manager.browser_cookie3.firefox")
    def test_returns_cookies(self, mock_firefox):
        mock_cj = MagicMock(spec=CookieJar)
        mock_cj.__iter__ = MagicMock(
            return_value=iter([_make_cookie("PHPSESSID", "abc123")])
        )
        mock_firefox.return_value = mock_cj

        result = get_firefox_cookies()
        assert result is mock_cj
        mock_firefox.assert_called_once_with(domain_name="freelancermap.de")

    @patch("src.cookie_manager.browser_cookie3.firefox")
    def test_raises_if_empty(self, mock_firefox):
        mock_cj = MagicMock(spec=CookieJar)
        mock_cj.__iter__ = MagicMock(return_value=iter([]))
        mock_firefox.return_value = mock_cj

        with pytest.raises(RuntimeError, match="Keine Firefox-Cookies"):
            get_firefox_cookies()


class TestCookiejarToHttpx:
    def test_converts_cookies(self):
        cookie = _make_cookie("PHPSESSID", "abc123")
        cj = MagicMock(spec=CookieJar)
        cj.__iter__ = MagicMock(return_value=iter([cookie]))

        result = cookiejar_to_httpx(cj)
        assert isinstance(result, httpx.Cookies)
        assert result.get("PHPSESSID") == "abc123"


class TestVerifySession:
    @patch("src.cookie_manager.httpx.Client")
    def test_valid_session(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        cookies = httpx.Cookies()
        cookies.set("PHPSESSID", "valid")
        assert verify_session(cookies) is True

    @patch("src.cookie_manager.httpx.Client")
    def test_invalid_session_redirect(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.headers = {"location": "https://www.freelancermap.de/login.html"}
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        cookies = httpx.Cookies()
        assert verify_session(cookies) is False


class TestGetAuthenticatedCookies:
    @patch("src.cookie_manager.COOKIE_FILE")
    @patch("src.cookie_manager.verify_session", return_value=True)
    @patch("src.cookie_manager.load_cookies_from_file")
    def test_prefers_cookie_file(self, mock_load, mock_verify, mock_path):
        mock_path.exists.return_value = True
        mock_cookies = httpx.Cookies()
        mock_load.return_value = mock_cookies

        result = get_authenticated_cookies()
        assert result is mock_cookies
        mock_load.assert_called_once()

    @patch("src.cookie_manager.COOKIE_FILE")
    @patch("src.cookie_manager.verify_session", return_value=True)
    @patch("src.cookie_manager.cookiejar_to_httpx")
    @patch("src.cookie_manager.get_firefox_cookies")
    def test_fallback_to_browser(self, mock_get, mock_convert, mock_verify, mock_path):
        mock_path.exists.return_value = False
        mock_cookies = httpx.Cookies()
        mock_convert.return_value = mock_cookies

        result = get_authenticated_cookies()
        assert result is mock_cookies
        mock_get.assert_called_once()

    @patch("src.cookie_manager.COOKIE_FILE")
    @patch(
        "src.cookie_manager.get_firefox_cookies", side_effect=Exception("no browser")
    )
    def test_raises_if_nothing_works(self, mock_get, mock_path):
        mock_path.exists.return_value = False

        with pytest.raises(RuntimeError, match="Keine gültige Session"):
            get_authenticated_cookies()


class TestCookieFileRoundtrip:
    def test_export_and_load(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        cookie = _make_cookie("PHPSESSID", "abc123")

        with patch("src.cookie_manager.get_firefox_cookies") as mock_get:
            mock_cj = MagicMock(spec=CookieJar)
            mock_cj.__iter__ = MagicMock(return_value=iter([cookie]))
            mock_get.return_value = mock_cj

            path = export_cookies_to_file(cookie_file)

        assert path.exists()
        data = json.loads(path.read_text())
        assert len(data) == 1
        assert data[0]["name"] == "PHPSESSID"

        loaded = load_cookies_from_file(path)
        assert loaded.get("PHPSESSID") == "abc123"
