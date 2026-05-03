"""
Entry point principal del scraper de ofertas laborales.

Uso:
    python scripts/run_scraper.py                               # Computrabajo (default)
    python scripts/run_scraper.py --site getonboard --jobs 100  # GetOnBoard
    python scripts/run_scraper.py --site getonboard --categories programming mobile-developer
    python scripts/run_scraper.py --jobs 300                    # Limitar a 300 ofertas IT
    python scripts/run_scraper.py --no-headless                 # Browser visible (debug)
    python scripts/run_scraper.py --no-supabase                 # Solo guardar local

Comportamiento resiliente:
    - Si se interrumpe con Ctrl+C, guarda todo lo recolectado hasta ese momento.
    - Al iniciar, detecta automáticamente si hay una sesión previa con progreso
      y ofrece continuar desde donde se dejó (sin re-scrapear URLs procesadas).
    - Guarda checkpoints incrementales cada 20 ofertas IT válidas.
"""

import argparse
import os
import random
import signal
import sys
import time

from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.browser import BrowserManager        # noqa: E402
from src.cleaner import TextCleaner          # noqa: E402
from src.getonboard_parser import GetOnBoardParser   # noqa: E402
from src.job_filter import JobFilter         # noqa: E402
from src.parser import ComputrabajoParser    # noqa: E402
from src.session import SessionManager       # noqa: E402
from src.supabase_exporter import SupabaseExporter  # noqa: E402

# Cargar .env si existe
load_dotenv()

# URL y configuración por defecto según el portal
SITE_DEFAULTS: dict[str, str] = {
    "computrabajo": "https://pe.computrabajo.com/trabajo-de-desarrollador",
    "getonboard": "https://www.getonbrd.com",
}
DEFAULT_SITE = os.getenv("TARGET_SITE", "computrabajo")
DEFAULT_URL = os.getenv(
    "TARGET_URL", SITE_DEFAULTS.get(DEFAULT_SITE, SITE_DEFAULTS["computrabajo"])
)
DEFAULT_JOBS = int(os.getenv("TARGET_JOBS", "100"))
DEFAULT_HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
FLUSH_EVERY = 20  # Checkpoint automático cada N ofertas IT válidas


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
    time.sleep(1)
    return page.content()


