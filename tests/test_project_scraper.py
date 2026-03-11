"""Tests für project_scraper — Unit-Tests mit gemocktem HTTP."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.project_scraper import (
    _extract_id_from_url,
    scrape_project_page,
)


class TestExtractIdFromUrl:
    def test_valid_url(self):
        assert (
            _extract_id_from_url("https://www.freelancermap.de/nproj/2977008.html")
            == "2977008"
        )

    def test_with_params(self):
        assert (
            _extract_id_from_url("https://www.freelancermap.de/nproj/123.html?foo=bar")
            == "123"
        )


class TestScrapeProjectPage:
    @patch("src.project_scraper.httpx.Client")
    def test_successful_scrape(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body>Projektseite</body></html>"
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        cookies = httpx.Cookies()
        html = scrape_project_page(
            "https://www.freelancermap.de/nproj/123.html", cookies=cookies
        )
        assert "Projektseite" in html

    @patch("src.project_scraper.httpx.Client")
    def test_login_redirect_raises(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.headers = {"location": "https://www.freelancermap.de/login.html"}

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        cookies = httpx.Cookies()
        with pytest.raises(RuntimeError, match="Session ungültig"):
            scrape_project_page(
                "https://www.freelancermap.de/nproj/123.html", cookies=cookies
            )
