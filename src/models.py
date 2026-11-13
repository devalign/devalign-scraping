"""
Modelos de dominio para el módulo de scraping.

Define la entidad central JobOffer que representa una oferta laboral estructurada
compartida por todos los parsers, filtros y exportadores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class JobOffer:
    """
    Schema de datos de una oferta laboral estructurada.
    Coincide con el esquema de almacenamiento y la tabla job_offers en Supabase.
    """

    job_title: str = ""
    company: str = ""
    location: str = ""
    country: str = ""  # Código ISO-2 (pe, co, mx, cl, ar), 'latam' o ''
    salary: str = ""  # Ej: "S/. 3,500", "$ 5.000.000 COP", "A convenir"
    modality: str = ""  # Ej: "Remoto", "Presencial", "Híbrido"
    date_posted: str = ""  # Ej: "Hace 2 días", "Ayer", "2026-05-10"
    hard_skills: list[str] = field(default_factory=list)
    soft_skills: list[str] = field(default_factory=list)
    experience_years: str = ""  # Ej: "2-4", "5+", "No especificado"
    education_level: str = ""  # Ej: "universitaria", "técnica", "indiferente"
    full_description: str = ""  # Texto íntegro limpio — crítico para modelos NLP/ML
    source_url: str = ""  # Clave única
    portal: str = (
        ""  # Ej: "computrabajo", "getonboard", "remotive", "arbeitnow", "weworkremotely"
    )
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
