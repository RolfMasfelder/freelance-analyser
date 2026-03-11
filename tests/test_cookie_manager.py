"""Tests für cookie_manager — Unit-Tests mit gemocktem Browser + Live-Tests."""

from http.cookiejar import CookieJar
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.cookie_manager import (
    cookiejar_to_httpx,
    get_authenticated_cookies,
    get_firefox_cookies,
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
    @patch("src.cookie_manager.verify_session", return_value=True)
    @patch("src.cookie_manager.get_firefox_cookies")
    @patch("src.cookie_manager.cookiejar_to_httpx")
    def test_success(self, mock_convert, mock_get, mock_verify):
        mock_cookies = httpx.Cookies()
        mock_convert.return_value = mock_cookies

        result = get_authenticated_cookies()
        assert result is mock_cookies

    @patch("src.cookie_manager.verify_session", return_value=False)
    @patch("src.cookie_manager.get_firefox_cookies")
    @patch("src.cookie_manager.cookiejar_to_httpx")
    def test_raises_if_invalid(self, mock_convert, mock_get, mock_verify):
        mock_convert.return_value = httpx.Cookies()

        with pytest.raises(RuntimeError, match="ungültig"):
            get_authenticated_cookies()
