"""
Orquestador Multi-País para Scraping de Demanda Laboral Tech en LATAM.

Coordina la recolección integral de ofertas tech en:
1. GetOnBoard:
   - programming
   - mobile-developer
   - sysadmin-devops-qa
   - data-science-analytics
   - machine-learning-ai
   - cybersecurity
   - design-ux

2. Computrabajo Multi-País:
   - Perú (pe)
   - Colombia (co)
   - México (mx)
   - Chile (cl)
   - Argentina (ar)
   Términos clave: 'desarrollador', 'software', 'devops', 'qa', 'datos'

Uso:
    python scripts/scrape_latam_suite.py                        # Suite completa
    python scripts/scrape_latam_suite.py --gob-only             # Solo GetOnBoard
    python scripts/scrape_latam_suite.py --ct-only              # Solo Computrabajo
    python scripts/scrape_latam_suite.py --countries co mx      # Países específicos
    python scripts/scrape_latam_suite.py --jobs-per-batch 150   # Límite por país/categoría
    python scripts/scrape_latam_suite.py --no-headless          # Browser visible
    python scripts/scrape_latam_suite.py --no-supabase          # Solo local
"""

import argparse
import os
import sys
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Agregar raíz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.run_scraper import run, SITE_DEFAULTS  # noqa: E402
from src.getonboard_parser import DEFAULT_CATEGORIES as GOB_CATEGORIES  # noqa: E402
from src.parser import ComputrabajoParser  # noqa: E402

COMPUTRABAJO_COUNTRIES = ["pe", "co", "mx", "cl", "ar"]
COMPUTRABAJO_KEYWORDS = ["desarrollador", "software", "devops", "qa", "datos"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="[*] DevAlign — Orquestador de Scraping Multi-País LATAM"
    )
    parser.add_argument(
        "--gob-only",
        action="store_true",
        help="Ejecutar únicamente GetOnBoard",
    )
    parser.add_argument(
        "--ct-only",
        action="store_true",
        help="Ejecutar únicamente Computrabajo",
    )
    parser.add_argument(
        "--countries",
        nargs="+",
        default=COMPUTRABAJO_COUNTRIES,
        choices=COMPUTRABAJO_COUNTRIES,
        help="Países de Computrabajo a scrapear (default: pe co mx cl ar)",
    )
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=COMPUTRABAJO_KEYWORDS,
        help="Keywords para Computrabajo (default: desarrollador software devops qa datos)",
    )
    parser.add_argument(
        "--jobs-per-batch",
        type=int,
        default=250,
        help="Límite máximo de ofertas por bloque/país (default: 250)",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="Mostrar browser (solo Computrabajo debug)",
    )
    parser.add_argument(
        "--no-supabase",
        action="store_true",
        help="Guardar solo localmente sin exportar a Supabase",
    )
    parser.add_argument(
        "--max-duplicates",
        type=int,
        default=12,
        help="Límite de duplicados consecutivos antes de parada temprana por término",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    headless = not args.no_headless
    start_time = time.time()

    print("=" * 65)
    print("      DEVALIGN — SUITE DE RECOLECCIÓN LATAM 100% TECH")
    print("=" * 65)
    mode_str = (
        "GetOnBoard only"
        if args.gob_only
        else "Computrabajo only" if args.ct_only else "Full Suite (GOB + CT)"
    )
    print(f"Modo: {mode_str}")
    print(f"Países Computrabajo: {args.countries}")
    print(f"Keywords CT: {args.keywords}")
    print(f"Meta por batch: {args.jobs_per_batch}")
    print(f"Exportar a Supabase: {not args.no_supabase}")
    print("=" * 65)

    # ──────────────────────────────────────────────────────────────────
    # FASE 1: GetOnBoard (API REST rápida, multi-categoría)
    # ──────────────────────────────────────────────────────────────────
    if not args.ct_only:
        print("\n" + "#" * 65)
        print(">>> INICIANDO FASE 1: GetOnBoard (API REST)")
        print("#" * 65)

        gob_output = "data/gob_latam_suite.json"
        try:
            run(
                target_jobs=args.jobs_per_batch * len(GOB_CATEGORIES),
                base_url=SITE_DEFAULTS["getonboard"],
                headless=True,
                no_supabase=args.no_supabase,
                output_file=gob_output,
                site="getonboard",
                categories=GOB_CATEGORIES,
                max_duplicates=args.max_duplicates,
            )
        except KeyboardInterrupt:
            print("\n[!] Fase GetOnBoard interrumpida por el usuario.")
            if (
                input("¿Deseas continuar con Computrabajo? (s/N): ").strip().lower()
                != "s"
            ):
                sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Fallo en fase GetOnBoard: {e}")

    # ──────────────────────────────────────────────────────────────────
    # FASE 2: Computrabajo Multi-País (HTML Playwright)
    # ──────────────────────────────────────────────────────────────────
    if not args.gob_only:
        print("\n" + "#" * 65)
        print(">>> INICIANDO FASE 2: Computrabajo Multi-País (LATAM)")
        print("#" * 65)

        for country in args.countries:
            country_name = ComputrabajoParser.SUPPORTED_COUNTRIES.get(
                country, country.upper()
            )
            print("\n" + "-" * 60)
            print(f"[*] Procesando Computrabajo — {country_name} [{country.upper()}]")
            print("-" * 60)

            ct_output = f"data/computrabajo_{country}.json"
            base_url = f"https://{country}.computrabajo.com/trabajo-de-desarrollador"

            try:
                run(
                    target_jobs=args.jobs_per_batch,
                    base_url=base_url,
                    headless=headless,
                    no_supabase=args.no_supabase,
                    output_file=ct_output,
                    site="computrabajo",
                    keywords=args.keywords,
                    max_duplicates=args.max_duplicates,
                    country=country,
                    auto_resume=True,
                )
            except KeyboardInterrupt:
                print(f"\n[!] Scraping de {country.upper()} interrumpido.")
                if (
                    input("¿Deseas pasar al siguiente país? (S/n): ").strip().lower()
                    == "n"
                ):
                    break
            except Exception as e:
                print(f"[ERROR] Error al procesar {country.upper()}: {e}")

    elapsed = (time.time() - start_time) / 60
    print("\n" + "=" * 65)
    print(f"[OK] Suite de recoleccion finalizada en {elapsed:.1f} minutos.")
    print("=" * 65)


if __name__ == "__main__":
    main()
