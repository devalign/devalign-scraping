"""
Exportador de datos hacia Supabase.

Realiza la inserción o actualización (upsert) en lotes (batching) de ofertas
laborales en Supabase, utilizando source_url como clave única.
"""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

BATCH_SIZE = 100


class SupabaseExporter:
    """
    Exporta ofertas a Supabase con control de lotes y consulta taxonomía.
    """

    def __init__(self):
        load_dotenv()
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError(
                "Faltan SUPABASE_URL o SUPABASE_KEY en las variables de entorno"
            )

        self.supabase: Client = create_client(url, key)
        self.table_name = "job_offers"

    def get_existing_urls(self, portal_name: str, days_limit: int = 90) -> set[str]:
        """
        Consulta las URLs de ofertas ya guardadas en Supabase en los últimos N días.
        """
        print(
            f"[*] Consultando URLs existentes en Supabase para {portal_name} "
            f"(últimos {days_limit} días)..."
        )
        try:
            since_date = (
                datetime.now(timezone.utc) - timedelta(days=days_limit)
            ).isoformat()
            urls: set[str] = set()
            page_size = 1000
            start = 0

            while True:
                response = (
                    self.supabase.table(self.table_name)
                    .select("source_url")
                    .eq("portal", portal_name)
                    .gte("scraped_at", since_date)
                    .range(start, start + page_size - 1)
                    .execute()
                )
                batch = [
                    row["source_url"] for row in response.data if "source_url" in row
                ]
                urls.update(batch)
                if len(batch) < page_size:
                    break
                start += page_size

            print(f"[OK] Se obtuvieron {len(urls)} URLs existentes desde Supabase.")
            return urls
        except Exception as e:
            print(f"[ERROR] Error al consultar URLs existentes de Supabase: {e}")
            return set()

    def get_standard_skills(self) -> list[str]:
        """
        Obtiene la lista de nombres de habilidades estándar desde la tabla `skills`.
        """
        try:
            skills: list[str] = []
            page_size = 1000
            start = 0

            while True:
                response = (
                    self.supabase.table("skills")
                    .select("name")
                    .range(start, start + page_size - 1)
                    .execute()
                )
                batch = [
                    row["name"].strip() for row in response.data if row.get("name")
                ]
                skills.extend(batch)
                if len(batch) < page_size:
                    break
                start += page_size

            return skills
        except Exception as e:
            print(f"[WARN] Error al consultar tabla skills en Supabase: {e}")
            return []

    def _map_to_db(self, record: dict) -> dict:
        """
        Mapea el esquema del dataclass JobOffer a las columnas de la tabla job_offers.
        """
        r_copy = dict(record)
        if "hard_skills" in r_copy:
            r_copy["raw_hard_skills"] = r_copy.pop("hard_skills")
        elif "raw_hard_skills" not in r_copy:
            r_copy["raw_hard_skills"] = []

        if "soft_skills" in r_copy:
            r_copy["raw_soft_skills"] = r_copy.pop("soft_skills")
        elif "raw_soft_skills" not in r_copy:
            r_copy["raw_soft_skills"] = []

        country = r_copy.get("country")
        r_copy["country"] = str(country).strip().lower() if country else None
        return r_copy

    def save(self, offers: list) -> None:
        """
        Sube una lista de JobOffer (dataclasses) a Supabase.
        """
        if not offers:
            print("[WARN] No hay ofertas para subir a Supabase.")
            return

        records = [self._map_to_db(asdict(o)) for o in offers]
        self._upsert(records)

    def save_dicts(self, records: list[dict]) -> None:
        """
        Sube una lista de ofertas ya en formato dict.
        """
        if not records:
            print("[WARN] No hay registros para subir a Supabase.")
            return

        mapped_records = [self._map_to_db(r) for r in records]
        self._upsert(mapped_records)

    def _upsert(self, records: list[dict]) -> None:
        """
        Ejecuta upsert en lotes de BATCH_SIZE (100) para no saturar PostgREST.
        Lanza la excepción si algún lote falla para proteger los checkpoints.
        """
        total = len(records)
        print(f"[*] Subiendo {total} ofertas a Supabase en lotes de {BATCH_SIZE}...")
        processed = 0

        for i in range(0, total, BATCH_SIZE):
            batch = records[i : i + BATCH_SIZE]
            try:
                response = (
                    self.supabase.table(self.table_name)
                    .upsert(batch, on_conflict="source_url")
                    .execute()
                )
                processed += len(response.data or batch)
            except Exception as e:
                print(f"[ERROR] Falló lote {i // BATCH_SIZE + 1} de Supabase: {e}")
                raise RuntimeError(f"Error al sincronizar con Supabase: {e}") from e

        print(f"[OK] Supabase: {processed} registros procesados exitosamente.")
