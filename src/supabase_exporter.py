"""
Exportador de datos hacia Supabase.

Realiza la inserción o actualización (upsert) de ofertas laborales
en la base de datos de Supabase, utilizando la source_url como clave única.
"""

import os
from dataclasses import asdict
from supabase import create_client, Client


class SupabaseExporter:
    """
    Exporta una lista de JobOffer a la base de datos de Supabase.

    Maneja:
    - Conexión mediante variables de entorno
    - Upsert para evitar duplicados basados en source_url
    - Filtrado básico de calidad
    """

    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError(
                "Faltan SUPABASE_URL o SUPABASE_KEY en las variables de entorno"
            )

        self.supabase: Client = create_client(url, key)
        self.table_name = "job_offers"

    def _is_valid_it_job(self, o) -> bool:
        """
        Valida si la oferta es realmente de IT y tiene datos suficientes.
        """
        # 1. Filtro por palabras prohibidas en el título (evita vendedores, CNC, etc.)
        blacklist = [
            'vendedor', 'ventas', 'cnc', 'matricero', 'comercial', 
            'maquinaria', 'industrial', 'campo', 'consumo'
        ]
        title_lower = o.job_title.lower()
        if any(word in title_lower for word in blacklist):
            return False

        # 2. Filtro: Debe tener al menos una habilidad técnica (lo que pidió el partner)
        if not o.hard_skills:
            return False

        # 3. Filtro: Descripción mínima (subimos a 150 chars para calidad)
        if len(o.full_description) < 150:
            return False

        return True

    def save(self, offers: list) -> None:
        """
        Sube la lista de ofertas a Supabase tras un filtrado estricto.

        Args:
            offers: Lista de JobOffer dataclass instances.
        """
        if not offers:
            print("[WARN] No hay ofertas para subir a Supabase.")
            return

        # Convertir dataclasses a dicts y filtrar por calidad estricta
        valid_records = []
        for o in offers:
            if self._is_valid_it_job(o):
                record = asdict(o)
                valid_records.append(record)

        if not valid_records:
            print("[WARN] No hay ofertas válidas tras el filtrado estricto.")
            return

        print(f"[*] Subiendo {len(valid_records)} ofertas a Supabase...")

        try:
            # Upsert usando source_url como constraint para evitar duplicados
            # Nota: on_conflict='source_url' requiere que la columna tenga un UNIQUE constraint
            response = (
                self.supabase.table(self.table_name)
                .upsert(valid_records, on_conflict="source_url")
                .execute()
            )

            print(
                f"[OK] Supabase: {len(response.data)} registros procesados exitosamente."
            )

        except Exception as e:
            print(f"[ERROR] Error al subir a Supabase: {e}")
