"""Tests für scripts/extract_cv.py — CV-Extraktion aus ODT via LLM."""

from pathlib import Path

import pytest

# Importieren der Funktionen direkt — Skript liegt in scripts/
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.extract_cv import (
    _strip_code_fences,
    _strip_thinking,
    extract_text_from_odt,
    validate_cv_yaml,
)


SAMPLE_YAML = """\
name: "Max Mustermann"
title: "Senior Entwickler"
experience_years: 15

skills:
  - Python
  - Docker

skills_secondary:
  - React

preferred_locations:
  - Remote
preferred_remote: "100%"
preferred_contract_types:
  - Freiberuflich
min_duration_months: 3

exclude_skills:
  - SAP
exclude_industries: []

keywords:
  - backend
"""


class TestStripThinking:
    def test_removes_think_block(self):
        text = "<think>Reasoning...</think>\nname: Test"
        assert _strip_thinking(text) == "name: Test"

    def test_no_think_block(self):
        text = "name: Test"
        assert _strip_thinking(text) == "name: Test"

    def test_multiline_think(self):
        text = "<think>\nStep 1\nStep 2\n</think>\n\nname: Test"
        assert _strip_thinking(text) == "name: Test"


class TestStripCodeFences:
    def test_removes_yaml_fences(self):
        text = "```yaml\nname: Test\n```"
        assert _strip_code_fences(text) == "name: Test"

    def test_removes_bare_fences(self):
        text = "```\nname: Test\n```"
        assert _strip_code_fences(text) == "name: Test"

    def test_no_fences(self):
        text = "name: Test"
        assert _strip_code_fences(text) == "name: Test"

    def test_removes_yml_fences(self):
        text = "```yml\nname: Test\n```"
        assert _strip_code_fences(text) == "name: Test"


class TestValidateCvYaml:
    def test_valid_yaml(self):
        data = validate_cv_yaml(SAMPLE_YAML)
        assert data["name"] == "Max Mustermann"
        assert "Python" in data["skills"]

    def test_missing_name_raises(self):
        yaml_text = "skills:\n  - Python\n"
        with pytest.raises(ValueError, match="Pflichtfelder"):
            validate_cv_yaml(yaml_text)

    def test_missing_skills_raises(self):
        yaml_text = "name: Test\nskills: []\n"
        with pytest.raises(ValueError, match="Pflichtfelder"):
            validate_cv_yaml(yaml_text)

    def test_invalid_yaml_raises(self):
        with pytest.raises(ValueError, match="kein gültiges YAML"):
            validate_cv_yaml("- just a list\n- of items")

    def test_complete_structure(self):
        data = validate_cv_yaml(SAMPLE_YAML)
        assert data["experience_years"] == 15
        assert "React" in data["skills_secondary"]
        assert "backend" in data["keywords"]


class TestExtractTextFromOdt:
    def test_reads_real_odt(self):
        odt_path = Path("data/rma-Lebenslauf-2026.odt")
        if not odt_path.exists():
            pytest.skip("ODT-Datei nicht vorhanden")
        text = extract_text_from_odt(odt_path)
        assert len(text) > 1000
        assert "Masfelder" in text
