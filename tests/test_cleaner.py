"""Tests para TextCleaner: cada etapa del pipeline de limpieza."""

import pytest

from src.cleaner import TextCleaner
from src.parser import JobOffer


@pytest.fixture
def cleaner():
    return TextCleaner()


class TestFixEncoding:
    """Tests para reparación de encoding mojibake."""

    def test_fixes_mojibake(self, cleaner):
        # â€™ es un mojibake común de '
        broken = "It\u00e2\u0080\u0099s a test"
        fixed = cleaner.fix_encoding(broken)
        assert "\u00e2\u0080\u0099" not in fixed

    def test_preserves_spanish_chars(self, cleaner):
        text = "Diseño y programación ágil con años de experiencia"
        assert cleaner.fix_encoding(text) == text


class TestRemoveHtmlArtifacts:
    """Tests para eliminación de HTML residual."""

    def test_removes_tags(self, cleaner):
        text = "Hello <b>world</b> and <br/>more"
        result = cleaner.remove_html_artifacts(text)
        assert "<b>" not in result
        assert "<br/>" not in result
        assert "world" in result

    def test_removes_entities(self, cleaner):
        text = "precio&amp;descuento&nbsp;aquí"
        result = cleaner.remove_html_artifacts(text)
        assert "&amp;" not in result
        assert "&nbsp;" not in result


class TestNormalizeWhitespace:
    """Tests para normalización de espacios."""

    def test_collapses_spaces(self, cleaner):
        text = "hello    world     test"
        assert cleaner.normalize_whitespace(text) == "hello world test"

    def test_collapses_newlines(self, cleaner):
        text = "line1\n\n\n\n\nline2"
        assert cleaner.normalize_whitespace(text) == "line1\n\nline2"

    def test_strips_edges(self, cleaner):
        text = "  hello world  "
        assert cleaner.normalize_whitespace(text) == "hello world"


class TestRemoveNoisePatterns:
    """Tests para eliminación de ruido."""

    def test_removes_urls(self, cleaner):
        text = "Visita https://example.com para más info"
        result = cleaner.remove_noise_patterns(text)
        assert "https://example.com" not in result
        assert "Visita" in result

    def test_removes_long_numbers(self, cleaner):
        text = "Contactar al 987654321 para info"
        result = cleaner.remove_noise_patterns(text)
        assert "987654321" not in result

    def test_preserves_spanish_characters(self, cleaner):
        text = "Programación en español con ñ y acentos: áéíóú"
        result = cleaner.remove_noise_patterns(text)
        assert "ñ" in result
        assert "á" in result
        assert "Programación" in result


class TestNormalizeSkillsList:
    """Tests para normalización de listas de skills."""

    def test_joins_with_pipe(self, cleaner):
        skills = ["Python", "React", "Docker"]
        result = cleaner.normalize_skills_list(skills)
        assert "|" in result
        assert "python" in result  # Lowercase

    def test_deduplicates(self, cleaner):
        skills = ["Python", "python", "PYTHON"]
        result = cleaner.normalize_skills_list(skills)
        assert result.count("python") == 1

    def test_sorts_alphabetically(self, cleaner):
        skills = ["React", "Angular", "Docker"]
        result = cleaner.normalize_skills_list(skills)
        parts = [s.strip() for s in result.split("|")]
        assert parts == sorted(parts)

    def test_handles_empty_list(self, cleaner):
        assert cleaner.normalize_skills_list([]) == ""

    def test_filters_empty_strings(self, cleaner):
        skills = ["Python", "", "React"]
        result = cleaner.normalize_skills_list(skills)
        assert result.count("|") == 1  # Solo 2 items válidos


class TestCleanTextField:
    """Tests para el pipeline completo sobre un campo de texto."""

    def test_full_pipeline(self, cleaner):
        text = (
            "Diseño <b>web</b> &amp; programación\n\n\n\n"
            "visita https://example.com\n"
            "contacto: 123456789012"
        )
        result = cleaner.clean_text_field(text)
        assert "<b>" not in result
        assert "&amp;" not in result
        assert "https://example.com" not in result
        assert "123456789012" not in result
        assert "Diseño" in result
        assert "programación" in result


class TestCleanJobOffer:
    """Tests para la limpieza completa de un JobOffer."""

    def test_returns_new_instance(self, cleaner):
        offer = JobOffer(
            job_title="  Dev  <br/>  ",
            company="  ACME  Corp  ",
            location="  Lima  ",
            full_description="Description with     extra spaces and <b>html</b>.",
            hard_skills=["Python", "React"],
            soft_skills=["Liderazgo"],
            experience_years="  3 años  ",
            education_level="  Universitaria  ",
        )
        cleaned = cleaner.clean(offer)

        # Es una nueva instancia
        assert cleaned is not offer

        # Campos limpiados
        assert "<br/>" not in cleaned.job_title
        assert "  " not in cleaned.company
        assert "<b>" not in cleaned.full_description
        assert "|" in cleaned.hard_skills  # Ahora es string con pipe
        assert cleaned.experience_years == "3 años"
        assert cleaned.education_level == "universitaria"
