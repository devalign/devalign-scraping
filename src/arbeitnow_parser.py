"""
Parser para Arbeitnow API.

Extrae ofertas laborales desde la API REST de Arbeitnow
(https://www.arbeitnow.com/api/job-board-api).
"""

from __future__ import annotations

from bs4 import BeautifulSoup
import requests
from typing import Optional
import re

from src.base_parser import BaseParser
from src.getonboard_parser import GetOnBoardParser
from src.parser import JobOffer

# Constantes
API_BASE = "https://www.arbeitnow.com/api/job-board-api"

HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "DevAlign Scraper (https://github.com/devalign/devalign-scraping)",
}

class ArbeitnowParser(BaseParser):
    SITE_NAME = "arbeitnow"
    DEFAULT_BASE_URL = "https://www.arbeitnow.com"

    def __init__(self):
        self._job_data_cache: dict[str, dict] = {}

    def fetch_job_listings(self, page, current_page: int) -> list[tuple[str, str]]:
        url = f"{API_BASE}?page={current_page}"
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=15)
        
        if resp.status_code != 200:
            return []
            
        data = resp.json()
        jobs = data.get("data", [])
        
        entries = []
        for job in jobs:
            job_url = job.get("url", "")
            title = job.get("title", "Desconocido")
            if job_url:
                self._job_data_cache[job_url] = job
                entries.append((job_url, title))
                
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
        
        offer.location = job_data.get("location", "")
        
        is_remote = job_data.get("remote", False)
        offer.modality = "Remoto" if is_remote else "Presencial"
            
        created_at = str(job_data.get("created_at", ""))
        if created_at.isdigit():
            # Unix timestamp a veces
            import datetime
            offer.date_posted = datetime.datetime.utcfromtimestamp(int(created_at)).strftime('%Y-%m-%d')
        elif created_at:
            offer.date_posted = created_at[:10]
            
        offer.full_description = description_text
        
        # Extraer skills de tags y descripción
        extracted_skills = set()
        
        # 1. De los tags
        tags = job_data.get("tags", [])
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, str):
                    extracted_skills.add(t.lower())
                    
        # 2. De la descripción
        desc_lower = description_text.lower()
        for kw in GetOnBoardParser.HARD_SKILLS_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', desc_lower):
                extracted_skills.add(kw)
                
        # Intersecar con nuestras keywords para asegurar que son de TI, o dejar los tags si están en el whitelist
        # Para Arbeitnow (que trae muchos de no-TI), solo confiamos en los extraídos que coinciden con nuestro whitelist
        valid_skills = [s for s in extracted_skills if s in GetOnBoardParser.HARD_SKILLS_KEYWORDS]
        
        offer.hard_skills = valid_skills
            
        return offer
