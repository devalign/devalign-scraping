"""
Extracción estructurada de ofertas laborales desde HTML.

Contiene el schema de datos (JobOffer) y la lógica de parseo (JobParser)
para páginas de listado y detalle de Computrabajo.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bs4 import BeautifulSoup


@dataclass
class JobOffer:
    """
    Schema de datos de una oferta laboral.
    Coincide 1:1 con las columnas del CSV de salida.
    """

    job_title: str = ""
    company: str = ""
    location: str = ""
    hard_skills: list = field(default_factory=list)
    soft_skills: list = field(default_factory=list)
    experience_years: str = ""  # Ej: "2-4", "5+", "No especificado"
    education_level: str = ""  # Ej: "universitaria", "técnica", "indiferente"
    full_description: str = ""  # TEXTO ÍNTEGRO — crítico para IA
    source_url: str = ""
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class JobParser:
    """
    Parsea HTML de Computrabajo para extraer datos estructurados.

    Dos métodos principales:
    - parse_listing_page: extrae URLs de vacantes desde la página de listado
    - parse_job_detail: parsea el detalle completo de una vacante individual
    """

    # Diccionarios de referencia para clasificación semi-automática
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
    ]

    # Selectores CSS para Computrabajo (Actualizados 2026-04-24)
    SELECTORS = {
        "listing_links": "a.js-o-link",
        "job_title": "h1.fwB",
        "company_location": "h1.fwB + p",
        "description": 'div[div-link="oferta"]',
    }

    def parse_listing_page(self, html: str) -> list[str]:
        """
        Extrae URLs individuales de vacantes desde la página de listado.

        Args:
            html: HTML renderizado de la página de listado.

        Returns:
            Lista de URLs absolutas de vacantes individuales.
        """
        soup = BeautifulSoup(html, "lxml")
        links = soup.select(self.SELECTORS["listing_links"])
        urls = []
        for a in links:
            href = a.get("href", "")
            if href:
                # Asegurar URL absoluta
                if href.startswith("/"):
                    href = f"https://pe.computrabajo.com{href}"
                urls.append(href)
        return urls

    def parse_job_detail(self, html: str, url: str) -> JobOffer:
        """
        Parsea una página de detalle y retorna un JobOffer poblado.

        IMPORTANTE: full_description captura el texto ÍNTEGRO sin filtrar.
        La limpieza se delega al TextCleaner.

        Args:
            html: HTML renderizado de la página de detalle.
            url: URL de origen de la vacante.

        Returns:
            JobOffer con todos los campos poblados.
        """
        soup = BeautifulSoup(html, "lxml")
        offer = JobOffer(source_url=url)

        # Título
        title_tag = soup.select_one(self.SELECTORS["job_title"])
        offer.job_title = title_tag.get_text(strip=True) if title_tag else ""

        # Empresa y Ubicación (Vienen en un mismo tag en el nuevo DOM)
        comp_loc_tag = soup.select_one(self.SELECTORS["company_location"])
        if comp_loc_tag:
            text = comp_loc_tag.get_text(strip=True)
            if " - " in text:
                parts = text.split(" - ", 1)
                offer.company = parts[0].strip()
                offer.location = parts[1].strip()
            else:
                offer.company = text

        # Fallback para versiones móviles o variaciones del DOM
        if not offer.company:
            # Intentar buscar el link de empresa si existe
            company_link = soup.select_one('a[href*="/empresas/"]')
            if company_link:
                offer.company = company_link.get_text(strip=True)

        # Descripción íntegra — NO filtrar aquí, el cleaner lo hará
        desc_tag = soup.select_one(self.SELECTORS["description"])

        # Fallback para versiones móviles o DOM en headless
        if not desc_tag:
            desc_heading = soup.find(
                lambda tag: tag.name in ["h2", "h1", "p"]
                and tag.text
                and "Descripción de la oferta" in tag.text
            )
            if desc_heading and desc_heading.parent:
                desc_tag = desc_heading.parent

        offer.full_description = (
            desc_tag.get_text(separator="\n", strip=True) if desc_tag else ""
        )

        # Extracción semi-automática de skills desde la descripción
        desc_lower = offer.full_description.lower()
        offer.hard_skills = [s for s in self.HARD_SKILLS_KEYWORDS if s in desc_lower]
        offer.soft_skills = [s for s in self.SOFT_SKILLS_KEYWORDS if s in desc_lower]

        # Años de experiencia con regex
        exp_match = re.search(
            r"(\d+)\s*(?:a\s*\d+)?\s*años?\s*de\s*experiencia", desc_lower
        )
        offer.experience_years = exp_match.group(0) if exp_match else "No especificado"

        # Nivel educativo
        edu_map = {
            "universitaria": [
                "universidad",
                "ingeniería",
                "licenciatura",
                "bachiller",
            ],
            "técnica": ["técnico", "instituto", "cetpro"],
            "maestría": ["maestría", "mba", "postgrado"],
        }
        offer.education_level = "No especificado"
        for level, keywords in edu_map.items():
            if any(k in desc_lower for k in keywords):
                offer.education_level = level
                break

        return offer
