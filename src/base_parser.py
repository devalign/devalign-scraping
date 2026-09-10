"""
Interfaz base (Abstract Base Class) para parsers de portales de empleo.

Define el contrato que deben cumplir todos los parsers del proyecto.
Cada parser implementa su propia estrategia de extracción (Patrón Strategy).

Parsers disponibles:
    - ComputrabajoParser : HTML scraping con Playwright + BeautifulSoup
    - GetOnBoardParser   : API REST pública (sin browser) + requests
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseParser(ABC):
    """
    Interfaz abstracta para parsers de portales de empleo.

    Cada subclase implementa la lógica específica de extracción para un portal.
    El orquestador (`run_scraper.py`) trabaja exclusivamente con esta interfaz.

    Convención de firma:
        - `page` es la instancia de Playwright Page activa. Para parsers basados
          en API (ej. GetOnBoardParser), este argumento se recibe pero se ignora.
    """

    # Identificador único del portal (ej. "computrabajo", "getonboard").
    # Usado en logs, checkpoints y argumentos de CLI.
    SITE_NAME: str = ""

    # URL base predeterminada del portal.
    DEFAULT_BASE_URL: str = ""

    @abstractmethod
    def fetch_job_listings(self, page, current_page: int) -> list[tuple[str, str]]:
        """
        Obtiene la lista de ofertas de una página de resultados.

        Para parsers HTML: navega con `page` y parsea el HTML.
        Para parsers API:  realiza una llamada HTTP REST e ignora `page`.

        Args:
            page:         Instancia de Playwright Page (puede ser None para API parsers).
            current_page: Número de página (1-indexed).

        Returns:
            Lista de tuplas (url_completa, titulo_visible).
            Lista vacía si no hay más resultados.
        """

    @abstractmethod
    def fetch_and_parse_job(self, page, url: str) -> object:
        """
        Navega o fetcha una oferta individual y retorna un JobOffer poblado.

        Para parsers HTML: navega con `page` al `url` y parsea el HTML.
        Para parsers API:  realiza una llamada HTTP al `url` y parsea el HTML
                           solo para datos no disponibles en la API (ej. tags).

        Args:
            page: Instancia de Playwright Page (puede ser None para API parsers).
            url:  URL pública de la oferta.

        Returns:
            Instancia de JobOffer con todos los campos disponibles poblados.
        """

    @staticmethod
    def extract_from_json_ld(html: str) -> dict:
        """
        Extrae y parsea el primer bloque application/ld+json que sea de tipo JobPosting.
        Retorna un diccionario con los datos estructurados o un diccionario vacío si falla.
        """
        import json
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        json_ld_scripts = soup.select('script[type="application/ld+json"]')

        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "JobPosting":
                    return data
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
        return {}
