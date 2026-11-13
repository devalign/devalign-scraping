"""
Parser para Arbeitnow API.

Extrae ofertas laborales desde la API REST de Arbeitnow
(https://www.arbeitnow.com/api/job-board-api).
"""

from __future__ import annotations

import datetime
from bs4 import BeautifulSoup

from src.base_parser import HttpParser
from src.models import JobOffer
from src.taxonomy import SkillTaxonomyService

API_BASE = "https://www.arbeitnow.com/api/job-board-api"
HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "DevAlign Scraper (https://github.com/devalign/devalign-scraping)",
}


class ArbeitnowParser(HttpParser):
    SITE_NAME = "arbeitnow"
    DEFAULT_BASE_URL = "https://www.arbeitnow.com"

    def __init__(self):
        super().__init__(headers=HTTP_HEADERS, timeout=15)
        self._job_data_cache: dict[str, dict] = {}
        self._taxonomy = SkillTaxonomyService.get_instance()

    def fetch_job_listings(
        self, current_page: int = 1, page=None, **kwargs
    ) -> list[tuple[str, str]]:
        if not isinstance(current_page, int) and isinstance(page, int):
            current_page, page = page, current_page
        url = f"{API_BASE}?page={current_page}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return []
            data = resp.json()
        except Exception as e:
            print(f"   [ARBEITNOW-ERROR] Error al cargar listado: {e}")
            return []

        jobs = data.get("data", [])
        entries = []
        for job in jobs:
            job_url = job.get("url", "")
            title = job.get("title", "Desconocido")
            if job_url:
                self._job_data_cache[job_url] = job
                entries.append((job_url, title))

        return entries

    def fetch_and_parse_job(self, url: str = "", page=None, **kwargs) -> JobOffer:
        if not isinstance(url, str) and isinstance(page, str):
            url, page = page, url
        if not url and "url" in kwargs:
            url = kwargs["url"]
        job_data = self._job_data_cache.get(url, {})

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
            offer.date_posted = datetime.datetime.fromtimestamp(
                int(created_at), tz=datetime.timezone.utc
            ).strftime("%Y-%m-%d")
        elif created_at:
            offer.date_posted = created_at[:10]

        offer.full_description = description_text

        # 1. Tags explícitos provistos por la API
        extracted_skills = set()
        tags = job_data.get("tags", [])
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, str):
                    extracted_skills.add(t.lower().strip())

        # 2. Extracción de habilidades mediante taxonomía
        hard_skills, soft_skills = self._taxonomy.extract_skills(description_text)
        offer.hard_skills = sorted(list(set(hard_skills) | extracted_skills))
        offer.soft_skills = soft_skills

        return offer
