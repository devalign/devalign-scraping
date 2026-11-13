"""
Parser de GetOnBoard — Estrategia API-First.

Extrae ofertas laborales desde la API REST pública de GetOnBoard
(https://www.getonbrd.com/api/v0/) sin necesidad de un browser headless.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Optional

from bs4 import BeautifulSoup

from src.base_parser import HttpParser
from src.models import JobOffer
from src.taxonomy import SkillTaxonomyService

# ── Constantes ─────────────────────────────────────────────────────────────

API_BASE = "https://www.getonbrd.com/api/v0"

# Categorías IT por defecto (slug de la API de GetOnBoard)
DEFAULT_CATEGORIES: list[str] = [
    "programming",
    "mobile-developer",
    "sysadmin-devops-qa",
    "data-science-analytics",
    "machine-learning-ai",
    "cybersecurity",
    "design-ux",
]

# Países aceptados para filtrar ofertas (vacías/remote se incluyen siempre)
ACCEPTED_COUNTRIES: set[str] = {
    "Peru",
    "Chile",
    "Colombia",
    "Mexico",
    "Argentina",
    "Remote",
}

# Mapeo de remote_modality de la API → valor normalizado en JobOffer
MODALITY_MAP: dict[str, str] = {
    "fully_remote": "Remoto",
    "remote_local": "Remoto",
    "hybrid": "Híbrido",
    "onsite": "Presencial",
}

# Mapeo de países de GetOnBoard → código ISO-2 normalizado
GOB_COUNTRY_MAP: dict[str, str] = {
    "chile": "cl",
    "colombia": "co",
    "peru": "pe",
    "perú": "pe",
    "mexico": "mx",
    "méxico": "mx",
    "argentina": "ar",
    "uruguay": "uy",
}

# Delay entre requests a la API (anti-abuse)
REQUEST_DELAY_SECS: float = 1.0

# Headers para requests HTTP
HTTP_HEADERS: dict[str, str] = {
    "Accept": "application/json",
    "Accept-Language": "es-419,es;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class GetOnBoardParser(HttpParser):
    """
    Parser API-first para www.getonbrd.com.
    Hereda de HttpParser, utilizando conexión HTTP persistente y pool de reintentos.
    """

    SITE_NAME: str = "getonboard"
    DEFAULT_BASE_URL: str = "https://www.getonbrd.com"

    def __init__(
        self,
        categories: Optional[list[str]] = None,
        accepted_countries: Optional[set[str]] = None,
    ):
        super().__init__(headers=HTTP_HEADERS, timeout=15)
        self._categories: list[str] = categories or DEFAULT_CATEGORIES
        self._accepted_countries: set[str] = accepted_countries or ACCEPTED_COUNTRIES

        # Alias para compatibilidad con código existente que use self._session
        self._session = self.session

        # Cache de empresas: {company_numeric_id: "Nombre Empresa"}
        self._company_cache: dict[int, str] = {}

        # Iterador interno de categorías para paginación multi-categoría
        self._category_page_map: dict[str, int] = {cat: 1 for cat in self._categories}
        self._current_category_idx: int = 0

        # Buffer de ofertas obtenidas en el último batch de la API
        self._job_data_cache: dict[str, dict] = {}

        self._taxonomy = SkillTaxonomyService.get_instance()

    @property
    def HARD_SKILLS_KEYWORDS(self) -> list[str]:
        return self._taxonomy.hard_skills

    @property
    def SOFT_SKILLS_KEYWORDS(self) -> list[str]:
        return self._taxonomy.soft_skills

    # ── Interfaz BaseParser ─────────────────────────────────────────────────

    def fetch_job_listings(
        self, current_page: int = 1, page=None, **kwargs
    ) -> list[tuple[str, str]]:
        """
        Obtiene la lista de ofertas de la API de GetOnBoard.
        Soporta llamadas posicionales y por keyword:
            fetch_job_listings(current_page=1, page=None)
            fetch_job_listings(page, current_page)
        """
        if not isinstance(current_page, int) and isinstance(page, int):
            current_page, page = page, current_page
        while self._current_category_idx < len(self._categories):
            category = self._categories[self._current_category_idx]
            cat_page = self._category_page_map[category]

            url = f"{API_BASE}/categories/{category}/jobs"
            params = {"per_page": 25, "page": cat_page}

            try:
                resp = self._session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                print(f"   [GOB-ERROR] Error al fetchar categoría '{category}': {exc}")
                self._current_category_idx += 1
                continue

            jobs = data.get("data", [])
            meta = data.get("meta", {})
            total_pages = meta.get("total_pages", 1)

            if not jobs:
                self._current_category_idx += 1
                continue

            if cat_page >= total_pages:
                self._current_category_idx += 1
            else:
                self._category_page_map[category] = cat_page + 1

            entries: list[tuple[str, str]] = []
            for job in jobs:
                attrs = job.get("attributes", {})
                public_url = job.get("links", {}).get("public_url", "")
                title = attrs.get("title", "")

                if not public_url:
                    continue

                if not self._is_country_accepted(attrs):
                    continue

                self._job_data_cache[public_url] = {
                    "attrs": attrs,
                    "job_id": job.get("id", ""),
                }

                entries.append((public_url, title))

            time.sleep(REQUEST_DELAY_SECS)
            return entries

        return []

    def fetch_and_parse_job(self, url: str = "", page=None, **kwargs) -> JobOffer:
        """
        Construye un JobOffer a partir del cache de la API + HTML del detalle.
        Soporta llamadas posicionales y por keyword:
            fetch_and_parse_job(url="...", page=None)
            fetch_and_parse_job(page, url="...")
        """
        if not isinstance(url, str) and isinstance(page, str):
            url, page = page, url
        if not url and "url" in kwargs:
            url = kwargs["url"]
        cached = self._job_data_cache.get(url, {})
        attrs = cached.get("attrs", {})

        offer = JobOffer(source_url=url, portal=self.SITE_NAME)

        # 1. Título
        offer.job_title = attrs.get("title", "")

        # 2. Empresa (con cache)
        company_data = attrs.get("company", {}).get("data", {})
        company_id = company_data.get("id") if company_data else None
        if company_id:
            offer.company = self._resolve_company(company_id)

        # 3. Ubicación / Países
        countries: list[str] = attrs.get("countries", [])
        offer.location = ", ".join(countries) if countries else "Remoto"
        if len(countries) > 1:
            offer.country = "latam"
        elif len(countries) == 1:
            offer.country = GOB_COUNTRY_MAP.get(countries[0].lower().strip(), "")
        else:
            offer.country = ""

        # 4. Salario
        offer.salary = self._format_salary(attrs)

        # 5. Modalidad
        remote_modality = attrs.get("remote_modality", "")
        is_remote = attrs.get("remote", False)
        if is_remote and not remote_modality:
            offer.modality = "Remoto"
        else:
            offer.modality = MODALITY_MAP.get(remote_modality, "Presencial")

        # 6. Fecha de publicación
        published_at = attrs.get("published_at")
        if published_at:
            dt = datetime.fromtimestamp(published_at, tz=timezone.utc)
            offer.date_posted = dt.strftime("%Y-%m-%d")
        else:
            offer.date_posted = "Reciente"

        # 7. Descripción + Funciones
        description_html = attrs.get("description", "") or ""
        functions_html = attrs.get("functions", "") or ""
        full_html = f"{description_html}\n{functions_html}".strip()
        offer.full_description = self._html_to_text(full_html)

        # 8. Tags del HTML de detalle
        tag_names = self._fetch_tags_from_html(url)

        # 9. Hard & Soft Skills con taxonomía centralizada
        tag_lower = {t.lower() for t in tag_names}
        desc_lower = offer.full_description.lower()
        combined_text = f"{' '.join(tag_lower)} {desc_lower}"

        hard_skills, soft_skills = self._taxonomy.extract_skills(combined_text)
        offer.hard_skills = hard_skills
        offer.soft_skills = soft_skills

        # 10. Años de experiencia
        exp_matches = re.findall(
            r"\d+\s*(?:a\s*\d+)?\s*años?\s*de\s*experiencia", desc_lower
        )
        offer.experience_years = exp_matches[-1] if exp_matches else "No especificado"

        # 11. Nivel educativo
        edu_map = {
            "universitaria": ["universidad", "ingeniería", "licenciatura", "bachiller"],
            "técnica": ["técnico", "instituto", "cetpro"],
            "maestría": ["maestría", "mba", "postgrado"],
        }
        offer.education_level = "No especificado"
        for level, keywords in edu_map.items():
            if any(k in desc_lower for k in keywords):
                offer.education_level = level
                break

        return offer

    # ── Helpers privados ────────────────────────────────────────────────────

    def _is_country_accepted(self, attrs: dict) -> bool:
        countries: list[str] = attrs.get("countries", [])
        is_remote: bool = attrs.get("remote", False)

        if not countries or is_remote:
            return True

        return bool(set(countries) & self._accepted_countries)

    def _resolve_company(self, company_id: int) -> str:
        if company_id in self._company_cache:
            return self._company_cache[company_id]

        try:
            resp = self._session.get(f"{API_BASE}/companies/{company_id}", timeout=10)
            if resp.status_code == 200:
                name = resp.json().get("data", {}).get("attributes", {}).get("name", "")
                self._company_cache[company_id] = name
                time.sleep(0.5)
                return name
        except Exception:
            pass

        self._company_cache[company_id] = ""
        return ""

    def _fetch_tags_from_html(self, url: str) -> list[str]:
        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "lxml")
            tags = soup.select("a.gb-tags__item")
            return [t.get_text(strip=True) for t in tags if t.get_text(strip=True)]
        except Exception:
            return []

    def _format_salary(self, attrs: dict) -> str:
        min_s = attrs.get("min_salary")
        max_s = attrs.get("max_salary")

        if min_s is None and max_s is None:
            return "No especificado"
        if min_s is not None and max_s is not None:
            return f"USD {int(min_s):,} - {int(max_s):,}"
        if min_s is not None:
            return f"USD {int(min_s):,}+"
        return f"hasta USD {int(max_s):,}"

    def _html_to_text(self, html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        for li in soup.select("li"):
            li.insert_before("• ")
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
