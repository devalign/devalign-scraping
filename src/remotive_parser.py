"""
Parser para Remotive API.

Extrae ofertas laborales desde la API REST de Remotive
(https://remotive.com/api/remote-jobs).
"""

from __future__ import annotations

from bs4 import BeautifulSoup
import requests
from datetime import datetime, timezone
from typing import Optional

from src.base_parser import BaseParser
from src.parser import JobOffer

# Constantes
API_BASE = "https://remotive.com/api/remote-jobs"
DEFAULT_CATEGORY = "software-dev"

HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "DevAlign Scraper (https://github.com/devalign/devalign-scraping)",
}

class RemotiveParser(BaseParser):
    SITE_NAME = "remotive"
    DEFAULT_BASE_URL = "https://remotive.com"

    def __init__(self, category: Optional[str] = None):
        self._category = category or DEFAULT_CATEGORY
        self._job_data_cache: dict[str, dict] = {}
        # La API de Remotive (v1) no está paginada, retorna todo en una lista `jobs`.
        # Llevaremos control de si ya pedimos los datos para retornar vacío en páginas > 1.
        self._fetched = False

    def fetch_job_listings(self, page, current_page: int) -> list[tuple[str, str]]:
        if self._fetched and current_page > 1:
            return []

        url = f"{API_BASE}?category={self._category}"
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        resp.raise_for_status()
        
        data = resp.json()
        jobs = data.get("jobs", [])
        
        entries = []
        for job in jobs:
            job_url = job.get("url", "")
            title = job.get("title", "Desconocido")
            if job_url:
                self._job_data_cache[job_url] = job
                entries.append((job_url, title))
                
        self._fetched = True
        return entries

    def fetch_and_parse_job(self, page, url: str) -> JobOffer:
        # Recuperar datos cacheados
        job_data = self._job_data_cache.get(url, {})
        
        # Limpiar tags HTML en description
        raw_html = job_data.get("description", "")
        if raw_html:
            soup = BeautifulSoup(raw_html, "lxml")
            description_text = soup.get_text(separator="\n").strip()
        else:
            description_text = ""
            
        offer = JobOffer(source_url=url, portal=self.SITE_NAME)
        offer.job_title = job_data.get("title", "")
        offer.company = job_data.get("company_name", "")
        
        location = job_data.get("candidate_required_location", "")
        offer.location = location if location else "Remote"
        offer.modality = "Remoto" # Remotive = 100% Remote
        
        salary = job_data.get("salary", "")
        if salary:
            offer.salary = str(salary)
            
        pub_date = job_data.get("publication_date", "")
        if pub_date:
            offer.date_posted = pub_date[:10] # Solo YYYY-MM-DD
            
        offer.full_description = description_text
        
        # Guardar tags como soft o hard skills (Remotive da tags mezclados)
        tags = job_data.get("tags", [])
        if isinstance(tags, list):
            offer.hard_skills = [t for t in tags if isinstance(t, str)]
            
        return offer
