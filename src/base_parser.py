"""
Interfaz base (Abstract Base Class) y clases especializadas para parsers de empleo.

Define los contratos para:
- BaseParser: Interfaz raíz para todos los parsers.
- BrowserParser: Para portales con renderizado JS vía Playwright (ej. Computrabajo).
- HttpParser: Para portales API REST o RSS con sesión HTTP persistente (ej. GetOnBoard).
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from src.models import JobOffer


class BaseParser(ABC):
    """
    Interfaz abstracta raíz para parsers de portales de empleo.
    """

    SITE_NAME: str = ""
    DEFAULT_BASE_URL: str = ""
    requires_browser: bool = False

    @abstractmethod
    def fetch_job_listings(self, current_page: int, page=None) -> list[tuple[str, str]]:
        """
        Obtiene la lista de ofertas de una página de resultados.

        Args:
            current_page: Número de página (1-indexed).
            page:         Instancia de Playwright Page (opcional, solo para BrowserParser).

        Returns:
            Lista de tuplas (url_completa, titulo_visible).
        """

    @abstractmethod
    def fetch_and_parse_job(self, url: str, page=None) -> JobOffer:
        """
        Fetcha y parsea una oferta individual y retorna un JobOffer poblado.

        Args:
            url:  URL pública de la oferta.
            page: Instancia de Playwright Page (opcional, solo para BrowserParser).

        Returns:
            Instancia de JobOffer con todos los campos disponibles poblados.
        """

    @staticmethod
    def extract_from_json_ld(html: str) -> dict:
        """
        Extrae y parsea el primer bloque application/ld+json que sea de tipo JobPosting.
        Retorna un diccionario con los datos estructurados o vacío si falla.
        """
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


class BrowserParser(BaseParser):
    """
    Clase base para parsers que dependen de un navegador real (Playwright).
    """

    requires_browser: bool = True

    def __init__(self):
        self.page = None

    def set_page(self, page) -> None:
        """Asigna la página de Playwright activa."""
        self.page = page


class HttpParser(BaseParser):
    """
    Clase base para parsers que operan sobre APIs REST o feeds RSS vía HTTP puro.
    Implementa sesión persistente (connection pooling) y reintentos exponenciales.
    """

    requires_browser: bool = False

    def __init__(
        self,
        headers: Optional[dict[str, str]] = None,
        timeout: int = 15,
        max_retries: int = 3,
    ):
        self.timeout = timeout
        self.session = requests.Session()

        if headers:
            self.session.headers.update(headers)

        # Configurar reintentos automáticos para códigos transitorios
        retries = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def close(self) -> None:
        """Cierra la sesión HTTP persistente."""
        try:
            self.session.close()
        except Exception:
            pass