def parse_args():
    """Parsea argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="[*] DevAlign Scraper — Extrae ofertas laborales IT"
    )
    parser.add_argument(
        "--site",
        type=str,
        default=DEFAULT_SITE,
        choices=["computrabajo", "getonboard"],
        help=f"Portal de empleo a scrapear (default: {DEFAULT_SITE})",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_JOBS,
        help=f"Número de ofertas IT válidas a recolectar (default: {DEFAULT_JOBS})",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="URL base del portal (override manual; por defecto se usa el del --site)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        metavar="CATEGORY",
        help=(
            "[Solo GetOnBoard] Categorías a scrapear. "
            "Ej: --categories programming mobile-developer sysadmin-devops-qa"
        ),
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Ejecutar browser en modo visible (para debug; solo aplica a Computrabajo)",
    )
    parser.add_argument(
        "--no-supabase",
        action="store_true",
        help="No subir datos a Supabase (solo guardar localmente)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/test_run.json",
        help="Ruta para guardar el archivo local de resultados (default: data/test_run.json)",
    )
    return parser.parse_args()


def _build_parser(site: str, categories: list[str] | None):
    """
    Factory: instancia el parser correcto según el portal seleccionado.

    Args:
        site:       Identificador del portal ("computrabajo" | "getonboard").
        categories: Lista de categorías (solo relevante para GetOnBoard).

    Returns:
        Instancia de BaseParser lista para usar.
    """
    if site == "getonboard":
        return GetOnBoardParser(categories=categories)
    return ComputrabajoParser()


def _prompt_resume() -> bool:
    """
    Detecta si hay una sesión previa y pregunta al usuario si desea reanudarla.

    Returns:
        True si se debe cargar el checkpoint, False para empezar desde cero.
    """
    checkpoint = SessionManager.find_recent_checkpoint()
    if not checkpoint:
        return False

    # Leer metadata del checkpoint sin cargarlo completo
    try:
        import json
        with open(checkpoint, encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("metadata", {})
        collected = meta.get("total_collected", 0)
        target = meta.get("target_jobs", "?")
        saved_at = meta.get("saved_at", "?")[:19].replace("T", " ")
    except Exception:
        return False

    print(f"\n[!] Sesión previa encontrada: {checkpoint.name}")
    print(f"    Progreso: {collected}/{target} ofertas IT")
    print(f"    Guardada: {saved_at} UTC")

    answer = input("\n¿Deseas continuar desde donde se dejó? (S/n): ").strip().lower()
    return answer in ("", "s", "si", "sí", "yes", "y")


def run(
    target_jobs: int,
    base_url: str,
    headless: bool,
    no_supabase: bool,
    output_file: str,
    site: str = "computrabajo",
    categories: list[str] | None = None,
):
    """
    Ejecuta el pipeline completo de scraping con resiliencia.

    Args:
        target_jobs: Número de ofertas IT válidas a recolectar.
        base_url:    URL base del portal (solo relevante para Computrabajo).
        headless:    Si True, el browser no muestra ventana (solo Computrabajo).
        no_supabase: Si True, omite la exportación a Supabase.
        output_file: Ruta del archivo JSON local de salida.
        site:        Portal a scrapear ("computrabajo" | "getonboard").
        categories:  Categorías GetOnBoard (None usa el default del parser).
    """
    parser = _build_parser(site, categories)
    cleaner = TextCleaner()
    job_filter = JobFilter()
    exporter = None if no_supabase else SupabaseExporter()

    # ── Inicializar sesión ─────────────────────────────────────────────
    session = SessionManager(
        output_file=output_file,
        target_jobs=target_jobs,
        base_url=base_url,
        flush_every=FLUSH_EVERY,
    )

    # ── Detección automática de sesión previa ──────────────────────────
    if _prompt_resume():
        checkpoint = SessionManager.find_recent_checkpoint()
        session.load_checkpoint(checkpoint)

    # ── Signal handler para Ctrl+C / SIGTERM ──────────────────────────
    signal.signal(signal.SIGINT, lambda *_: session.request_shutdown())
    signal.signal(signal.SIGTERM, lambda *_: session.request_shutdown())

    print("\n[*] DevAlign Scraper")
    print(f"   Portal:      {site.capitalize()}")
    print(f"   Target URL:  {base_url}")
    print(f"   Meta IT:     {target_jobs} ofertas válidas")
    print(f"   Ya cargadas: {session.count}")
    print(f"   Headless:    {headless}")
    print(f"   Supabase:    {not no_supabase}")
    print(f"   Checkpoint:  cada {FLUSH_EVERY} ofertas")
    print(f"{'-' * 50}")

    # ── GetOnBoard usa API REST; no abrimos Playwright ─────────────────
    needs_browser = (site == "computrabajo")

    # ── Loop principal ─────────────────────────────────────────────────
    try:
        with BrowserManager(headless=headless) as context:
            page = context.new_page() if needs_browser else None

            while not session.should_stop and session.count < target_jobs:
                print(f"\n[Page {session.current_page}]")

                # ── Obtener listado ────────────────────────────────────
                try:
                    job_entries = parser.fetch_job_listings(
                        page, session.current_page
                    )
                except Exception as e:
                    print(f"   [ERROR] Error al cargar listado: {e}")
                    session.register_error()
                    if session.errors > 5:
                        print("   [ABORT] Demasiados errores consecutivos.")
                        break
                    session.current_page += 1
                    continue

                if not job_entries:
                    print(
                        f"   [WARN] Sin más resultados en página {session.current_page}."
                    )
                    break

                print(f"   [#] {len(job_entries)} vacantes encontradas")

                for job_url, job_title in job_entries:
                    if session.should_stop or session.count >= target_jobs:
                        break

                    # ── Pre-filtro por título/URL ──────────────────────
                    if not job_filter.is_relevant(job_title, job_url):
                        print(f"   [SKIP] {job_title[:65]}")
                        session.register_skip()
                        session.mark_processed(job_url)
                        continue

                    # ── Skip si ya fue procesada ───────────────────────
                    if session.is_already_processed(job_url):
                        print(f"   [DONE] Ya procesada: {job_title[:55]}")
                        continue

                    # ── Parsear detalle ────────────────────────────────
                    try:
                        offer = parser.fetch_and_parse_job(page, job_url)

                        # Reintento con espera extra (solo Computrabajo/HTML)
                        if needs_browser and (
                            not offer.job_title or not offer.full_description
                        ):
                            try:
                                page.wait_for_selector("h1", timeout=3000)
                                detail_html = page.content()
                                offer = parser.parse_job_detail(  # type: ignore[attr-defined]
                                    detail_html, job_url
                                )
                            except Exception:
                                pass

                        offer = cleaner.clean(offer)

                        # ── Post-filtro ────────────────────────────────
                        if not job_filter.is_valid_it_job(offer):
                            print(
                                f"   [FILTERED] {offer.job_title[:55]} "
                                f"(skills: {len(offer.hard_skills)}, "
                                f"desc: {len(offer.full_description)}c)"
                            )
                            session.register_filtered()
                            session.mark_processed(job_url)
                            continue

                        session.add_offer(offer)
                        print(
                            f"   [{session.count}/{target_jobs}] "
                            f"[OK] {offer.job_title[:60]}"
                        )

                    except Exception as e:
                        print(f"   [ERROR] Error en {job_url}: {e}")
                        session.register_error()

                    # Delay: Computrabajo requiere más espera que GOB API
                    if needs_browser:
                        time.sleep(random.uniform(2.5, 5.0))
                    else:
                        time.sleep(random.uniform(0.5, 1.5))

                session.current_page += 1

    finally:
        session.save_final(exporter=exporter)



if __name__ == "__main__":
    args = parse_args()
    headless = DEFAULT_HEADLESS and not args.no_headless
    base_url = args.url or SITE_DEFAULTS.get(args.site, SITE_DEFAULTS["computrabajo"])
    run(
        target_jobs=args.jobs,
        base_url=base_url,
        headless=headless,
        no_supabase=args.no_supabase,
        output_file=args.output,
        site=args.site,
        categories=args.categories,
    )
