"""
Gestión de estado, persistencia y ciclo de vida de una sesión de scraping.

Responsabilidades:
    - Acumular ofertas recolectadas en memoria.
    - Guardar checkpoints incrementales cada N ofertas (protección ante caídas).
    - Detectar y cargar checkpoints previos para reanudar sesiones interrumpidas.
    - Exponer un flag `should_stop` que el loop principal consulta para salidas
      limpias ante SIGINT / SIGTERM (graceful shutdown).
    - Ejecutar el guardado final (JSON local + Supabase) en un bloque `finally`.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


# Directorio donde se almacenan los checkpoints intermedios.
CHECKPOINT_DIR = Path("data/checkpoints")

# Un checkpoint se considera "reciente" si tiene menos de esta cantidad de horas.
RECENT_CHECKPOINT_HOURS = 12


class SessionManager:
    """
    Gestiona el estado completo de una sesión de scraping con persistencia resiliente.

    Garantías:
        - Nunca se pierden más de `flush_every` ofertas ante una interrupción.
        - Un checkpoint incluye las URLs ya procesadas para evitar re-scraping.
        - El método `save_final()` es idempotente: puede llamarse varias veces.

    Uso típico:
        session = SessionManager(output_file="data/results.json", flush_every=20)

        # Dentro del loop:
        session.add_offer(offer)      # Auto-flush si llega al límite
        if session.should_stop:
            break

        # En el bloque finally (siempre se ejecuta):
        session.save_final(exporter=supabase_exporter)
    """

    def __init__(
        self,
        output_file: str,
        target_jobs: int,
        base_url: str,
        flush_every: int = 20,
    ):
        self.output_file = output_file
        self.target_jobs = target_jobs
        self.base_url = base_url
        self.flush_every = flush_every

        self._collected: list = []
        self._processed_urls: set[str] = set()
        self._errors: int = 0
        self._current_page: int = 1
        self._skipped: int = 0
        self._filtered: int = 0
        self._shutdown_requested: bool = False
        self._started_at: str = datetime.now(timezone.utc).isoformat()
        self._checkpoint_path: Path | None = None
        self._session_checkpoints: list[Path] = []

        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Propiedades públicas
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        """Número de ofertas válidas recolectadas."""
        return len(self._collected)

    @property
    def errors(self) -> int:
        return self._errors

    @property
    def current_page(self) -> int:
        return self._current_page

    @current_page.setter
    def current_page(self, value: int) -> None:
        self._current_page = value

    @property
    def should_stop(self) -> bool:
        """True si se solicitó un apagado limpio (SIGINT/SIGTERM)."""
        return self._shutdown_requested

    # ------------------------------------------------------------------
    # Control de sesión
    # ------------------------------------------------------------------

    def request_shutdown(self) -> None:
        """Activa el flag de apagado limpio. Llamado desde el signal handler."""
        if not self._shutdown_requested:
            print("\n\n[!] Ctrl+C detectado. Terminando limpiamente...")
            self._shutdown_requested = True

    def register_error(self) -> None:
        self._errors += 1

    def register_skip(self) -> None:
        """Registra una URL descartada por pre-filtro (no-IT)."""
        self._skipped += 1

    def register_filtered(self) -> None:
        """Registra una oferta descartada por post-filtro (sin skills/desc)."""
        self._filtered += 1

    def is_already_processed(self, url: str) -> bool:
        """Comprueba si una URL ya fue procesada (relevante en modo resume)."""
        return url.split("#")[0] in self._processed_urls

    def mark_processed(self, url: str) -> None:
        """Marca una URL como procesada (se llama incluso en ofertas descartadas)."""
        self._processed_urls.add(url.split("#")[0])

    # ------------------------------------------------------------------
    # Acumulación de ofertas
    # ------------------------------------------------------------------

    def add_offer(self, offer) -> None:
        """
        Agrega una oferta válida a la sesión y dispara un flush si corresponde.

        Args:
            offer: Instancia de JobOffer ya validada por JobFilter.
        """
        self._collected.append(offer)
        self.mark_processed(offer.source_url)

        if self.count % self.flush_every == 0:
            self._flush_checkpoint()

    # ------------------------------------------------------------------
    # Persistencia — Checkpoints intermedios
    # ------------------------------------------------------------------

    def _flush_checkpoint(self) -> None:
        """
        Guarda el estado actual en un archivo de checkpoint.
        Se llama automáticamente desde add_offer().
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = CHECKPOINT_DIR / f"checkpoint_{timestamp}.json"

        data = {
            "metadata": {
                "started_at": self._started_at,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "total_collected": self.count,
                "target_jobs": self.target_jobs,
                "current_page": self._current_page,
                "errors": self._errors,
                "skipped": self._skipped,
                "filtered": self._filtered,
                "base_url": self.base_url,
            },
            "processed_urls": list(self._processed_urls),
            "offers": [asdict(o) for o in self._collected],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self._checkpoint_path = path
        self._session_checkpoints.append(path)
        print(f"   [CHECKPOINT] {self.count} ofertas guardadas → {path.name}")

        # Limpiar checkpoints viejos (más de RECENT_CHECKPOINT_HOURS horas)
        self._cleanup_old_checkpoints()

    def _cleanup_old_checkpoints(self) -> None:
        """Elimina checkpoints con más de RECENT_CHECKPOINT_HOURS horas."""
        now = datetime.now(timezone.utc).timestamp()
        limit = RECENT_CHECKPOINT_HOURS * 3600

        for ck in CHECKPOINT_DIR.glob("checkpoint_*.json"):
            if now - ck.stat().st_mtime > limit:
                try:
                    ck.unlink()
                except OSError:
                    pass

    # ------------------------------------------------------------------
    # Persistencia — Detección y carga de checkpoints
    # ------------------------------------------------------------------

    @staticmethod
    def find_recent_checkpoint() -> Path | None:
        """
        Busca el checkpoint más reciente dentro del límite de horas permitido.

        Returns:
            Path al checkpoint más reciente, o None si no hay ninguno válido.
        """
        if not CHECKPOINT_DIR.exists():
            return None

        checkpoints = sorted(CHECKPOINT_DIR.glob("checkpoint_*.json"), reverse=True)
        if not checkpoints:
            return None

        now = datetime.now(timezone.utc).timestamp()
        limit = RECENT_CHECKPOINT_HOURS * 3600
        latest = checkpoints[0]

        if now - latest.stat().st_mtime <= limit:
            return latest
        return None

    def load_checkpoint(self, path: Path) -> None:
        """
        Carga el estado desde un checkpoint para reanudar la sesión.

        Args:
            path: Path al archivo de checkpoint a cargar.
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("metadata", {})
        self._current_page = meta.get("current_page", 1)
        self._errors = meta.get("errors", 0)
        self._skipped = meta.get("skipped", 0)
        self._filtered = meta.get("filtered", 0)
        self._started_at = meta.get("started_at", self._started_at)
        self._processed_urls = set(data.get("processed_urls", []))

        # Reconstruir ofertas como dicts (se usarán directamente en save_final)
        self._collected = data.get("offers", [])

        print(f"   [RESUME] Cargado checkpoint: {path.name}")
        print(f"   [RESUME] {self.count} ofertas previas, retomando desde página {self._current_page}")

    # ------------------------------------------------------------------
    # Guardado final
    # ------------------------------------------------------------------

    def save_final(self, exporter=None) -> None:
        """
        Guarda el resultado final en JSON local y opcionalmente en Supabase.
        Diseñado para ejecutarse en un bloque `finally` — siempre se llama.

        Args:
            exporter: Instancia de SupabaseExporter, o None para omitir Supabase.
        """
        print(f"\n{'-' * 50}")
        print("Summary:")
        print(f"   Recolectadas (IT válidas): {self.count}")
        print(f"   Descartadas pre-filtro:    {self._skipped}")
        print(f"   Descartadas post-filtro:   {self._filtered}")
        print(f"   Errores:                   {self._errors}")

        if not self._collected:
            print("\n[!] No se recolectaron ofertas.")
            return

        # Supabase
        if exporter:
            # Si los elementos son dicts (cargados desde checkpoint), los
            # pasamos directamente; si son dataclasses, los convertimos.
            if isinstance(self._collected[0], dict):
                exporter.save_dicts(self._collected)
            else:
                exporter.save(self._collected)

        # JSON local
        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)

        # Normalizar a lista de dicts para serialización uniforme
        if self._collected and not isinstance(self._collected[0], dict):
            from dataclasses import asdict as _asdict
            records = [_asdict(o) for o in self._collected]
        else:
            records = self._collected

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] Datos guardados en: {self.output_file}")

        # Eliminar checkpoints si terminó con éxito (no fue interrumpido)
        if not self._shutdown_requested and self._session_checkpoints:
            cleaned = 0
            for ckpt in self._session_checkpoints:
                try:
                    if ckpt.exists():
                        ckpt.unlink()
                        cleaned += 1
                except OSError:
                    pass
            if cleaned > 0:
                print(f"[OK] {cleaned} checkpoint(s) de la sesión limpiados.")
