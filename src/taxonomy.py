"""
Servicio centralizado de Taxonomía de Habilidades Técnicas y Blandas.

Responsabilidades:
1. Sincronizar dinámicamente las habilidades estándar desde Supabase (tabla `skills`)
   con una política de caché TTL (7 días) para proteger la cuota del Free Plan.
2. Servir como fallback offline incondicional mediante `data/skills_taxonomy.json`.
3. Extraer habilidades de textos libres mediante regex compilado con límites
   de palabra seguros para símbolos técnicos (ej. c#, .net, c++).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Optional

TAXONOMY_FILE = Path(__file__).resolve().parent.parent / "data" / "skills_taxonomy.json"
CACHE_TTL_SECONDS = 7 * 24 * 3600  # 7 días

DEFAULT_HARD_SKILLS: list[str] = [
    ".net",
    "adobe xd",
    "agile",
    "android",
    "angular",
    "aws",
    "azure",
    "backend",
    "blockchain",
    "c#",
    "c++",
    "ci/cd",
    "cloud computing",
    "cypress",
    "cybersecurity",
    "dart",
    "devops",
    "django",
    "docker",
    "fastapi",
    "figma",
    "firebase",
    "flask",
    "flutter",
    "frontend",
    "fullstack",
    "gcp",
    "git",
    "golang",
    "graphql",
    "html",
    "css",
    "ios",
    "java",
    "javascript",
    "jenkins",
    "jest",
    "jira",
    "kanban",
    "kotlin",
    "kubernetes",
    "laravel",
    "linux",
    "machine learning",
    "microservicios",
    "mongodb",
    "mysql",
    "next.js",
    "node",
    "pandas",
    "php",
    "postgresql",
    "power bi",
    "python",
    "qa",
    "rails",
    "react",
    "react native",
    "redis",
    "rest api",
    "ruby",
    "sass",
    "scikit-learn",
    "scrum",
    "selenium",
    "software engineering",
    "solidity",
    "spring boot",
    "sql",
    "swift",
    "system design",
    "tableau",
    "tensorflow",
    "terraform",
    "typescript",
    "unity",
    "unreal engine",
    "ux/ui",
    "vue",
]

DEFAULT_SOFT_SKILLS: list[str] = [
    "adaptabilidad",
    "aprendizaje rápido",
    "atención al detalle",
    "autonomía",
    "capacidad de análisis",
    "colaboración",
    "communication",
    "comunicación",
    "creatividad",
    "empatía",
    "gestión del tiempo",
    "leadership",
    "liderazgo",
    "negociación",
    "organización",
    "orientado a resultados",
    "pensamiento crítico",
    "proactivo",
    "resolución de problemas",
    "responsabilidad",
    "teamwork",
    "tolerancia a la frustración",
    "trabajo en equipo",
]


def _build_skill_regex(skill: str) -> re.Pattern:
    r"""
    Construye un regex con límites no-palabra (?<!\w) y (?!\w)
    que preserva símbolos técnicos como c#, .net, c++ sin falsos positivos.
    """
    escaped = re.escape(skill.lower().strip())
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


class SkillTaxonomyService:
    """
    Servicio de taxonomía de habilidades compartida entre todos los parsers y filtros.
    """

    _instance: Optional[SkillTaxonomyService] = None

    def __init__(
        self,
        hard_skills: Optional[list[str]] = None,
        soft_skills: Optional[list[str]] = None,
        file_path: Optional[Path] = None,
    ):
        self.file_path = file_path or TAXONOMY_FILE
        self._hard_skills: list[str] = []
        self._soft_skills: list[str] = []
        self._compiled_hard: list[tuple[str, re.Pattern]] = []
        self._compiled_soft: list[tuple[str, re.Pattern]] = []

        if hard_skills is not None or soft_skills is not None:
            self.set_skills(hard_skills or [], soft_skills or [])
        else:
            self.load_from_cache()

    @classmethod
    def get_instance(cls) -> SkillTaxonomyService:
        """Retorna la instancia singleton del servicio."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def hard_skills(self) -> list[str]:
        return list(self._hard_skills)

    @property
    def soft_skills(self) -> list[str]:
        return list(self._soft_skills)

    def set_skills(self, hard: list[str], soft: list[str]) -> None:
        """Actualiza y precompila los patrones de habilidades."""
        self._hard_skills = sorted(
            list(set(s.lower().strip() for s in hard if s.strip()))
        )
        self._soft_skills = sorted(
            list(set(s.lower().strip() for s in soft if s.strip()))
        )
        self._compiled_hard = [(s, _build_skill_regex(s)) for s in self._hard_skills]
        self._compiled_soft = [(s, _build_skill_regex(s)) for s in self._soft_skills]

    def load_from_cache(self) -> bool:
        """Carga las habilidades desde el archivo local de taxonomía (con fallback por defecto)."""
        if not self.file_path.exists():
            self.set_skills(DEFAULT_HARD_SKILLS, DEFAULT_SOFT_SKILLS)
            return True
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            hard = data.get("hard_skills", [])
            soft = data.get("soft_skills", [])
            self.set_skills(hard or DEFAULT_HARD_SKILLS, soft or DEFAULT_SOFT_SKILLS)
            return True
        except Exception as e:
            print(f"[WARN] Error al cargar taxonomía local desde {self.file_path}: {e}")
            self.set_skills(DEFAULT_HARD_SKILLS, DEFAULT_SOFT_SKILLS)
            return True

    def sync_with_supabase(self, exporter, force_refresh: bool = False) -> None:
        """
        Sincroniza la taxonomía con la tabla `skills` en Supabase.
        Respeta una ventana de TTL (7 días) para no saturar peticiones ni cuota Free.
        """
        if not exporter:
            return

        should_fetch = force_refresh
        if not should_fetch:
            if not self.file_path.exists():
                should_fetch = True
            else:
                mtime = os.path.getmtime(self.file_path)
                if (time.time() - mtime) > CACHE_TTL_SECONDS:
                    should_fetch = True

        if not should_fetch:
            return

        try:
            print("[*] Sincronizando taxonomía estándar desde Supabase...")
            remote_skills = exporter.get_standard_skills()
            if remote_skills:
                # Combinar con los existentes para no perder habilidades locales
                combined_hard = list(
                    set(self._hard_skills + [s.lower().strip() for s in remote_skills])
                )
                self.set_skills(combined_hard, self._soft_skills)

                # Persistir snapshot offline actualizado
                self.file_path.parent.mkdir(parents=True, exist_ok=True)
                snapshot = {
                    "version": "1.0",
                    "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "hard_skills": self._hard_skills,
                    "soft_skills": self._soft_skills,
                }
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, ensure_ascii=False, indent=2)
                print(
                    f"[OK] Taxonomía actualizada con {len(self._hard_skills)} skills."
                )
        except Exception as e:
            print(f"[WARN] No se pudo sincronizar taxonomía desde Supabase: {e}")

    def extract_skills(self, text: str) -> tuple[list[str], list[str]]:
        """
        Extrae habilidades técnicas y blandas presentes en el texto.
        Retorna: (hard_skills_encontradas, soft_skills_encontradas).
        """
        if not text:
            return [], []

        matched_hard = [
            name for name, pattern in self._compiled_hard if pattern.search(text)
        ]
        matched_soft = [
            name for name, pattern in self._compiled_soft if pattern.search(text)
        ]

        return matched_hard, matched_soft
