"""
Parser para Remotive API.

Extrae ofertas laborales desde la API REST de Remotive
(https://remotive.com/api/remote-jobs).
"""

from __future__ import annotations

from typing import Optional
from bs4 import BeautifulSoup

from src.base_parser import HttpParser
from src.models import JobOffer
from src.taxonomy import SkillTaxonomyService

API_BASE = "https://remotive.com/api/remote-jobs"
DEFAULT_CATEGORY = "software-dev"
HTTP_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "DevAlign Scraper (https://github.com/devalign/devalign-scraping)",
}


class RemotiveParser(HttpParser):
    SITE_NAME = "remotive"
    DEFAULT_BASE_URL = "https://remotive.com"

    def __init__(self, category: Optional[str] = None):
        super().__init__(headers=HTTP_HEADERS, timeout=15)
        self._category = category or DEFAULT_CATEGORY
        self._job_data_cache: dict[str, dict] = {}
        self._fetched = False
        self._taxonomy = SkillTaxonomyService.get_instance()

    def fetch_job_listings(
        self, current_page: int = 1, page=None, **kwargs
    ) -> list[tuple[str, str]]:
        if not isinstance(current_page, int) and isinstance(page, int):
            current_page, page = page, current_page
        if self._fetched and current_page > 1:
            return []

        url = f"{API_BASE}?category={self._category}"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"   [REMOTIVE-ERROR] Error al cargar listado: {e}")
            return []

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

        location = job_data.get("candidate_required_location", "")
        offer.location = location if location else "Remote"
        offer.modality = "Remoto"

        salary = job_data.get("salary", "")
        if salary:
            offer.salary = str(salary)

        pub_date = job_data.get("publication_date", "")
        if pub_date:
            offer.date_posted = pub_date[:10]

        offer.full_description = description_text

        extracted_skills = set()
        tags = job_data.get("tags", [])
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, str):
                    extracted_skills.add(t.lower().strip())

        hard_skills, soft_skills = self._taxonomy.extract_skills(description_text)
        offer.hard_skills = sorted(list(set(hard_skills) | extracted_skills))
        offer.soft_skills = soft_skills

        return offer
