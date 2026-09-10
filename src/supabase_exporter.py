"""
Exportador de datos hacia Supabase.

Realiza la inserción o actualización (upsert) de ofertas laborales
en la base de datos de Supabase, utilizando la source_url como clave única.

Nota: El filtrado de calidad (blacklist, skills, descripción mínima) se realiza
ANTES de llegar aquí, en JobFilter. Este módulo solo recibe ofertas ya validadas.
"""

import os
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


class SupabaseExporter:
    """
    Exporta una lista de JobOffer a la base de datos de Supabase.

    Responsabilidad única: upsert de registros ya validados.
    El filtrado de calidad es responsabilidad de JobFilter.
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
        Consulta las URLs de ofertas ya guardadas en Supabase en los últimos N días,
        filtrando por portal y paginando para sobrepasar el límite de 1000 registros de PostgREST.

        Retorna:
            Conjunto de URLs existentes.
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

    def save(self, offers: list) -> None:
        """
        Sube una lista de JobOffer (dataclasses) a Supabase.

        Las ofertas ya vienen validadas por JobFilter — no se filtra aquí.
        Aplica _map_to_db() para renombrar campos del dataclass a columnas de la DB.

        Args:
            offers: Lista de instancias de JobOffer.
        """
        if not offers:
            print("[WARN] No hay ofertas para subir a Supabase.")
            return

        records = [self._map_to_db(asdict(o)) for o in offers]
        self._upsert(records)

    def _map_to_db(self, record: dict) -> dict:
        """
        Traduce los campos del dataclass JobOffer a columnas de la tabla job_offers.

        Cambios aplicados:
            - hard_skills  → raw_hard_skills  (JSONB staging en la DB)
            - soft_skills  → raw_soft_skills  (JSONB staging en la DB)

        El motor ML de devalign-api normaliza estos arrays posteriormente
        y puebla la tabla transaccional offer_skills.

        Args:
            record: Dict generado por dataclasses.asdict(offer).

        Returns:
            Dict con las keys alineadas a las columnas de job_offers.
        """
        record["raw_hard_skills"] = record.pop("hard_skills", [])
        record["raw_soft_skills"] = record.pop("soft_skills", [])
        return record

    def save_dicts(self, records: list[dict]) -> None:
        """
        Sube una lista de ofertas ya en formato dict (cargadas desde checkpoint).

        Args:
            records: Lista de dicts con la estructura de JobOffer.
        """
        if not records:
            print("[WARN] No hay registros para subir a Supabase.")
            return

        mapped_records = []
        for r in records:
            r_copy = dict(r)
            if "hard_skills" in r_copy:
                r_copy["raw_hard_skills"] = r_copy.pop("hard_skills", [])
            if "soft_skills" in r_copy:
                r_copy["raw_soft_skills"] = r_copy.pop("soft_skills", [])
            mapped_records.append(r_copy)

        self._upsert(mapped_records)

    def _upsert(self, records: list[dict]) -> None:
        """
        Ejecuta el upsert a Supabase usando source_url como constraint único.

        Args:
            records: Lista de dicts con la estructura de la tabla job_offers.
        """
        print(f"[*] Subiendo {len(records)} ofertas a Supabase...")
        try:
            response = (
                self.supabase.table(self.table_name)
                .upsert(records, on_conflict="source_url")
                .execute()
            )
            print(
                f"[OK] Supabase: {len(response.data)} registros procesados exitosamente."
            )
        except Exception as e:
            print(f"[ERROR] Error al subir a Supabase: {e}")
