"""
Parser para WeWorkRemotely RSS feed.

Extrae ofertas laborales desde el feed RSS oficial de WWR
(https://weworkremotely.com/remote-jobs.rss).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from src.base_parser import BaseParser
from src.getonboard_parser import GetOnBoardParser
from src.parser import JobOffer

# Constantes
RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

HTTP_HEADERS = {
    "User-Agent": "DevAlign Scraper (https://github.com/devalign/devalign-scraping)",
}

class WeworkremotelyParser(BaseParser):
    SITE_NAME = "weworkremotely"
    DEFAULT_BASE_URL = "https://weworkremotely.com"

    def __init__(self):
        self._job_data_cache: dict[str, dict] = {}
        self._fetched = False

    def fetch_job_listings(self, page, current_page: int) -> list[tuple[str, str]]:
        if self._fetched and current_page > 1:
            return []

        resp = requests.get(RSS_URL, headers=HTTP_HEADERS, timeout=15)
        resp.raise_for_status()
        
        try:
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
        except ET.ParseError:
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

    def fetch_and_parse_job(self, page, url: str) -> JobOffer:
        job_data = self._job_data_cache.get(url, {})
        
        raw_html = job_data.get("description", "")
        if raw_html:
            soup = BeautifulSoup(raw_html, "lxml")
            description_text = soup.get_text(separator="\n").strip()
        else:
            description_text = ""
            
        offer = JobOffer(source_url=url, portal=self.SITE_NAME)
        
        # El título en WWR suele venir como "Empresa: Título del puesto"
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
            extracted_skills.add(category.lower())
            
        desc_lower = description_text.lower()
        for kw in GetOnBoardParser.HARD_SKILLS_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', desc_lower):
                extracted_skills.add(kw)
                
        # En WWR (siendo el feed de programación) podemos incluir la categoría 
        # junto con las skills validadas.
        valid_skills = [s for s in extracted_skills if s in GetOnBoardParser.HARD_SKILLS_KEYWORDS or s == category.lower()]
        
        offer.hard_skills = valid_skills
            
        return offer
