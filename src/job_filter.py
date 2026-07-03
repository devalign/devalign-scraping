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

    # Palabras en el TÍTULO que indican un puesto claramente no-IT.
    # Se evalúan con `in` sobre title.lower() para capturar variaciones.
    TITLE_BLACKLIST: list[str] = [
        # Ventas / Comercial
        "vendedor",
        "ventas",
        "asesor comercial",
        "ejecutivo comercial",
        "comercial",
        "call center",
        "retenciones",
        "portabilidad",
        # Logística / Distribución
        "vendedor de ruta",
        "vendedor de campo",
        "chofer",
        "conductor",
        "motorizado",
        "mercaderista",
        "ruta",
        "reparto",
        # Industria / CNC
        "cnc",
        "matricero",
        "mecanizado",
        "electrónico industrial",
        "mantenimiento eléctrico",
        "riego",
        # Inmobiliario / Finanzas no-TI
        "inmobiliario",
        "planillas",
        "sala ventas",
        "operaciones crediticias",
        # Otros no-IT
        "consumo masivo",
        "abarrotes",
        "lácteos",
        "estacionamiento",
        "monitoreo gps",
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
        title_lower = title.lower()
        url_lower = url.lower()

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

        # Capa 3: descripción suficiente para NLP
        if len(offer.full_description) < self.MIN_DESCRIPTION_LENGTH:
            return False

        return True
