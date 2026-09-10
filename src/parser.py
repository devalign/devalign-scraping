"""
Extracción estructurada de ofertas laborales desde Computrabajo.

Contiene:
    - JobOffer : Dataclass con el schema de datos compartido por todos los parsers.
    - ComputrabajoParser : Implementación de BaseParser para pe.computrabajo.com
      mediante Playwright (renderizado JS) + BeautifulSoup (parseo HTML).

Nota: `JobParser` es un alias de compatibilidad hacia atrás. Usar `ComputrabajoParser`
      en código nuevo.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.base_parser import BaseParser


@dataclass
class JobOffer:
    """
    Schema de datos de una oferta laboral.
    Coincide 1:1 con las columnas del CSV de salida.
    """

    job_title: str = ""
    company: str = ""
    location: str = ""
    salary: str = ""  # Ej: "S/. 3,500", "A convenir"
    modality: str = ""  # Ej: "Remoto", "Presencial", "Híbrido"
    date_posted: str = ""  # Ej: "Hace 2 días", "Ayer"
    hard_skills: list = field(default_factory=list)
    soft_skills: list = field(default_factory=list)
    experience_years: str = ""  # Ej: "2-4", "5+", "No especificado"
    education_level: str = ""  # Ej: "universitaria", "técnica", "indiferente"
    full_description: str = ""  # TEXTO ÍNTEGRO — crítico para IA
    source_url: str = ""
    portal: str = ""  # Ej: "computrabajo", "getonboard"
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ComputrabajoParser(BaseParser):
    """
    Parser para pe.computrabajo.com usando Playwright + BeautifulSoup.

    Implementa la interfaz BaseParser. Usa un browser headless (Playwright)
    para renderizar JS y BeautifulSoup para parsear el HTML resultante.

    Métodos de la interfaz BaseParser:
        - fetch_job_listings  : carga la página de listado con Playwright
        - fetch_and_parse_job : navega al detalle y lo parsea

    Métodos internos (usables directamente en tests o debug):
        - parse_listing_page  : parsea HTML de listado ya renderizado
        - parse_job_detail    : parsea HTML de detalle ya renderizado
    """

    SITE_NAME: str = "computrabajo"
    DEFAULT_BASE_URL: str = "https://pe.computrabajo.com/trabajo-de-desarrollador"

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
    ]

    # Selectores CSS para Computrabajo (Actualizados Mayo 2026)
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

    def __init__(self, keyword: str = "desarrollador", country: str = "pe"):
        """
        Inicializa el parser con una palabra clave de búsqueda y país específico.
        Normaliza espacios a guiones para la URL.
        """
        self.country = country.lower().strip()
        if self.country not in self.SUPPORTED_COUNTRIES:
            raise ValueError(
                f"País '{country}' no soportado. Opciones: {list(self.SUPPORTED_COUNTRIES.keys())}"
            )
        normalized = keyword.strip().lower().replace(" ", "-")
        self.base_url = (
            f"https://{self.country}.computrabajo.com/trabajo-de-{normalized}"
        )

    # ------------------------------------------------------------------
    # Interfaz BaseParser
    # ------------------------------------------------------------------

    def fetch_job_listings(self, page, current_page: int) -> list[tuple[str, str]]:
        """
        Carga la página de listado con Playwright y extrae (url, título).

        Args:
            page:         Playwright Page activo.
            current_page: Número de página (1-indexed).

        Returns:
            Lista de tuplas (url, titulo). Vacía si no hay más resultados.
        """
        import time

        url = f"{self.base_url}?p={current_page}"
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)
        html = page.content()
        return self.parse_listing_page(html)

    def fetch_and_parse_job(self, page, url: str) -> JobOffer:
        """
        Navega al detalle con Playwright y retorna un JobOffer poblado.

        Args:
            page: Playwright Page activo.
            url:  URL pública de la oferta en Computrabajo.

        Returns:
            JobOffer con todos los campos disponibles poblados.
        """
        import time

        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1)
        html = page.content()
        return self.parse_job_detail(html, url)

    # ------------------------------------------------------------------
    # Métodos internos de parseo (también usables en tests)
    # ------------------------------------------------------------------

    def parse_listing_page(self, html: str) -> list[tuple[str, str]]:
        """
        Extrae (URL, título) de vacantes desde la página de listado.

        Retorna tuplas en vez de solo URLs para permitir pre-filtrado por
        título antes de navegar al detalle (ahorra ~5-8 seg por oferta).

        Returns:
            Lista de tuplas (url_completa, titulo_visible). El título puede
            ser una cadena vacía si el anchor no tiene texto.
        """
        soup = BeautifulSoup(html, "lxml")
        # Intentar varios selectores de links por si cambia la clase
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
            # Deduplicar por URL (sin fragmento de tracking)
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
        # Normalizar URL quitando fragmentos de tracking (ej. #lc=ListOffers...)
        clean_url = url.split("#")[0]
        offer = JobOffer(source_url=clean_url, portal=self.SITE_NAME)

        # 1. Título (Más robusto)
        title_tag = soup.select_one(self.SELECTORS["job_title"])
        offer.job_title = title_tag.get_text(strip=True) if title_tag else ""

        # 2. Empresa y Ubicación (Extracción Quirúrgica)
        # PRIORIDAD 1: Metadatos Estructurados (JSON-LD) - Es lo más preciso
        json_data = self.extract_from_json_ld(html)
        if json_data:
            # Empresa
            if not offer.company:
                hiring_org = json_data.get("hiringOrganization", {})
                offer.company = (
                    hiring_org.get("name", "")
                    if isinstance(hiring_org, dict)
                    else hiring_org
                )
            # Ubicación
            if not offer.location:
                loc = json_data.get("jobLocation", {}).get("address", {})
                if isinstance(loc, dict):
                    locality = loc.get("addressLocality", "")
                    region = loc.get("addressRegion", "")
                    address = f"{locality}, {region}".strip(", ")
                    offer.location = address
            # Salario
            if not offer.salary:
                base_salary = json_data.get("baseSalary", {})
                if isinstance(base_salary, dict):
                    val = base_salary.get("value", {})
                    if isinstance(val, dict):
                        min_val = val.get("minValue")
                        max_val = val.get("maxValue")
                        curr = val.get("unitText", "")
                        if min_val and max_val:
                            offer.salary = f"{curr} {min_val} - {max_val}"
            # Experiencia
            if not offer.experience_years:
                exp = json_data.get("experienceRequirements", {})
                if isinstance(exp, dict) and exp.get("monthsOfExperience"):
                    months = int(exp.get("monthsOfExperience", 0))
                    offer.experience_years = (
                        f"{months // 12} years" if months >= 12 else f"{months} months"
                    )
                elif isinstance(exp, str):
                    offer.experience_years = exp

        # PRIORIDAD 2: "Acerca de" (Súper fiable si existe)
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

        # PRIORIDAD 3: Selectores de Sidebar (Si aún no tenemos empresa)
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

        # PRIORIDAD 4: Limpieza de texto en el Header (Debajo del H1)
        if not offer.company or not offer.location:
            header_info = soup.select_one("div.mt5, div.pAllB.tc, h1 + p, h1 + div")
            if header_info:
                # Intentamos sacar la empresa de un link de empresa
                for a in header_info.select('a[href*="/empresas/"]'):
                    txt = a.get_text(strip=True)
                    if txt and not any(
                        x in txt for x in ["Buscar", "Evaluaciones", "Ver todas"]
                    ):
                        offer.company = txt
                        break

                # Análisis de texto plano en el header (excluyendo el H1 e iconos para evitar ruido)
                header_copy = BeautifulSoup(str(header_info), "html.parser")
                if header_copy.h1:
                    header_copy.h1.decompose()
                # Eliminar iconos
                for icon in header_copy.select('.icon, i, span[class*="icon"]'):
                    icon.decompose()

                txt_full = header_copy.get_text(" | ", strip=True)

                # Si hay guion " - ", suele ser "Empresa - Ubicación"
                if " - " in txt_full:
                    parts = txt_full.split(" - ")
                    if len(parts) >= 2:
                        potential_loc = parts[-1].split(" | ")[0].strip()
                        potential_comp = parts[0].split(" | ")[-1].strip()

                        # Validamos que no estemos poniendo la ubicación en la empresa
                        if not offer.location:
                            offer.location = potential_loc
                        if not offer.company:
                            offer.company = potential_comp
                elif " | " in txt_full:
                    # Formato "Empresa | Ubicación"
                    parts = txt_full.split(" | ")
                    if len(parts) >= 2:
                        if not offer.company:
                            offer.company = parts[0].strip()
                        if not offer.location:
                            offer.location = parts[1].strip()

        # PRIORIDAD 4: "Acerca de" (Súper fiable si existe)
        # (Ya cubierto arriba en Prioridad 2, pero dejamos fallback si se saltó)

        # FALLBACK: Ubicación desde Breadcrumbs (Súper fiable en Computrabajo)
        if not offer.location or len(offer.location) > 45:
            bc = soup.select("ol.breadcrumb li, ul.breadcrumb li")
            if len(bc) >= 2:
                # El penúltimo suele ser la ciudad/distrito
                offer.location = bc[-2].get_text(strip=True)

        # PRIORIDAD 5: Limpieza Final y Validaciones
        if offer.company:
            offer.company = (
                offer.company.replace("Empresa garantizada", "")
                .replace("Confidencial", "")
                .strip()
            )
            # Si la empresa es igual al título del trabajo, probablemente es un error de parseo
            if offer.company.lower() == offer.job_title.lower():
                offer.company = ""
            if offer.company.lower() in ["buscar empresas", "evaluaciones de empresas"]:
                offer.company = ""

        # FALLBACK: Metatags OG (Con cuidado de no capturar ubicación como empresa)
        if not offer.company:
            og_title = soup.select_one('meta[property="og:title"]')
            if og_title:
                content = og_title.get("content", "")
                if " en " in content:
                    # Formato: "Trabajo de [Cargo] en [Empresa] - [Ubicación]"
                    parts = content.split(" en ")
                    if len(parts) > 1:
                        # El resto suele ser "Empresa - Ubicación"
                        rem = parts[1].split(" - ")
                        if len(rem) > 1:
                            offer.company = rem[0].strip()
                            if not offer.location:
                                offer.location = rem[1].strip()
                        else:
                            # Si no hay guion, es arriesgado, pero intentamos
                            potential = rem[0].strip()
                            if not any(
                                x in potential.lower()
                                for x in ["lima", "peru", "arequipa"]
                            ):
                                offer.company = potential

        # Fallback de seguridad para Ubicación
        if not offer.location or len(offer.location) > 50:
            # Buscar texto que parezca ubicación (Departamento, Distrito)
            # Computrabajo suele ponerlo al final de ciertos párrafos
            loc_match = re.search(r"([A-Z][a-z]+, [A-Z][a-z]+)$", offer.job_title)
            if loc_match:
                offer.location = loc_match.group(1)
            else:
                # Intentar sacar del breadcrumb si existe
                bc = soup.select("ol.breadcrumb li")
                if len(bc) >= 3:
                    offer.location = bc[-2].get_text(strip=True)

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

        # LIMPIEZA DE REDUNDANCIA:
        # Quitamos etiquetas de UI que se repiten (Salario, Modalidad, etc. que ya extrajimos)
        if desc_tag:
            desc_copy = BeautifulSoup(str(desc_tag), "html.parser")

            # 1. Eliminar tags de metadatos (A convenir, Tiempo completo, etc.)
            for tag in desc_copy.select("span.tag, p.tag, div.tag, .mbB.fs16"):
                tag.decompose()

            # 2. Obtener texto y limpiar encabezados residuales
            text = desc_copy.get_text(separator="\n", strip=True)
            text = (
                text.strip()
            )  # Remove any leading whitespace that breaks the ^ anchor

            # Eliminar "Descripción de la oferta" y variantes
            # (suele estar al inicio pero puede tener caracteres invisibles antes)
            noise_headers = [
                r"Descripción de la oferta\s*",
                r"Descripción\s*\n",  # Solo si es un header solitario seguido de salto de línea
            ]
            for pattern in noise_headers:
                text = re.sub(pattern, "", text, count=1, flags=re.IGNORECASE)

            offer.full_description = text.strip()
        else:
            offer.full_description = ""

        # Salario, Modalidad y Fecha (Extracción por texto)
        # Computrabajo suele poner estos datos en etiquetas p o span con iconos
        all_text = soup.get_text(separator=" ", strip=True)

        # Salario (Extracción por texto y por tags)
        # Buscamos en los tags, pero preferimos los que tienen montos (S/)
        found_placeholder = False
        for tag in soup.select("span.tag, p.tag"):
            t_txt = tag.get_text(strip=True)
            if "S/" in t_txt:
                offer.salary = t_txt
                break
            if "A convenir" in t_txt:
                found_placeholder = True

        if not offer.salary or "A convenir" in offer.salary:
            # Regex mejorada:
            # 1. Busca S/ seguido de números
            # 2. Permite texto intermedio corto (como "más", "movilidad", "+")
            # Ejemplo: "S/ 1130 + Movilidad S/ 300"
            num_grp = r"\d+(?:[.,\s]\d+)*"
            salary_pattern = (
                rf"S/[.\s]*{num_grp}(?:\s*[^0-9]{{1,20}}\s*S/[.\s]*{num_grp})*"
            )
            salary_match = re.search(salary_pattern, all_text)
            if salary_match:
                offer.salary = salary_match.group(0).strip()
            elif found_placeholder:
                offer.salary = "A convenir"
            elif "A convenir" in all_text:
                offer.salary = "A convenir"

        # Modalidad
        if any(w in all_text.lower() for w in ["remoto", "desde casa", "teletrabajo"]):
            offer.modality = "Remoto"
        elif "híbrido" in all_text.lower():
            offer.modality = "Híbrido"
        else:
            offer.modality = "Presencial"

        # Fecha de publicación
        date_match = re.search(r"Hace\s\d+\s(días|horas|minutos)|Ayer|Hoy", all_text)
        offer.date_posted = date_match.group(0) if date_match else "Reciente"

        # Extracción semi-automática de skills desde la descripción con word boundaries
        desc_lower = offer.full_description.lower()

        # Usamos regex para asegurar que sean palabras completas (evita "react" en "reactivar")
        offer.hard_skills = [
            s
            for s in self.HARD_SKILLS_KEYWORDS
            if re.search(rf"\b{re.escape(s)}\b", desc_lower)
        ]
        offer.soft_skills = [
            s
            for s in self.SOFT_SKILLS_KEYWORDS
            if re.search(rf"\b{re.escape(s)}\b", desc_lower)
        ]

        # Años de experiencia con regex (Tomamos la ÚLTIMA mención)
        # Esto evita capturar cosas como "Empresa con 24 años de experiencia en el mercado"
        # ya que los requerimientos reales del candidato suelen estar al final del texto.
        exp_matches = re.findall(
            r"\d+\s*(?:a\s*\d+)?\s*años?\s*de\s*experiencia", desc_lower
        )
        offer.experience_years = exp_matches[-1] if exp_matches else "No especificado"

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


# Alias de compatibilidad hacia atrás.
# Los imports existentes (`from src.parser import JobParser`) seguirán funcionando.
# En código nuevo, usar ComputrabajoParser directamente.
JobParser = ComputrabajoParser
