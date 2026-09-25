"""
Filtrado centralizado de ofertas laborales.

Principio: filtrar lo antes posible para no desperdiciar tiempo de scraping.

Dos capas de filtrado:
    1. is_relevant(title, url) — Pre-filtro rápido, antes de navegar al detalle.
       Descarta no-IT por título visible o slug de URL (sin costo de red).
    2. is_valid_it_job(offer) — Post-filtro completo, después de parsear.
       Valida calidad mínima: al menos una skill técnica y descripción suficiente.
"""

from __future__ import annotations

import re


class JobFilter:
    """
    Filtro de dos capas para descartar ofertas no-IT o de baja calidad.

    Uso típico en el loop de scraping:
        filter = JobFilter()

        # Capa 1: antes de navegar al detalle (sin costo de red)
        if not filter.is_relevant(title, url):
            continue

        # ... fetch_page, parse_job_detail, clean ...

        # Capa 2: después de parsear (requiere JobOffer completo)
        if not filter.is_valid_it_job(offer):
            continue

        session.add_offer(offer)
    """

    # Palabras en el TÍTULO que indican un rol tecnológico explícito.
    # Si están presentes, eximen a la oferta de la blacklist
    # (ej. "Salesforce Developer", "Marketing Data Engineer").
    IT_EXEMPTION_KEYWORDS: list[str] = [
        # Roles tech compuestos en inglés
        "software engineer",
        "data engineer",
        "cloud engineer",
        "devops engineer",
        "qa engineer",
        "systems engineer",
        "machine learning engineer",
        "software developer",
        "web developer",
        "frontend developer",
        "backend developer",
        "full stack developer",
        "fullstack developer",
        "mobile developer",
        "android developer",
        "ios developer",
        "salesforce developer",
        "bi developer",
        "data scientist",
        "cloud architect",
        "software architect",
        "solutions architect",
        # Roles tech compuestos en español
        "ingeniero de software",
        "ingeniero de sistemas",
        "ingeniero de datos",
        "ingeniero devops",
        "ingeniero cloud",
        "ingeniero qa",
        "desarrollador de software",
        "desarrollador web",
        "desarrollador frontend",
        "desarrollador backend",
        "desarrollador fullstack",
        "desarrollador full stack",
        "desarrollador móvil",
        "desarrollador movil",
        "desarrollador android",
        "desarrollador ios",
        "desarrollador de sistemas",
        "desarrollador de aplicaciones",
        "desarrollador ti",
        "desarrollador java",
        "desarrollador .net",
        "desarrollador python",
        "desarrollador php",
        "programador web",
        "programador de sistemas",
        "programador de software",
        "programador ti",
        "analista programador",
        "científico de datos",
        "cientifico de datos",
        "qa automation",
        "qa automatizador",
        # Términos puramente tecnológicos (sin ambigüedad comercial o fabril)
        "software",
        "devops",
        "cloud",
        "sre",
        "full stack",
        "full-stack",
        "fullstack",
        "frontend",
        "backend",
    ]

    # Palabras en el TÍTULO que indican un puesto claramente no-IT (Español, Inglés, Alemán).
    # Se evalúan con `in` sobre title.lower() para capturar variaciones.
    TITLE_BLACKLIST: list[str] = [
        # Ventas / Comercial / Business
        "vendedor",
        "ventas",
        "asesor comercial",
        "ejecutivo comercial",
        "comercial",
        "call center",
        "retenciones",
        "portabilidad",
        "sales",
        "vertrieb",
        "account executive",
        "business development",
        "bdr",
        "sdr",
        "key account",
        "inside sales",
        "kundenberater",
        "teleoperador",
        "brand manager",
        "founder s associate",
        "founders associate",
        # Contabilidad / Finanzas / Impuestos
        "accountant",
        "accounting",
        "buchhalter",
        "bilanzbuchhalter",
        "anlagenbuchhalter",
        "finanzbuchhalter",
        "steuerberater",
        "steuerfachangestellte",
        "steuern",
        "contable",
        "contador",
        "contabilidad",
        "auditor",
        "auditoría",
        "auditoria",
        "wirtschaftsprüfer",
        "payroll",
        "nómina",
        "planillas",
        "operaciones crediticias",
        "banking",
        "controlling",
        "controller",
        # Marketing / Social Media / Contenido
        "marketing",
        "performance marketing",
        "online marketing",
        "social media",
        "community manager",
        "content manager",
        "content creator",
        "seo",
        "sem",
        "copywriter",
        "redakteur",
        "online-redakteur",
        "marktanalyse",
        # Recursos Humanos / Reclutamiento
        "recruiter",
        "recruiting",
        "talent acquisition",
        "human resources",
        "recursos humanos",
        "personalreferent",
        "hr manager",
        "hr specialist",
        "hr generalist",
        "people operations",
        # Logística / Operaciones / Distribución
        "logistik",
        "logistics",
        "warehouse",
        "lager",
        "lagerist",
        "vendedor de ruta",
        "vendedor de campo",
        "chofer",
        "conductor",
        "motorizado",
        "mercaderista",
        "ruta",
        "reparto",
        # Legal / Cumplimiento / Salud / Administrativo
        "legal",
        "jurist",
        "anwalt",
        "abogado",
        "paralegal",
        "fincrime",
        "pflege",
        "krankenpfleger",
        "krankentransport",
        "arzt",
        "nurse",
        "content reviewer",
        "data entry",
        "digitador",
        "transcriptor",
        # Industria / CNC / Inmobiliario
        "cnc",
        "matricero",
        "mecanizado",
        "electrónico industrial",
        "mantenimiento eléctrico",
        "riego",
        "inmobiliario",
        "sala ventas",
        "consumo masivo",
        "abarrotes",
        "lácteos",
        "estacionamiento",
        "monitoreo gps",
        # Calidad Industrial / Manufactura / Procesos No-IT
        "control de calidad",
        "gestión de calidad",
        "gestion de calidad",
        "aseguramiento de calidad",
        "aseguramiento en calidad",
        "sistema de gestión",
        "sistemas de gestión",
        "sistema de gestion",
        "sistemas de gestion",
        "sistemas integrados de gestión",
        "sig",
        "hseq",
        "sgc",
        "alimento",
        "alimentos",
        "alimentaria",
        "textil",
        "farmacéutic",
        "farmaceutic",
        "químic",
        "quimic",
        "planta de alimentos",
        "planta móvil",
        "planta movil",
        "operario",
        "operaria",
        "plástico",
        "plasticos",
        "plásticos",
        "salud",
        "clínic",
        "clinic",
        "enfermer",
        "concesionario",
        "automotriz",
        "constructor",
        "obra civil",
        "tratamiento agua",
        "ptap",
        "café",
        "cafe",
        "metalmecánic",
        "metalmecanic",
        "metrólogo",
        "metrologo",
        "cemento",
        "microbiolog",
        "ayudante de calidad",
        "controlador de calidad",
        "perito comprador",
        # Roles no-IT que usan 'desarrollador' o 'programador' en sentido comercial/industrial
        "desarrollador de ventas",
        "desarrollador de negocios",
        "desarrollador de negocio",
        "desarrollador comercial",
        "desarrollador de mercado",
        "desarrollador de ruta",
        "desarrollador inmobiliario",
        "desarrollador de producto",
        "desarrollador de crédito",
        "desarrollador de credito",
        "business developer",
        "programador maestro",
        "programador de producción",
        "programador de produccion",
        "programador de mantenimiento",
        "programador de rutas",
        "programador de ruta",
        "programador de suministros",
        "programador de cirugías",
        "programador de cirugias",
        "programador logístico",
        "programador logistico",
        "programador de lealtad",
        "programador de instalación",
        "programador de instalacion",
        "master scheduler",
        "scheduler",
        "programador cnc",
        "programador plc",
        "canal de detalle",
    ]

    # Fragmentos en el SLUG de la URL que indican no-IT.
    # Las URLs de Computrabajo contienen el título como slug (kebab-case).
    URL_BLACKLIST: list[str] = [
        "vendedor",
        "ventas",
        "comercial",
        "campo",
        "chofer",
        "mercaderista",
        "call-center",
        "ruta",
        "inmobiliario",
        "abarrotes",
        "lacteos",
        "estacionamiento",
        "accountant",
        "buchhalter",
        "steuerberater",
        "marketing",
        "sales",
        "recruiter",
    ]

    # Mínimo de caracteres en la descripción para considerar la oferta válida.
    MIN_DESCRIPTION_LENGTH: int = 150

    def is_relevant(self, title: str, url: str) -> bool:
        """
        Pre-filtro rápido: determina si vale la pena navegar al detalle.

        Evalúa el título visible del listado y el slug de la URL.
        No requiere red ni parseo de HTML de detalle.

        Args:
            title: Título visible del puesto (ej. "Vendedor de Campo").
            url:   URL de la oferta (ej. "https://pe.computrabajo.com/...vendedor-de-campo...").

        Returns:
            False si el título o la URL coinciden con la blacklist.
            True  en caso contrario (puede pasar al detalle).
        """
        title_lower = title.lower().strip()
        url_lower = url.lower().strip()

        if not title_lower:
            return False

        # Si el título tiene un rol tecnológico explícito, se acepta
        if any(kw in title_lower for kw in self.IT_EXEMPTION_KEYWORDS):
            return True

        for word in self.TITLE_BLACKLIST:
            if word in title_lower:
                return False

        for fragment in self.URL_BLACKLIST:
            if fragment in url_lower:
                return False

        return True

    def is_valid_it_job(self, offer) -> bool:
        """
        Post-filtro completo: valida calidad mínima de una oferta ya parseada.

        Requiere que la oferta tenga al menos una habilidad técnica detectada
        y una descripción suficientemente larga para ser útil en ML/NLP.

        Args:
            offer: Instancia de JobOffer ya limpiada por TextCleaner.

        Returns:
            True si la oferta es IT válida y tiene datos suficientes.
        """
        # Capa 1: re-evaluar título y URL (captura casos que pasaron is_relevant
        # con título vacío o que el parser rellenó con datos distintos)
        if not self.is_relevant(offer.job_title, offer.source_url):
            return False

        # Capa 2: debe tener al menos una skill técnica reconocida
        if not offer.hard_skills:
            return False

        # Capa 2b: Si la única skill detectada es "qa", exigir contexto explícito de software/TI
        # para descartar falsos positivos de aseguramiento de calidad fabril o documental.
        if [s.lower() for s in offer.hard_skills] == ["qa"]:
            title_lower = offer.job_title.lower()
            qa_it_indicators = [
                "software",
                "engineer",
                "automation",
                "automatizador",
                "tester",
                "testing",
                "desarrollo",
                "desarrollador",
                "developer",
                "ti",
                "sistemas",
                "it",
                "backend",
                "frontend",
                "web",
                "cloud",
            ]
            if not any(
                re.search(rf"\b{re.escape(ind)}\b", title_lower)
                for ind in qa_it_indicators
            ):
                return False

        # Capa 3: descripción suficiente para NLP
        if len(offer.full_description) < self.MIN_DESCRIPTION_LENGTH:
            return False

        return True
