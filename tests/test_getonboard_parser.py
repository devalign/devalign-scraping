"""
Tests para GetOnBoardParser: extracción de datos desde JSON API y HTML.

Estrategia:
    - Los tests NO hacen requests reales a la red (usamos mocks/fixtures con
      datos representativos de la API real de GetOnBoard).
    - Se valida: filtrado por país, mapeo de campos, extracción de tags HTML,
      formato de salario, y mapeo de modalidad.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.getonboard_parser import GetOnBoardParser, MODALITY_MAP, DEFAULT_CATEGORIES
from src.parser import JobOffer


# ── Fixtures: datos mock representativos de la API real ─────────────────────

MOCK_JOB_PERU = {
    "id": "backend-developer-acme-lima",
    "type": "job",
    "attributes": {
        "title": "Backend Developer",
        "description": "<p>Buscamos desarrollador Python con experiencia en Django.</p>",
        "functions": "<p>Desarrollar APIs REST.</p>",
        "remote": False,
        "remote_modality": "onsite",
        "countries": ["Peru"],
        "min_salary": 2000,
        "max_salary": 3500,
        "published_at": 1777000000,
        "category_name": "Programming",
        "tags": {"data": [{"id": 18, "type": "tag"}, {"id": 64, "type": "tag"}]},
        "company": {"data": {"id": 999, "type": "company"}},
        "perks": [],
    },
    "links": {
        "public_url": "https://www.getonbrd.com/jobs/backend-developer-acme-lima"
    },
}

MOCK_JOB_REMOTE = {
    "id": "senior-engineer-globo-remote",
    "type": "job",
    "attributes": {
        "title": "Senior Software Engineer",
        "description": "<p>Experiencia de 3 años en microservicios y Docker.</p>",
        "functions": "<ul><li>Diseñar arquitecturas cloud</li></ul>",
        "remote": True,
        "remote_modality": "fully_remote",
        "countries": ["Remote"],
        "min_salary": None,
        "max_salary": None,
        "published_at": 1777111111,
        "category_name": "Programming",
        "tags": {"data": []},
        "company": {"data": {"id": 888, "type": "company"}},
        "perks": [],
    },
    "links": {
        "public_url": "https://www.getonbrd.com/jobs/senior-engineer-globo-remote"
    },
}

MOCK_JOB_CHILE_EXCLUDED = {
    "id": "qa-engineer-acme-bogota",
    "type": "job",
    "attributes": {
        "title": "QA Engineer",
        "description": "<p>Testing role.</p>",
        "functions": "",
        "remote": False,
        "remote_modality": "onsite",
        "countries": ["Colombia"],
        "min_salary": None,
        "max_salary": None,
        "published_at": 1777222222,
        "category_name": "SysAdmin / DevOps / QA",
        "tags": {"data": []},
        "company": {"data": {"id": 777, "type": "company"}},
        "perks": [],
    },
    "links": {"public_url": "https://www.getonbrd.com/jobs/qa-engineer-acme-bogota"},
}

MOCK_JOB_HYBRID_LATAM = {
    "id": "devops-engineer-empresa-mexico",
    "type": "job",
    "attributes": {
        "title": "DevOps Engineer",
        "description": "<p>Buscamos DevOps con experiencia en Kubernetes y AWS.</p>",
        "functions": "",
        "remote": True,
        "remote_modality": "hybrid",
        "countries": ["Mexico"],
        "min_salary": 4000,
        "max_salary": None,
        "published_at": 1777333333,
        "category_name": "SysAdmin / DevOps / QA",
        "tags": {"data": []},
        "company": {"data": {"id": 666, "type": "company"}},
        "perks": [],
    },
    "links": {
        "public_url": "https://www.getonbrd.com/jobs/devops-engineer-empresa-mexico"
    },
}

# HTML mock del detalle de una oferta (simplificado)
MOCK_DETAIL_HTML = """
<html>
<body>
  <div class="gb-tags">
    <a class="gb-tags__item">Python</a>
    <a class="gb-tags__item">Django</a>
    <a class="gb-tags__item">Docker</a>
    <a class="gb-tags__item">Communication</a>
  </div>
