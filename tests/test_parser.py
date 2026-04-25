"""Tests para JobParser: extracción de URLs y parseo de detalle."""

import pytest

from src.parser import JobParser, JobOffer


# --- Fixtures: HTML mock ---

LISTING_HTML = """
<html>
<body>
    <div class="listings">
        <a class="js-o-link" href="/ofertas-de-trabajo/abc123">Oferta 1</a>
        <a class="js-o-link" href="/ofertas-de-trabajo/def456">Oferta 2</a>
        <a class="js-o-link" href="">Oferta vacía</a>
        <a class="other-link" href="/not-a-job">No es oferta</a>
    </div>
</body>
</html>
"""

DETAIL_HTML = """
<html>
<body>
    <h1 class="fs24">Desarrollador Full Stack Python</h1>
    <p class="fs16"><a class="js-o-link">TechCorp SAC</a></p>
    <p class="fs16">Lima, Perú</p>
    <div class="mb40 pb40 bb1">
        Buscamos desarrollador con experiencia en Python, Django y React.
        Requisitos:
        - 3 años de experiencia en desarrollo web
        - Conocimiento de PostgreSQL y Docker
        - Bachiller en ingeniería de sistemas
        - Trabajo en equipo y comunicación efectiva
        - Proactivo y orientado a resultados
    </div>
</body>
</html>
"""

DETAIL_HTML_EMPTY = """
<html>
<body>
    <div class="no-offer">Página sin datos de oferta</div>
</body>
</html>
"""


@pytest.fixture
def parser():
    return JobParser()


class TestParseListingPage:
    """Tests para la extracción de URLs desde el listado."""

    def test_extracts_valid_urls(self, parser):
        urls = parser.parse_listing_page(LISTING_HTML)
        assert len(urls) == 2
        assert all(url.startswith("https://www.computrabajo.com.pe") for url in urls)

    def test_ignores_empty_hrefs(self, parser):
        urls = parser.parse_listing_page(LISTING_HTML)
        # Solo 2 URLs válidas (la tercera tiene href vacío)
        assert len(urls) == 2

    def test_ignores_non_matching_selectors(self, parser):
        urls = parser.parse_listing_page(LISTING_HTML)
        assert not any("not-a-job" in url for url in urls)

    def test_returns_empty_on_no_results(self, parser):
        urls = parser.parse_listing_page("<html><body></body></html>")
        assert urls == []


class TestParseJobDetail:
    """Tests para el parseo de detalle de una vacante."""

    def test_extracts_title(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert offer.job_title == "Desarrollador Full Stack Python"

    def test_extracts_company(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert offer.company == "TechCorp SAC"

    def test_extracts_location(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert offer.location == "Lima, Perú"

    def test_extracts_full_description(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert "Python" in offer.full_description
        assert "Django" in offer.full_description
        assert len(offer.full_description) > 50

    def test_detects_hard_skills(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert "python" in offer.hard_skills
        assert "django" in offer.hard_skills
        assert "react" in offer.hard_skills
        assert "postgresql" in offer.hard_skills
        assert "docker" in offer.hard_skills

    def test_detects_soft_skills(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert "trabajo en equipo" in offer.soft_skills
        assert "comunicación" in offer.soft_skills
        assert "proactivo" in offer.soft_skills

    def test_extracts_experience_years(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert "3" in offer.experience_years
        assert "experiencia" in offer.experience_years

    def test_detects_education_level(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert offer.education_level == "universitaria"

    def test_preserves_source_url(self, parser):
        url = "https://example.com/job/1"
        offer = parser.parse_job_detail(DETAIL_HTML, url)
        assert offer.source_url == url

    def test_handles_missing_fields(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML_EMPTY, "https://example.com/job/2")
        assert offer.job_title == ""
        assert offer.company == ""
        assert offer.full_description == ""
        assert offer.experience_years == "No especificado"
        assert offer.education_level == "No especificado"

    def test_has_scraped_at_timestamp(self, parser):
        offer = parser.parse_job_detail(DETAIL_HTML, "https://example.com/job/1")
        assert offer.scraped_at  # No vacío
        assert "T" in offer.scraped_at  # Formato ISO


class TestJobOfferDataclass:
    """Tests para el dataclass JobOffer."""

    def test_default_values(self):
        offer = JobOffer()
        assert offer.job_title == ""
        assert offer.hard_skills == []
        assert offer.soft_skills == []
        assert offer.scraped_at  # Auto-generado

    def test_custom_values(self):
        offer = JobOffer(
            job_title="Dev",
            company="ACME",
            hard_skills=["python"],
        )
        assert offer.job_title == "Dev"
        assert offer.company == "ACME"
        assert offer.hard_skills == ["python"]
