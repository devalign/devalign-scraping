"""
Gestión del ciclo de vida del browser Playwright.

Patrón Context Manager para garantizar cierre limpio del browser
y rotación de User-Agent para evasión de detección.
"""

from playwright.sync_api import sync_playwright
from fake_useragent import UserAgent


class BrowserManager:
    """
    Gestiona el ciclo de vida del browser.
    Patrón Context Manager para garantizar cierre limpio.

    Uso:
        with BrowserManager(headless=True) as context:
            page = context.new_page()
            page.goto("https://example.com")
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright = None
        self._browser = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        ua = UserAgent()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        self.context = self._browser.new_context(
            user_agent=ua.random,
            viewport={"width": 1280, "height": 800},
            locale="es-PE",
        )
        return self.context

    def __exit__(self, *args):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
