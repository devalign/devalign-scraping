"""
Parser de GetOnBoard — Estrategia API-First.

Extrae ofertas laborales desde la API REST pública de GetOnBoard
(https://www.getonbrd.com/api/v0/) sin necesitar un browser headless.

Flujo de extracción por oferta:
    1. GET /api/v0/categories/{slug}/jobs  → lista JSON paginada (título, salary, modality, etc.)
    2. GET HTML del detalle (requests simple) → nombres de tags (a.gb-tags__item)
    3. GET /api/v0/companies/{id}           → nombre de empresa (cacheado por sesión)
    4. Mapeo a JobOffer + aplicación de HARD/SOFT_SKILLS_KEYWORDS

Ventajas respecto a scraping HTML con Playwright:
    - ~10x más rápido (sin renderizado JS)
    - Sin riesgo de detección de bot (API pública oficial)
    - Datos estructurados más fiables que selectores CSS

Categorías IT por defecto (configurables via --categories):
    - programming
    - mobile-developer
    - sysadmin-devops-qa
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from src.base_parser import BaseParser
from src.parser import JobOffer

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

# Delay entre requests a la API (anti-abuse; la API es pública pero amable)
REQUEST_DELAY_SECS: float = 1.0

# Headers para requests HTTP (no Playwright)
HTTP_HEADERS: dict[str, str] = {
    "Accept": "application/json",
    "Accept-Language": "es-419,es;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}


class GetOnBoardParser(BaseParser):
    """
    Parser API-first para www.getonbrd.com.

    No utiliza Playwright. Todos los datos estructurados (título, salario,
    modalidad, etc.) se obtienen de la API REST pública. Solo el HTML del
    detalle se fetcha para extraer los nombres de los tags técnicos.

    Uso con el orquestador:
        parser = GetOnBoardParser(categories=["programming", "mobile-developer"])
        entries = parser.fetch_job_listings(page=None, current_page=1)
        offer   = parser.fetch_and_parse_job(page=None, url=entries[0][0])
    """

    SITE_NAME: str = "getonboard"
    DEFAULT_BASE_URL: str = "https://www.getonbrd.com"

    # Diccionarios de referencia para clasificación (compartidos con ComputrabajoParser)
    HARD_SKILLS_KEYWORDS = [
        "python",
        "java",
        "javascript",
        "typescript",
        "react",
        "angular",
        "node",
        "django",
        "fastapi",
        "sql",
        "postgresql",
        "mongodb",
        "docker",
        "kubernetes",
        "aws",
        "gcp",
        "azure",
        "git",
        "ci/cd",
        "machine learning",
        "tensorflow",
        "scikit-learn",
        "pandas",
        ".net",
        "c#",
        "php",
        "laravel",
        "vue",
        "next.js",
        "flask",
        "redis",
        "mysql",
        "linux",
        "terraform",
        "jenkins",
        "jira",
        "figma",
        "html",
        "css",
        "sass",
        "graphql",
        "rest api",
        "microservicios",
        "scrum",
        "agile",
        "flutter",
        "dart",
        "kotlin",
        "swift",
        "golang",
        "ruby",
        "rails",
        "spring boot",
        "unity",
        "unreal engine",
        "blockchain",
        "solidity",
        "power bi",
        "tableau",
        "ux/ui",
        "adobe xd",
        "kanban",
        "devops",
        "cybersecurity",
        "qa",
        "selenium",
        "cypress",
        "jest",
        "backend",
        "frontend",
        "fullstack",
        "cloud computing",
        "system design",
        "software engineering",
        "ios",
        "android",
        "firebase",
        "react native",
    ]

    SOFT_SKILLS_KEYWORDS = [
        "comunicación",
        "trabajo en equipo",
        "liderazgo",
        "proactivo",
        "resolución de problemas",
        "adaptabilidad",
        "gestión del tiempo",
        "creatividad",
        "orientado a resultados",
        "colaboración",
        "pensamiento crítico",
        "negociación",
        "empatía",
        "autonomía",
        "responsabilidad",
        "organización",
        "atención al detalle",
        "tolerancia a la frustración",
        "capacidad de análisis",
        "aprendizaje rápido",
        "communication",
        "teamwork",
        "leadership",
    ]

    def __init__(
        self,
        categories: Optional[list[str]] = None,
        accepted_countries: Optional[set[str]] = None,
    ):
        """
        Args:
            categories:        Lista de slugs de categorías GetOnBoard a scrapear.
                               Default: DEFAULT_CATEGORIES (programming, mobile, sysadmin).
            accepted_countries: Conjunto de países a incluir. Default: ACCEPTED_COUNTRIES.
        """
        self._categories: list[str] = categories or DEFAULT_CATEGORIES
        self._accepted_countries: set[str] = accepted_countries or ACCEPTED_COUNTRIES

        # Cache de empresas: {company_numeric_id: "Nombre Empresa"}
        # Evita repetir requests a /api/v0/companies/{id} para la misma empresa.
        self._company_cache: dict[int, str] = {}

        # Iterador interno de categorías para paginación multi-categoría.
        # El orquestador incrementa current_page; nosotros llevamos la cuenta
        # de categoría internamente a través del índice.
        self._category_page_map: dict[str, int] = {cat: 1 for cat in self._categories}
        self._current_category_idx: int = 0

        # Buffer de ofertas obtenidas en el último batch de la API
        # (para no re-fetchear al llamar fetch_and_parse_job)
        self._job_data_cache: dict[str, dict] = {}

        self._session = requests.Session()
        self._session.headers.update(HTTP_HEADERS)

    # ── Interfaz BaseParser ─────────────────────────────────────────────────

    def fetch_job_listings(self, page, current_page: int) -> list[tuple[str, str]]:
        """
        Obtiene la lista de ofertas de la API de GetOnBoard.

        Itera sobre las categorías configuradas usando un esquema de páginas
        global. Cuando una categoría se agota (total_pages alcanzado), avanza
        a la siguiente.

        Args:
            page:         Ignorado (la API no necesita Playwright).
            current_page: Número de página global (manejado por SessionManager).

        Returns:
            Lista de tuplas (public_url, title) filtradas por país.
            Lista vacía si todas las categorías están agotadas.
        """
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
                # Categoría agotada → avanzar a la siguiente
                self._current_category_idx += 1
                continue

            # Actualizar página de esta categoría para la próxima llamada
            if cat_page >= total_pages:
                self._current_category_idx += 1
            else:
                self._category_page_map[category] = cat_page + 1

            # Filtrar por país y construir lista de (url, title)
            entries: list[tuple[str, str]] = []
            for job in jobs:
                attrs = job.get("attributes", {})
                public_url = job.get("links", {}).get("public_url", "")
                title = attrs.get("title", "")

                if not public_url:
                    continue

                if not self._is_country_accepted(attrs):
                    continue

                # Guardar en caché para usar en fetch_and_parse_job
                self._job_data_cache[public_url] = {
                    "attrs": attrs,
                    "job_id": job.get("id", ""),
                }

                entries.append((public_url, title))

            time.sleep(REQUEST_DELAY_SECS)
            return entries

        return []  # Todas las categorías agotadas

    def fetch_and_parse_job(self, page, url: str) -> JobOffer:
        """
        Construye un JobOffer a partir del cache de la API + HTML del detalle.

        Los datos estructurados (título, salario, modalidad, países) provienen
        del JSON ya obtenido en fetch_job_listings. Solo se hace un GET HTTP
        adicional para extraer los nombres de los tags técnicos del HTML.

        Args:
            page: Ignorado.
            url:  URL pública de la oferta.

        Returns:
            JobOffer poblado.
        """
        cached = self._job_data_cache.get(url, {})
        attrs = cached.get("attrs", {})

        offer = JobOffer(source_url=url, portal=self.SITE_NAME)

        # ── 1. Título ────────────────────────────────────────────────────
        offer.job_title = attrs.get("title", "")

        # ── 2. Empresa (con cache) ────────────────────────────────────────
        company_data = attrs.get("company", {}).get("data", {})
        company_id = company_data.get("id") if company_data else None
        if company_id:
            offer.company = self._resolve_company(company_id)

        # ── 3. Ubicación / Países ─────────────────────────────────────────
        countries: list[str] = attrs.get("countries", [])
        offer.location = ", ".join(countries) if countries else "Remoto"

        # ── 4. Salario ────────────────────────────────────────────────────
        offer.salary = self._format_salary(attrs)

        # ── 5. Modalidad ──────────────────────────────────────────────────
        remote_modality = attrs.get("remote_modality", "")
        is_remote = attrs.get("remote", False)
        if is_remote and not remote_modality:
            offer.modality = "Remoto"
        else:
            offer.modality = MODALITY_MAP.get(remote_modality, "Presencial")

        # ── 6. Fecha de publicación ───────────────────────────────────────
        published_at = attrs.get("published_at")
        if published_at:
            dt = datetime.fromtimestamp(published_at, tz=timezone.utc)
            offer.date_posted = dt.strftime("%Y-%m-%d")
        else:
            offer.date_posted = "Reciente"

        # ── 7. Descripción + Funciones (HTML → texto) ─────────────────────
        description_html = attrs.get("description", "") or ""
        functions_html = attrs.get("functions", "") or ""
        full_html = f"{description_html}\n{functions_html}".strip()
        offer.full_description = self._html_to_text(full_html)

        # ── 8. Tags (requiere GET al HTML del detalle) ────────────────────
        tag_names = self._fetch_tags_from_html(url)

        # ── 9. Hard & Soft Skills ─────────────────────────────────────────
        # Primero: tags explícitos de la plataforma (más fiables)
        tag_lower = {t.lower() for t in tag_names}
        desc_lower = offer.full_description.lower()
        combined_lower = f"{' '.join(tag_lower)} {desc_lower}"

        offer.hard_skills = [
            s
            for s in self.HARD_SKILLS_KEYWORDS
            if re.search(rf"\b{re.escape(s)}\b", combined_lower)
        ]
        offer.soft_skills = [
            s
            for s in self.SOFT_SKILLS_KEYWORDS
            if re.search(rf"\b{re.escape(s)}\b", combined_lower)
        ]

        # ── 10. Años de experiencia ───────────────────────────────────────
        exp_matches = re.findall(
            r"\d+\s*(?:a\s*\d+)?\s*años?\s*de\s*experiencia", desc_lower
        )
        offer.experience_years = exp_matches[-1] if exp_matches else "No especificado"

        # ── 11. Nivel educativo ───────────────────────────────────────────
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
        """
        Verifica si la oferta aplica para los países aceptados.

        Una oferta se acepta si:
        - Su lista de países está vacía (remoto sin restricción).
        - Al menos uno de sus países está en ACCEPTED_COUNTRIES.
        - Tiene remote=True (interpretado como abierto a LATAM).
        """
        countries: list[str] = attrs.get("countries", [])
        is_remote: bool = attrs.get("remote", False)

        if not countries or is_remote:
            return True

        return bool(set(countries) & self._accepted_countries)

    def _resolve_company(self, company_id: int) -> str:
        """
        Resuelve el ID numérico de empresa a su nombre de texto.

        Usa un caché en memoria para evitar requests repetidas durante
        la misma sesión de scraping.

        Args:
            company_id: ID numérico de la empresa (del campo company.data.id).

        Returns:
            Nombre de la empresa, o cadena vacía si no se pudo resolver.
        """
        if company_id in self._company_cache:
            return self._company_cache[company_id]

        try:
            resp = self._session.get(f"{API_BASE}/companies/{company_id}", timeout=10)
            if resp.status_code == 200:
                name = resp.json().get("data", {}).get("attributes", {}).get("name", "")
                self._company_cache[company_id] = name
                time.sleep(0.5)  # Pequeño delay para no saturar el endpoint
                return name
        except Exception:
            pass

        self._company_cache[company_id] = ""
        return ""

    def _fetch_tags_from_html(self, url: str) -> list[str]:
        """
        Obtiene los nombres de los tags técnicos desde el HTML del detalle.

        La API devuelve tags como IDs numéricos ({id: 1150}). Los nombres
        legibles (ej. "Python", "Docker") solo están disponibles en el HTML
        de la página pública vía `a.gb-tags__item`.

        Args:
            url: URL pública de la oferta en GetOnBoard.

        Returns:
            Lista de strings con los nombres de los tags (ej. ["Python", "Docker"]).
            Lista vacía si el fetch falla o no hay tags.
        """
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
        """
        Formatea el rango salarial de la API a una cadena legible.

        La API provee min_salary y max_salary en USD (numéricos).
        Si ambos son None, retorna "No especificado".

        Args:
            attrs: Diccionario de atributos de la oferta (API JSON).

        Returns:
            Cadena de salario (ej. "USD 2,500 - 4,000" o "No especificado").
        """
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
        """
        Convierte HTML de la descripción a texto plano limpio.

        Args:
            html: String HTML de la descripción/funciones de la oferta.

        Returns:
            Texto plano normalizado para NLP.
        """
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        # Preservar estructura de listas como texto legible
        for li in soup.select("li"):
            li.insert_before("• ")
        text = soup.get_text(separator="\n", strip=True)
        # Colapsar líneas vacías excesivas
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