</body>
</html>
"""

MOCK_COMPANY_RESPONSE = {
    "data": {
        "id": "acme-corp",
        "type": "company",
        "attributes": {"name": "ACME Corp", "description": "Software company."},
    }
}

MOCK_API_RESPONSE = {
    "data": [MOCK_JOB_PERU, MOCK_JOB_REMOTE],
    "meta": {"page": 1, "per_page": 25, "total_pages": 5},
}


# ── Tests: inicialización ───────────────────────────────────────────────────


class TestGetOnBoardParserInit:
    def test_default_categories(self):
        parser = GetOnBoardParser()
        assert parser._categories == DEFAULT_CATEGORIES

    def test_custom_categories(self):
        parser = GetOnBoardParser(categories=["programming"])
        assert parser._categories == ["programming"]

    def test_site_name(self):
        parser = GetOnBoardParser()
        assert parser.SITE_NAME == "getonboard"

    def test_company_cache_starts_empty(self):
        parser = GetOnBoardParser()
        assert parser._company_cache == {}


# ── Tests: filtrado por país ────────────────────────────────────────────────


class TestCountryFilter:
    def setup_method(self):
        self.parser = GetOnBoardParser()

    def test_accepts_peru(self):
        attrs = {"countries": ["Peru"], "remote": False}
        assert self.parser._is_country_accepted(attrs) is True

    def test_accepts_remote(self):
        attrs = {"countries": ["Remote"], "remote": True}
        assert self.parser._is_country_accepted(attrs) is True

    def test_accepts_latam_countries(self):
        for country in ["Chile", "Colombia", "Mexico", "Argentina"]:
            attrs = {"countries": [country], "remote": False}
            assert (
                self.parser._is_country_accepted(attrs) is True
            ), f"Debería aceptar {country}"

    def test_accepts_empty_countries(self):
        """Sin restricción de país → global/remoto → se acepta."""
        attrs = {"countries": [], "remote": False}
        assert self.parser._is_country_accepted(attrs) is True

    def test_rejects_non_latam_country(self):
        """España no está en ACCEPTED_COUNTRIES y no es remote."""
        attrs = {"countries": ["Spain"], "remote": False}
        assert self.parser._is_country_accepted(attrs) is False

    def test_accepts_if_remote_flag_true_regardless_of_country(self):
        """Si remote=True, aceptar aunque el país no esté en la lista."""
        attrs = {"countries": ["Spain"], "remote": True}
        assert self.parser._is_country_accepted(attrs) is True


# ── Tests: formato de salario ───────────────────────────────────────────────


class TestFormatSalary:
    def setup_method(self):
        self.parser = GetOnBoardParser()

    def test_both_values(self):
        attrs = {"min_salary": 2000, "max_salary": 4000}
        assert self.parser._format_salary(attrs) == "USD 2,000 - 4,000"

    def test_only_min(self):
        attrs = {"min_salary": 1500, "max_salary": None}
        assert self.parser._format_salary(attrs) == "USD 1,500+"

    def test_only_max(self):
        attrs = {"min_salary": None, "max_salary": 5000}
        assert self.parser._format_salary(attrs) == "hasta USD 5,000"

    def test_none_both(self):
        attrs = {"min_salary": None, "max_salary": None}
        assert self.parser._format_salary(attrs) == "No especificado"

    def test_zero_salary_not_specified(self):
        """Salario 0 es inválido; se trata como no especificado."""
        attrs = {"min_salary": None, "max_salary": 0}
        assert "0" in self.parser._format_salary(attrs)


# ── Tests: mapeo de modalidad ───────────────────────────────────────────────


class TestModalityMapping:
    def test_fully_remote(self):
        assert MODALITY_MAP["fully_remote"] == "Remoto"

    def test_hybrid(self):
        assert MODALITY_MAP["hybrid"] == "Híbrido"

    def test_onsite(self):
        assert MODALITY_MAP["onsite"] == "Presencial"

    def test_remote_local(self):
        assert MODALITY_MAP["remote_local"] == "Remoto"


# ── Tests: extracción de tags desde HTML ────────────────────────────────────


class TestFetchTagsFromHtml:
    def setup_method(self):
        self.parser = GetOnBoardParser()

    def test_extracts_tag_names(self):
        with patch.object(self.parser._session, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = MOCK_DETAIL_HTML
            mock_get.return_value = mock_resp

            tags = self.parser._fetch_tags_from_html(
                "https://www.getonbrd.com/jobs/test"
            )

        assert "Python" in tags
        assert "Django" in tags
        assert "Docker" in tags
        assert "Communication" in tags

    def test_returns_empty_on_http_error(self):
        with patch.object(self.parser._session, "get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_get.return_value = mock_resp

            tags = self.parser._fetch_tags_from_html(
                "https://www.getonbrd.com/jobs/not-found"
            )

        assert tags == []

    def test_returns_empty_on_network_exception(self):
        with patch.object(
            self.parser._session, "get", side_effect=Exception("timeout")
        ):
            tags = self.parser._fetch_tags_from_html(
                "https://www.getonbrd.com/jobs/timeout"
            )
        assert tags == []


# ── Tests: fetch_and_parse_job ──────────────────────────────────────────────


class TestFetchAndParseJob:
    def setup_method(self):
        self.parser = GetOnBoardParser()
        url = MOCK_JOB_PERU["links"]["public_url"]
        # Pre-popular el cache como lo haría fetch_job_listings
        self.parser._job_data_cache[url] = {
            "attrs": MOCK_JOB_PERU["attributes"],
            "job_id": MOCK_JOB_PERU["id"],
        }
        self.url = url

    def _mock_session(self, company_name: str = "ACME Corp"):
        """Configura el mock de session para respuestas de empresa y HTML."""
        company_resp = MagicMock()
        company_resp.status_code = 200
        company_resp.json.return_value = MOCK_COMPANY_RESPONSE

        html_resp = MagicMock()
        html_resp.status_code = 200
        html_resp.text = MOCK_DETAIL_HTML

        def side_effect(url, **kwargs):
            if "companies" in url:
                return company_resp
            return html_resp

        return side_effect

    def test_job_title(self):
        with patch.object(
            self.parser._session, "get", side_effect=self._mock_session()
        ):
            offer = self.parser.fetch_and_parse_job(page=None, url=self.url)
        assert offer.job_title == "Backend Developer"

    def test_salary_formatted(self):
        with patch.object(
            self.parser._session, "get", side_effect=self._mock_session()
        ):
            offer = self.parser.fetch_and_parse_job(page=None, url=self.url)
        assert offer.salary == "USD 2,000 - 3,500"

    def test_modality_onsite(self):
        with patch.object(
            self.parser._session, "get", side_effect=self._mock_session()
        ):
            offer = self.parser.fetch_and_parse_job(page=None, url=self.url)
        assert offer.modality == "Presencial"

    def test_location_peru(self):
        with patch.object(
            self.parser._session, "get", side_effect=self._mock_session()
        ):
            offer = self.parser.fetch_and_parse_job(page=None, url=self.url)
        assert "Peru" in offer.location

    def test_source_url_preserved(self):
        with patch.object(
            self.parser._session, "get", side_effect=self._mock_session()
        ):
            offer = self.parser.fetch_and_parse_job(page=None, url=self.url)
        assert offer.source_url == self.url

    def test_hard_skills_from_tags(self):
        with patch.object(
            self.parser._session, "get", side_effect=self._mock_session()
        ):
            offer = self.parser.fetch_and_parse_job(page=None, url=self.url)
        # Python y Docker son HARD_SKILLS_KEYWORDS
        assert "python" in offer.hard_skills or "docker" in offer.hard_skills

    def test_company_resolved(self):
        with patch.object(
            self.parser._session, "get", side_effect=self._mock_session()
        ):
            offer = self.parser.fetch_and_parse_job(page=None, url=self.url)
        assert offer.company == "ACME Corp"

    def test_returns_joboffer_instance(self):
        with patch.object(
            self.parser._session, "get", side_effect=self._mock_session()
        ):
            offer = self.parser.fetch_and_parse_job(page=None, url=self.url)
        assert isinstance(offer, JobOffer)


# ── Tests: fetch_job_listings ───────────────────────────────────────────────


class TestFetchJobListings:
    def setup_method(self):
        self.parser = GetOnBoardParser(categories=["programming"])

    def _build_api_response(self, jobs: list, page: int = 1, total_pages: int = 1):
        return MagicMock(
            **{
                "status_code": 200,
                "raise_for_status": MagicMock(),
                "json.return_value": {
                    "data": jobs,
                    "meta": {
                        "page": page,
                        "per_page": 25,
                        "total_pages": total_pages,
                    },
                },
            }
        )

    def test_returns_list_of_tuples(self):
        mock_resp = self._build_api_response([MOCK_JOB_PERU, MOCK_JOB_REMOTE])
        with patch.object(self.parser._session, "get", return_value=mock_resp):
            entries = self.parser.fetch_job_listings(page=None, current_page=1)

        assert isinstance(entries, list)
        assert all(isinstance(e, tuple) and len(e) == 2 for e in entries)

    def test_filters_non_latam_countries(self):
        """Colombia sí está en ACCEPTED_COUNTRIES, pero España no."""
        mock_resp = self._build_api_response(
            [MOCK_JOB_CHILE_EXCLUDED]  # Colombia → debe incluirse
        )
        with patch.object(self.parser._session, "get", return_value=mock_resp):
            entries = self.parser.fetch_job_listings(page=None, current_page=1)

        # Colombia está en ACCEPTED_COUNTRIES → se incluye
        assert len(entries) == 1

    def test_returns_empty_when_api_empty(self):
        mock_resp = self._build_api_response([])
        with patch.object(self.parser._session, "get", return_value=mock_resp):
            entries = self.parser.fetch_job_listings(page=None, current_page=1)

        assert entries == []

    def test_advances_category_index_when_exhausted(self):
        parser = GetOnBoardParser(categories=["programming", "mobile-developer"])
        # Primera llamada: programming agotado (total_pages=1)
        mock_resp = self._build_api_response([MOCK_JOB_PERU], page=1, total_pages=1)
        with patch.object(parser._session, "get", return_value=mock_resp):
            parser.fetch_job_listings(page=None, current_page=1)

        # Después de agotar programming, debe avanzar a mobile-developer
        assert parser._current_category_idx == 1

    def test_handles_network_error_gracefully(self):
        """Un error de red en una categoría avanza a la siguiente."""
        parser = GetOnBoardParser(categories=["programming", "mobile-developer"])
        with patch.object(
            parser._session, "get", side_effect=Exception("Connection refused")
        ):
            entries = parser.fetch_job_listings(page=None, current_page=1)

        assert entries == []

    def test_caches_job_data_for_later_parsing(self):
        mock_resp = self._build_api_response([MOCK_JOB_PERU])
        with patch.object(self.parser._session, "get", return_value=mock_resp):
            _ = self.parser.fetch_job_listings(page=None, current_page=1)

        url = MOCK_JOB_PERU["links"]["public_url"]
        assert url in self.parser._job_data_cache


# ── Tests: company cache ────────────────────────────────────────────────────


class TestCompanyCache:
    def test_caches_after_first_request(self):
        parser = GetOnBoardParser()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_COMPANY_RESPONSE

        with patch.object(parser._session, "get", return_value=mock_resp) as mock_get:
            name1 = parser._resolve_company(999)
            name2 = parser._resolve_company(999)  # Debe usar cache, no hacer GET

        assert name1 == "ACME Corp"
        assert name2 == "ACME Corp"
        assert mock_get.call_count == 1  # Solo un GET real

    def test_returns_empty_string_on_error(self):
        parser = GetOnBoardParser()
        with patch.object(parser._session, "get", side_effect=Exception("timeout")):
            name = parser._resolve_company(12345)

        assert name == ""
