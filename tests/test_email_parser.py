"""Tests für email_parser — Unit-Tests + Integration mit echter mbox."""

from pathlib import Path

import pytest

from src.email_parser import (
    ProjectEntry,
    _clean_url,
    _decode_quoted_printable,
    _extract_project_id,
    parse_email_body,
    parse_mbox_file,
)

SAMPLE_MBOX = Path("data/raw_emails/Agent_Oracle_Java_Python_PostgreSQL_KI - Anzahl neue Projekte_100.mbox")


class TestDecodeQuotedPrintable:
    def test_soft_line_break(self):
        text = "Hallo=\n Welt"
        assert _decode_quoted_printable(text) == "Hallo Welt"

    def test_utf8_entity(self):
        text = "M=C3=BCnchen"
        assert _decode_quoted_printable(text) == "München"

    def test_plain_text(self):
        assert _decode_quoted_printable("Hallo Welt") == "Hallo Welt"


class TestExtractProjectId:
    def test_valid_url(self):
        url = "https://www.freelancermap.de/nproj/2977008.html?utm_source=foo"
        assert _extract_project_id(url) == 2977008

    def test_clean_url(self):
        url = "https://www.freelancermap.de/nproj/2977008.html"
        assert _extract_project_id(url) == 2977008

    def test_no_match(self):
        assert _extract_project_id("https://example.com") == 0


class TestCleanUrl:
    def test_strips_tracking_params(self):
        url = "https://www.freelancermap.de/nproj/2977008.html?utm_source=systemmail&utm_medium=email"
        assert _clean_url(url) == "https://www.freelancermap.de/nproj/2977008.html"

    def test_already_clean(self):
        url = "https://www.freelancermap.de/nproj/2977008.html"
        assert _clean_url(url) == "https://www.freelancermap.de/nproj/2977008.html"


class TestParseEmailBody:
    SAMPLE_BODY = """Hallo Rolf Masfelder,

unser Projektagent hat neue Aufträge zu Ihrer gespeicherten Suche gefunden:


Betrieb & Weiterentwicklung (.NET/C#) Aurea CRM
Erstellt: 10.03.2026 um 09:52 Uhr
von: Target Networks GmbH
Ort: Berlin
Vertragsart: Freiberuflich
Remote: 100 %
Start: 4/2026

https://www.freelancermap.de/nproj/2977008.html?utm_source=systemmail&utm_medium=email

-----------------------------

Fullstack Entwickler (m/w/d) mit Testautomatisierung
Erstellt: 10.03.2026 um 09:26 Uhr
von: iSAX Consulting GmbH
Ort: Frankfurt am Main
Vertragsart: Freiberuflich
Remote: 100 %
Start: 4/2026

https://www.freelancermap.de/nproj/2976991.html?utm_source=systemmail

-----------------------------
"""

    def test_parse_two_projects(self):
        projects = parse_email_body(self.SAMPLE_BODY)
        assert len(projects) == 2

    def test_first_project_fields(self):
        projects = parse_email_body(self.SAMPLE_BODY)
        p = projects[0]
        assert p.project_id == 2977008
        assert "Aurea CRM" in p.title
        assert p.company == "Target Networks GmbH"
        assert p.location == "Berlin"
        assert p.contract_type == "Freiberuflich"
        assert p.remote == "100 %"
        assert p.start == "4/2026"
        assert p.url == "https://www.freelancermap.de/nproj/2977008.html"

    def test_second_project_fields(self):
        projects = parse_email_body(self.SAMPLE_BODY)
        p = projects[1]
        assert p.project_id == 2976991
        assert "Fullstack" in p.title
        assert p.company == "iSAX Consulting GmbH"

    def test_empty_body(self):
        assert parse_email_body("") == []

    def test_no_projects(self):
        assert parse_email_body("Hallo Welt, keine Projekte hier.") == []


@pytest.mark.skipif(not SAMPLE_MBOX.exists(), reason="Beispiel-mbox nicht vorhanden")
class TestParseMboxFile:
    def test_parse_real_mbox(self):
        projects = parse_mbox_file(SAMPLE_MBOX)
        assert len(projects) > 50  # 100 erwartet laut Betreff

    def test_all_have_project_id(self):
        projects = parse_mbox_file(SAMPLE_MBOX)
        for p in projects:
            assert p.project_id > 0

    def test_all_have_url(self):
        projects = parse_mbox_file(SAMPLE_MBOX)
        for p in projects:
            assert p.url.startswith("https://www.freelancermap.de/nproj/")

    def test_all_have_title(self):
        projects = parse_mbox_file(SAMPLE_MBOX)
        for p in projects:
            assert len(p.title) > 3

    def test_first_project(self):
        projects = parse_mbox_file(SAMPLE_MBOX)
        p = projects[0]
        assert p.project_id == 2977008
        assert p.company == "Target Networks GmbH"
