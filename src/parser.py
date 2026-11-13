"""
Extracción estructurada de ofertas laborales desde Computrabajo.

Contiene:
    - JobOffer : Re-exportado desde src.models para compatibilidad total.
    - ComputrabajoParser : Implementación de BrowserParser para Computrabajo
      mediante Playwright (renderizado JS) + BeautifulSoup (parseo HTML).
"""

from __future__ import annotations

import re
from bs4 import BeautifulSoup

from src.base_parser import BrowserParser
from src.models import JobOffer
from src.taxonomy import SkillTaxonomyService


class ComputrabajoParser(BrowserParser):
    """
    Parser para computrabajo (.pe, .co, .mx, .cl, .ar) usando Playwright + BeautifulSoup.
    """

    SITE_NAME: str = "computrabajo"
    DEFAULT_BASE_URL: str = "https://pe.computrabajo.com/trabajo-de-desarrollador"

    # Selectores CSS para Computrabajo
    SELECTORS = {
        "listing_links": "a.js-o-link",
        "job_title": "h1",
        "company_location": "div.mt5, h1 + div, h1 + p",
        "description": 'div[div-link="oferta"], section.box_border',
    }

    SUPPORTED_COUNTRIES: dict[str, str] = {
        "pe": "Perú",
        "co": "Colombia",
        "mx": "México",
        "cl": "Chile",
        "ar": "Argentina",
    }

    EXCLUDED_LOCATION_TOKENS: dict[str, list[str]] = {
        "pe": ["lima", "peru", "perú", "arequipa", "trujillo"],
        "co": ["bogota", "bogotá", "colombia", "medellin", "medellín", "cali"],
        "mx": ["mexico", "méxico", "cdmx", "guadalajara", "monterrey"],
        "cl": ["chile", "santiago", "valparaiso", "valparaíso"],
        "ar": ["argentina", "buenos aires", "cordoba", "córdoba", "rosario"],
    }

    def __init__(self, keyword: str = "desarrollador", country: str = "pe"):
        super().__init__()
        self.country = country.lower().strip()
        if self.country not in self.SUPPORTED_COUNTRIES:
            raise ValueError(
                f"País '{country}' no soportado. Opciones: {list(self.SUPPORTED_COUNTRIES.keys())}"
            )
        normalized = keyword.strip().lower().replace(" ", "-")
        self.base_url = (
            f"https://{self.country}.computrabajo.com/trabajo-de-{normalized}"
        )
        self._taxonomy = SkillTaxonomyService.get_instance()

    @property
    def HARD_SKILLS_KEYWORDS(self) -> list[str]:
        return self._taxonomy.hard_skills

    @property
    def SOFT_SKILLS_KEYWORDS(self) -> list[str]:
        return self._taxonomy.soft_skills

    # ------------------------------------------------------------------
    # Interfaz BaseParser (soporta tanto (current_page, page) como (page, current_page))
    # ------------------------------------------------------------------

    def fetch_job_listings(
        self, current_page: int = 1, page=None, **kwargs
    ) -> list[tuple[str, str]]:
        """
        Carga la página de listado con Playwright y extrae (url, título).
        Permite:
            fetch_job_listings(current_page=1, page=page)
            fetch_job_listings(page, current_page)
        """
        import time

        if not isinstance(current_page, int) and isinstance(page, int):
            current_page, page = page, current_page

        active_page = page or self.page
        if active_page is None:
            raise ValueError(
                "ComputrabajoParser requiere una instancia de Playwright Page activa."
            )

        url = f"{self.base_url}?p={current_page}"
        active_page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)
        html = active_page.content()
        return self.parse_listing_page(html)

    def fetch_and_parse_job(self, url: str = "", page=None, **kwargs) -> JobOffer:
        """
        Navega al detalle con Playwright y retorna un JobOffer poblado.
        Permite:
            fetch_and_parse_job(url="...", page=page)
            fetch_and_parse_job(page, url="...")
        """
        import time

        if not isinstance(url, str) and isinstance(page, str):
            url, page = page, url
        if not url and "url" in kwargs:
            url = kwargs["url"]

        active_page = page or self.page
        if active_page is None:
            raise ValueError(
                "ComputrabajoParser requiere una instancia de Playwright Page activa."
            )

        active_page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)
        html = active_page.content()
        return self.parse_job_detail(html, url)

    # ------------------------------------------------------------------
    # Métodos internos de parseo (usables en tests o con HTML renderizado)
    # ------------------------------------------------------------------

    def parse_listing_page(self, html: str) -> list[tuple[str, str]]:
        """
        Extrae (URL, título) de vacantes desde la página de listado.
        """
        soup = BeautifulSoup(html, "lxml")
        links = soup.select(self.SELECTORS["listing_links"]) or soup.select(
            "article a.tw-block"
        )
        seen: set[str] = set()
        entries: list[tuple[str, str]] = []

        for a in links:
            href = a.get("href", "")
            if not href or "/ofertas-de-trabajo/" not in href:
                continue
            if href.startswith("/"):
                href = f"https://{self.country}.computrabajo.com{href}"
            clean_href = href.split("#")[0]
            if clean_href in seen:
                continue
            seen.add(clean_href)

            title = a.get_text(strip=True)
            entries.append((href, title))

        return entries

    def parse_job_detail(self, html: str, url: str) -> JobOffer:
        """
        Parsea una página de detalle y retorna un JobOffer poblado.
        """
        soup = BeautifulSoup(html, "lxml")
        clean_url = url.split("#")[0]
        offer = JobOffer(
            source_url=clean_url, portal=self.SITE_NAME, country=self.country
        )

        # 1. Título
        title_tag = soup.select_one(self.SELECTORS["job_title"])
        offer.job_title = title_tag.get_text(strip=True) if title_tag else ""

        # 2. Metadatos Estructurados (JSON-LD)
        json_data = self.extract_from_json_ld(html)
        if json_data:
            if not offer.company:
                hiring_org = json_data.get("hiringOrganization", {})
                offer.company = (
                    hiring_org.get("name", "")
                    if isinstance(hiring_org, dict)
                    else hiring_org
                )
            if not offer.location:
                loc = json_data.get("jobLocation", {}).get("address", {})
                if isinstance(loc, dict):
                    locality = loc.get("addressLocality", "")
                    region = loc.get("addressRegion", "")
                    address = f"{locality}, {region}".strip(", ")
                    offer.location = address
            if not offer.salary:
                base_salary = json_data.get("baseSalary", {})
                if isinstance(base_salary, dict):
                    val = base_salary.get("value", {})
                    if isinstance(val, dict):
                        min_val = val.get("minValue")
                        max_val = val.get("maxValue")
                        curr = val.get("unitText", "")
                        if min_val and max_val:
                            offer.salary = f"{curr} {min_val} - {max_val}".strip()
            if not offer.experience_years:
                exp = json_data.get("experienceRequirements", {})
                if isinstance(exp, dict) and exp.get("monthsOfExperience"):
                    months = int(exp.get("monthsOfExperience", 0))
                    offer.experience_years = (
                        f"{months // 12} years" if months >= 12 else f"{months} months"
                    )
                elif isinstance(exp, str):
                    offer.experience_years = exp

        # 3. Empresa: "Acerca de"
        if not offer.company or len(offer.company) < 3:
            for h2 in soup.find_all("h2"):
                h2_text = h2.get_text(" ", strip=True)
                if "Acerca de" in h2_text:
                    company_name = h2_text.replace("Acerca de", "").strip()
                    company_name = company_name.replace("\xa0", " ").strip()
                    if company_name and not any(
                        x in company_name
                        for x in ["Buscar", "Evaluaciones", "Ver todas"]
                    ):
                        offer.company = company_name
                        break

        # 4. Empresa: Sidebar
        if not offer.company or "Buscar" in offer.company:
            sidebar = soup.select_one(
                "div.box_border.pAll.tc, section.box_border, div.box_resume"
            )
            if sidebar:
                comp_tag = sidebar.select_one("p.fs16.fwB, a.fwB")
                if comp_tag and not any(
                    x in comp_tag.text for x in ["Ver todas", "Evaluaciones"]
                ):
                    offer.company = comp_tag.get_text(strip=True)

        # 5. Empresa / Ubicación: Header
        if not offer.company or not offer.location:
            header_info = soup.select_one("div.mt5, div.pAllB.tc, h1 + p, h1 + div")
            if header_info:
                for a in header_info.select('a[href*="/empresas/"]'):
                    txt = a.get_text(strip=True)
                    if txt and not any(
                        x in txt for x in ["Buscar", "Evaluaciones", "Ver todas"]
                    ):
                        offer.company = txt
                        break

                header_copy = BeautifulSoup(str(header_info), "html.parser")
                if header_copy.h1:
                    header_copy.h1.decompose()
                for icon in header_copy.select('.icon, i, span[class*="icon"]'):
                    icon.decompose()

                txt_full = header_copy.get_text(" | ", strip=True)
                if " - " in txt_full:
                    parts = txt_full.split(" - ")
                    if len(parts) >= 2:
                        potential_loc = parts[-1].split(" | ")[0].strip()
                        potential_comp = parts[0].split(" | ")[-1].strip()
                        if not offer.location:
                            offer.location = potential_loc
                        if not offer.company:
                            offer.company = potential_comp
                elif " | " in txt_full:
                    parts = txt_full.split(" | ")
                    if len(parts) >= 2:
                        if not offer.company:
                            offer.company = parts[0].strip()
                        if not offer.location:
                            offer.location = parts[1].strip()

        # Ubicación desde Breadcrumbs
        if not offer.location or len(offer.location) > 45:
            bc = soup.select("ol.breadcrumb li, ul.breadcrumb li")
            if len(bc) >= 2:
                offer.location = bc[-2].get_text(strip=True)

        # Limpieza de Empresa
        if offer.company:
            offer.company = (
                offer.company.replace("Empresa garantizada", "")
                .replace("Confidencial", "")
                .strip()
            )
            if offer.company.lower() == offer.job_title.lower():
                offer.company = ""
            if offer.company.lower() in ["buscar empresas", "evaluaciones de empresas"]:
                offer.company = ""

        # Fallback OG Title (con descarte geográfico según país)
        if not offer.company:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title:
                content = og_title.get("content", "")
                if " en " in content:
                    parts = content.split(" en ")
                    if len(parts) > 1:
                        rem = parts[1].split(" - ")
                        if len(rem) > 1:
                            offer.company = rem[0].strip()
                            if not offer.location:
                                offer.location = rem[1].strip()
                        else:
                            potential = rem[0].strip()
                            country_excluded = self.EXCLUDED_LOCATION_TOKENS.get(
                                self.country,
                                ["peru", "colombia", "mexico", "chile", "argentina"],
                            )
                            if not any(
                                x in potential.lower() for x in country_excluded
                            ):
                                offer.company = potential

        # Fallback de seguridad para Ubicación
        if not offer.location or len(offer.location) > 50:
            loc_match = re.search(r"([A-Z][a-z]+, [A-Z][a-z]+)$", offer.job_title)
            if loc_match:
                offer.location = loc_match.group(1)
            else:
                bc = soup.select("ol.breadcrumb li")
                if len(bc) >= 3:
                    offer.location = bc[-2].get_text(strip=True)

        # Descripción
        desc_tag = soup.select_one(self.SELECTORS["description"])
        if not desc_tag:
            desc_heading = soup.find(
                lambda tag: tag.name in ["h2", "h1", "p"]
                and tag.text
                and "Descripción de la oferta" in tag.text
            )
            if desc_heading and desc_heading.parent:
                desc_tag = desc_heading.parent

        if desc_tag:
            desc_copy = BeautifulSoup(str(desc_tag), "html.parser")
            for tag in desc_copy.select("span.tag, p.tag, div.tag, .mbB.fs16"):
                tag.decompose()

            text = desc_copy.get_text(separator="\n", strip=True).strip()
            noise_headers = [
                r"Descripción de la oferta\s*",
                r"Descripción\s*\n",
            ]
            for pattern in noise_headers:
                text = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)
            offer.full_description = text.strip()
        else:
            offer.full_description = ""

        # Salario (Multi-moneda LATAM)
        all_text = soup.get_text(separator=" ", strip=True)
        found_placeholder = False
        currency_identifiers = [
            "S/",
            "$",
            "COP",
            "MXN",
            "CLP",
            "ARS",
            "USD",
            "EUR",
            "PEN",
        ]

        for tag in soup.select("span.tag, p.tag"):
            t_txt = tag.get_text(strip=True)
            if any(curr in t_txt for curr in currency_identifiers) and any(
                c.isdigit() for c in t_txt
            ):
                offer.salary = t_txt
                break
            if "A convenir" in t_txt or "a convenir" in t_txt:
                found_placeholder = True

        if not offer.salary or "A convenir" in offer.salary:
            # Regex robusto multi-moneda LATAM
            currency_pattern = r"(?:S/\.?|\$|USD|EUR|COP|MXN|CLP|ARS|PEN)"
            num_pattern = r"\d{1,3}(?:[.,\s\']\d{3})*(?:[.,]\d{2})?"
            salary_pattern = (
                rf"{currency_pattern}\s*{num_pattern}"
                rf"(?:\s*-\s*{currency_pattern}?\s*{num_pattern})?"
            )
            salary_match = re.search(salary_pattern, all_text, re.IGNORECASE)
            if salary_match:
                offer.salary = salary_match.group(0).strip()
            elif found_placeholder or "a convenir" in all_text.lower():
                offer.salary = "A convenir"

        # Modalidad
        if any(w in all_text.lower() for w in ["remoto", "desde casa", "teletrabajo"]):
            offer.modality = "Remoto"
        elif "híbrido" in all_text.lower() or "hibrido" in all_text.lower():
            offer.modality = "Híbrido"
        else:
            offer.modality = "Presencial"

        # Fecha de publicación
        date_match = re.search(
            r"Hace\s\d+\s(días|dias|horas|minutos)|Ayer|Hoy", all_text, re.IGNORECASE
        )
        offer.date_posted = date_match.group(0) if date_match else "Reciente"

        # Extracción de skills mediante SkillTaxonomyService
        hard_skills, soft_skills = self._taxonomy.extract_skills(offer.full_description)
        offer.hard_skills = hard_skills
        offer.soft_skills = soft_skills

        # Años de experiencia (última mención)
        desc_lower = offer.full_description.lower()
        exp_matches = re.findall(
            r"\d+\s*(?:a\s*\d+)?\s*años?\s*de\s*experiencia", desc_lower
        )
        offer.experience_years = exp_matches[-1] if exp_matches else "No especificado"

        # Nivel educativo
        edu_map = {
            "universitaria": [
                "universidad",
                "ingeniería",
                "ingenieria",
                "licenciatura",
                "bachiller",
            ],
            "técnica": ["técnico", "tecnico", "instituto", "cetpro"],
            "maestría": ["maestría", "maestria", "mba", "postgrado", "posgrado"],
        }
        offer.education_level = "No especificado"
        for level, keywords in edu_map.items():
            if any(k in desc_lower for k in keywords):
                offer.education_level = level
                break

        return offer


# Alias de compatibilidad hacia atrás
JobParser = ComputrabajoParser
