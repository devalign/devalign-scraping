"""
Parser para WeWorkRemotely RSS feed.

Extrae ofertas laborales desde el feed RSS oficial de WWR
(https://weworkremotely.com/remote-jobs.rss).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

from src.base_parser import HttpParser
from src.models import JobOffer
from src.taxonomy import SkillTaxonomyService

RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
HTTP_HEADERS = {
    "User-Agent": "DevAlign Scraper (https://github.com/devalign/devalign-scraping)",
}


class WeworkremotelyParser(HttpParser):
    SITE_NAME = "weworkremotely"
    DEFAULT_BASE_URL = "https://weworkremotely.com"

    def __init__(self):
        super().__init__(headers=HTTP_HEADERS, timeout=15)
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

        try:
            resp = self.session.get(RSS_URL, timeout=self.timeout)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
        except Exception as e:
            print(f"   [WWR-ERROR] Error al cargar RSS: {e}")
            return []

        entries = []
        for item in items:
            title_node = item.find("title")
            link_node = item.find("link")
            desc_node = item.find("description")
            pubdate_node = item.find("pubDate")
            category_node = item.find("category")

            title = title_node.text if title_node is not None else "Desconocido"
            link = link_node.text if link_node is not None else ""
            desc = desc_node.text if desc_node is not None else ""
            pubdate = pubdate_node.text if pubdate_node is not None else ""
            category = category_node.text if category_node is not None else ""

            if link:
                self._job_data_cache[link] = {
                    "title": title,
                    "description": desc,
                    "pubDate": pubdate,
                    "category": category,
                }
                entries.append((link, title))

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

        raw_title = job_data.get("title", "")
        if ":" in raw_title:
            company, job_title = raw_title.split(":", 1)
            offer.company = company.strip()
            offer.job_title = job_title.strip()
        else:
            offer.company = ""
            offer.job_title = raw_title

        offer.location = "Remote"
        offer.modality = "Remoto"

        pub_date = job_data.get("pubDate", "")
        if pub_date:
            try:
                dt = parsedate_to_datetime(pub_date)
                offer.date_posted = dt.strftime("%Y-%m-%d")
            except Exception:
                offer.date_posted = pub_date[:10]

        offer.full_description = description_text

        category = job_data.get("category", "")
        extracted_skills = set()
        if category:
            extracted_skills.add(category.lower().strip())

        hard_skills, soft_skills = self._taxonomy.extract_skills(description_text)
        offer.hard_skills = sorted(list(set(hard_skills) | extracted_skills))
        offer.soft_skills = soft_skills

        return offer
