"""Tests für email_fetcher — Unit-Tests mit gemocktem IMAP."""

import email.mime.text
from unittest.mock import MagicMock, patch

import pytest

from src.config import Settings
from src.email_fetcher import _extract_body, fetch_emails, list_folders


@pytest.fixture
def settings():
    return Settings(
        imap_host="imap.test.local",
        imap_port=993,
        imap_user="test@test.local",
        imap_password="secret",
        imap_ssl=True,
    )


def _make_raw_email(
    subject: str, body: str, sender: str = "noreply@freelancermap.de"
) -> bytes:
    """Erzeugt eine minimale RFC822-E-Mail als bytes."""
    msg = email.mime.text.MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["Date"] = "Mon, 10 Mar 2026 09:00:00 +0100"
    msg["Message-ID"] = "<test@local>"
    return msg.as_bytes()


class TestExtractBody:
    def test_plain_text(self):
        msg = email.mime.text.MIMEText("Hello World", "plain", "utf-8")
        assert _extract_body(msg) == "Hello World"

    def test_empty_payload(self):
        msg = email.message_from_string("")
        assert _extract_body(msg) == ""


class TestFetchEmails:
    @patch("src.email_fetcher.IMAPClient")
    def test_fetch_returns_emails(self, mock_imap_cls, settings):
        raw = _make_raw_email(
            "Neues Projekt",
            "Python Entwickler gesucht\nhttps://www.freelancermap.de/nproj/123.html",
        )

        mock_client = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.search.return_value = [101]
        mock_client.fetch.return_value = {101: {b"RFC822": raw}}

        results = fetch_emails(settings=settings)

        assert len(results) == 1
        assert results[0].uid == 101
        assert "Python Entwickler" in results[0].body
        assert results[0].subject == "Neues Projekt"
        mock_client.login.assert_called_once_with("test@test.local", "secret")

    @patch("src.email_fetcher.IMAPClient")
    def test_fetch_no_results(self, mock_imap_cls, settings):
        mock_client = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.search.return_value = []

        results = fetch_emails(settings=settings)
        assert results == []

    @patch("src.email_fetcher.IMAPClient")
    def test_fetch_marks_seen(self, mock_imap_cls, settings):
        raw = _make_raw_email("Test", "Body")

        mock_client = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.search.return_value = [200]
        mock_client.fetch.return_value = {200: {b"RFC822": raw}}

        fetch_emails(settings=settings, mark_seen=True)

        mock_client.select_folder.assert_called_once_with("INBOX", readonly=False)
        mock_client.add_flags.assert_called_once_with([200], [b"\\Seen"])


class TestListFolders:
    @patch("src.email_fetcher.IMAPClient")
    def test_list_folders(self, mock_imap_cls, settings):
        mock_client = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_client.list_folders.return_value = [
            ([], b"/", "INBOX"),
            ([], b"/", "Sent"),
        ]

        folders = list_folders(settings=settings)
        assert folders == ["INBOX", "Sent"]
