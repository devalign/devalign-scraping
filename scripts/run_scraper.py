"""
Entry point principal del scraper de ofertas laborales.

Uso:
    python scripts/run_scraper.py
    python scripts/run_scraper.py --jobs 50 --output data/processed/custom.csv
    python scripts/run_scraper.py --jobs 10 --no-headless
"""

import argparse
import os
import random
import sys
import time

from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.browser import BrowserManager  # noqa: E402
from src.parser import JobParser  # noqa: E402
from src.cleaner import TextCleaner  # noqa: E402
from src.supabase_exporter import SupabaseExporter  # noqa: E402

# Cargar .env si existe
load_dotenv()

# Configuración por defecto desde .env o valores hardcoded
DEFAULT_URL = os.getenv(
    "TARGET_URL", "https://pe.computrabajo.com/trabajo-de-desarrollador"
)
DEFAULT_JOBS = int(os.getenv("TARGET_JOBS", "100"))
DEFAULT_HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
)
def fetch_page(page, url: str) -> str:
    """
    Navega a una URL con reintentos automáticos ante fallos.

    Args:
        page: Playwright page instance.
        url: URL a navegar.

    Returns:
        HTML renderizado de la página.
    """
    page.goto(url, wait_until="networkidle", timeout=30000)
    # Pequeño delay extra para asegurar renderizado de JS dinámico
    time.sleep(1)
    return page.content()


def parse_args():
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="[*] DevAlign Scraper — Extrae ofertas laborales de Computrabajo"
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help=f"Número de ofertas a recolectar (default: {DEFAULT_JOBS})",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_URL,
        help=f"URL base del portal (default: {DEFAULT_URL})",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Ejecutar browser en modo visible (para debug)",
    )
    return parser.parse_args()


def run(target_jobs: int, base_url: str, headless: bool):
    """
    Ejecuta el pipeline completo de scraping.

    Args:
        target_jobs: Número de ofertas a recolectar.
        base_url: URL base del portal de empleo.
        headless: Si True, el browser no muestra ventana.
    """
    parser = JobParser()
    cleaner = TextCleaner()
    exporter = SupabaseExporter()
    collected = []
    errors = 0

    print("[*] DevAlign Scraper")
    print(f"   Target: {base_url}")
    print(f"   Jobs: {target_jobs}")
    print(f"   Headless: {headless}")
    print(f"{'-' * 50}")

    with BrowserManager(headless=headless) as context:
        page = context.new_page()
        current_page = 1

        while len(collected) < target_jobs:
            url = f"{base_url}?p={current_page}"
            print(f"\n[Page {current_page}]: {url}")

            try:
                html = fetch_page(page, url)
            except Exception as e:
                print(f"   [ERROR] Error al cargar listado: {e}")
                errors += 1
                if errors > 5:
                    print("   [ABORT] Demasiados errores. Abortando.")
                    break
                current_page += 1
                continue

            job_urls = parser.parse_listing_page(html)

            if not job_urls:
                print(f"   [WARN] Sin más resultados en página {current_page}.")
                break

            print(f"   [#] {len(job_urls)} vacantes encontradas")

            for job_url in job_urls:
                if len(collected) >= target_jobs:
                    break

                try:
                    detail_html = fetch_page(page, job_url)
                    # Debug: Guardar el primer HTML recibido para inspección
                    if len(collected) == 0:
                        with open("debug_detail.html", "w", encoding="utf-8") as f:
                            f.write(detail_html)
                        print("   [DEBUG] Primer HTML guardado en debug_detail.html")

                    offer = parser.parse_job_detail(detail_html, job_url)

                    if not offer.job_title or not offer.full_description:
                        # Reintento con wait explícito si faltan datos críticos
                        try:
                            # Esperar al título o al contenedor de descripción
                            page.wait_for_selector(
                                parser.SELECTORS["job_title"], timeout=3000
                            )
                            page.wait_for_selector(
                                parser.SELECTORS["description"], timeout=3000
                            )
                            detail_html = page.content()
                            offer = parser.parse_job_detail(detail_html, job_url)
                        except Exception:
                            pass

                    if not offer.job_title or not offer.full_description:
                        print(
                            f"   [WARN] Datos incompletos en {job_url} "
                            f"(Título: {bool(offer.job_title)}, "
                            f"Desc: {len(offer.full_description)} chars)"
                        )

                    offer = cleaner.clean(offer)
                    collected.append(offer)
                    print(
                        f"   [{len(collected)}/{target_jobs}] "
                        f"[OK] {offer.job_title[:60]}"
                    )
                except Exception as e:
                    print(f"   [ERROR] Error en {job_url}: {e}")
                    errors += 1

                # Delay aleatorio — simula comportamiento humano, reduce bans
                time.sleep(random.uniform(2.5, 5.0))

            current_page += 1

    print(f"\n{'-' * 50}")
    print("Summary:")
    print(f"   Recolectadas: {len(collected)}")
    print(f"   Errores: {errors}")

    if collected:
        exporter.save(collected)
    else:
        print("\n[!] No se recolectaron ofertas.")


if __name__ == "__main__":
    args = parse_args()
    headless = DEFAULT_HEADLESS and not args.no_headless
    run(
        target_jobs=args.jobs,
        base_url=args.url,
        headless=headless,
    )
