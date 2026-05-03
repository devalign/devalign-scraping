"""
Extracción estructurada de ofertas laborales desde HTML.

Contiene el schema de datos (JobOffer) y la lógica de parseo (JobParser)
para páginas de listado y detalle de Computrabajo.
"""

import json
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
    salary: str = ""  # Ej: "S/. 3,500", "A convenir"
    modality: str = ""  # Ej: "Remoto", "Presencial", "Híbrido"
    date_posted: str = ""  # Ej: "Hace 2 días", "Ayer"
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
        "python", "java", "javascript", "typescript", "react", "angular", "node",
        "django", "fastapi", "sql", "postgresql", "mongodb", "docker", "kubernetes",
        "aws", "gcp", "azure", "git", "ci/cd", "machine learning", "tensorflow",
        "scikit-learn", "pandas", ".net", "c#", "php", "laravel", "vue", "next.js",
        "flask", "redis", "mysql", "linux", "terraform", "jenkins", "jira", "figma",
        "html", "css", "sass", "graphql", "rest api", "microservicios", "scrum",
        "agile", "flutter", "dart", "kotlin", "swift", "go", "ruby", "rails",
        "spring boot", "unity", "unreal engine", "blockchain", "solidity",
        "power bi", "tableau", "excel", "ux/ui", "adobe xd", "kanban", "devops",
        "cybersecurity", "qa", "selenium", "cypress", "jest", "backend", "frontend",
        "fullstack"
    ]

    SOFT_SKILLS_KEYWORDS = [
        "comunicación", "trabajo en equipo", "liderazgo", "proactivo",
        "resolución de problemas", "adaptabilidad", "gestión del tiempo",
        "creatividad", "orientado a resultados", "colaboración",
        "pensamiento crítico", "negociación", "empatía", "autonomía",
        "responsabilidad", "organización", "atención al detalle",
        "tolerancia a la frustración", "capacidad de análisis", "aprendizaje rápido"
    ]

    # Selectores CSS para Computrabajo (Actualizados Mayo 2026)
    SELECTORS = {
        "listing_links": "a.js-o-link",
        "job_title": "h1",
        "company_location": "div.mt5, h1 + div, h1 + p",
        "description": 'div[div-link="oferta"], section.box_border',
    }

    def parse_listing_page(self, html: str) -> list[str]:
        """
        Extrae URLs individuales de vacantes desde la página de listado.
        """
        soup = BeautifulSoup(html, "lxml")
        # Intentar varios selectores de links por si cambia la clase
        links = soup.select(self.SELECTORS["listing_links"]) or soup.select("article a.tw-block")
        urls = []
        for a in links:
            href = a.get("href", "")
            if href and "/ofertas-de-trabajo/" in href:
                if href.startswith("/"):
                    href = f"https://pe.computrabajo.com{href}"
                urls.append(href)
        return list(set(urls))

    def parse_job_detail(self, html: str, url: str) -> JobOffer:
        """
        Parsea una página de detalle y retorna un JobOffer poblado.
        """
        soup = BeautifulSoup(html, "lxml")
        offer = JobOffer(source_url=url)

        # 1. Título (Más robusto)
        title_tag = soup.select_one(self.SELECTORS["job_title"])
        offer.job_title = title_tag.get_text(strip=True) if title_tag else ""

        # 2. Empresa y Ubicación (Extracción Quirúrgica)
        # PRIORIDAD 1: Metadatos Estructurados (JSON-LD) - Es lo más preciso
        json_ld = soup.select('script[type="application/ld+json"]')
        for script in json_ld:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    if not offer.company:
                        hiring_org = data.get("hiringOrganization", {})
                        offer.company = hiring_org.get("name", "") if isinstance(hiring_org, dict) else hiring_org
                    if not offer.location:
                        loc = data.get("jobLocation", {}).get("address", {})
                        if isinstance(loc, dict):
                            address = f"{loc.get('addressLocality', '')}, {loc.get('addressRegion', '')}".strip(", ")
                            offer.location = address
            except Exception:
                continue

        # PRIORIDAD 2: "Acerca de" (Súper fiable si existe)
        if not offer.company or len(offer.company) < 3:
            for h2 in soup.find_all('h2'):
                h2_text = h2.get_text(" ", strip=True)
                if 'Acerca de' in h2_text:
                    company_name = h2_text.replace('Acerca de', '').strip()
                    company_name = company_name.replace('\xa0', ' ').strip()
                    if company_name and not any(x in company_name for x in ["Buscar", "Evaluaciones", "Ver todas"]):
                        offer.company = company_name
                        break

        # PRIORIDAD 3: Selectores de Sidebar (Si aún no tenemos empresa)
        if not offer.company or "Buscar" in offer.company:
            sidebar = soup.select_one('div.box_border.pAll.tc, section.box_border, div.box_resume')
            if sidebar:
                comp_tag = sidebar.select_one('p.fs16.fwB, a.fwB')
                if comp_tag and not any(x in comp_tag.text for x in ["Ver todas", "Evaluaciones"]):
                    offer.company = comp_tag.get_text(strip=True)

        # PRIORIDAD 4: Limpieza de texto en el Header (Debajo del H1)
        if not offer.company or not offer.location:
            header_info = soup.select_one("div.mt5, div.pAllB.tc, h1 + p, h1 + div")
            if header_info:
                # Intentamos sacar la empresa de un link de empresa
                for a in header_info.select('a[href*="/empresas/"]'):
                    txt = a.get_text(strip=True)
                    if txt and not any(x in txt for x in ["Buscar", "Evaluaciones", "Ver todas"]):
                        offer.company = txt
                        break
                
                # Análisis de texto plano en el header (excluyendo el H1 e iconos para evitar ruido)
                header_copy = BeautifulSoup(str(header_info), 'html.parser')
                if header_copy.h1: header_copy.h1.decompose()
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
                        if not offer.company: offer.company = parts[0].strip()
                        if not offer.location: offer.location = parts[1].strip()

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
            offer.company = offer.company.replace("Empresa garantizada", "").replace("Confidencial", "").strip()
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
                            if not offer.location: offer.location = rem[1].strip()
                        else:
                            # Si no hay guion, es arriesgado, pero intentamos
                            potential = rem[0].strip()
                            if not any(x in potential.lower() for x in ["lima", "peru", "arequipa"]):
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
            desc_copy = BeautifulSoup(str(desc_tag), 'html.parser')
            
            # 1. Eliminar tags de metadatos (A convenir, Tiempo completo, etc.)
            for tag in desc_copy.select('span.tag, p.tag, div.tag, .mbB.fs16'):
                tag.decompose()

            # 2. Obtener texto y limpiar encabezados residuales
            text = desc_copy.get_text(separator="\n", strip=True)
            text = text.strip()  # Remove any leading whitespace that breaks the ^ anchor
            
            # Eliminar "Descripción de la oferta" y variantes (suele estar al inicio pero puede tener caracteres invisibles antes)
            noise_headers = [
                r"Descripción de la oferta\s*",
                r"Descripción\s*\n", # Solo si es un header solitario seguido de salto de línea
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
            salary_pattern = r"S/[.\s]*\d+(?:[.,\s]\d+)*(?:\s*[^0-9]{1,20}\s*S/[.\s]*\d+(?:[.,\s]\d+)*)*"
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
            s for s in self.HARD_SKILLS_KEYWORDS 
            if re.search(rf"\b{re.escape(s)}\b", desc_lower)
        ]
        offer.soft_skills = [
            s for s in self.SOFT_SKILLS_KEYWORDS 
            if re.search(rf"\b{re.escape(s)}\b", desc_lower)
        ]

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
