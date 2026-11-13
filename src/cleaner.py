"""
Pipeline de limpieza y normalización de texto para NLP/ML.

Principio: Limpiar ruido sintáctico y de codificación, preservando
estrictamente el contexto semántico de la vacante.
"""

from __future__ import annotations

import re
from dataclasses import replace as dc_replace
import ftfy

from src.models import JobOffer


class TextCleaner:
    """
    Pipeline de saneamiento encadenado para textos de ofertas laborales:
    1. fix_encoding — Repara unicode roto (mojibake)
    2. remove_html_artifacts — Elimina etiquetas residuales y entidades HTML
    3. remove_noise_patterns — URLs, artefactos de UI y secuencias numéricas de ruido
    4. normalize_whitespace — Colapsa espacios y saltos de línea excesivos
    """

    def fix_encoding(self, text: str) -> str:
        """Repara mojibake: â€™ → ', Ã³ → ó, etc."""
        return ftfy.fix_text(text)

    def remove_html_artifacts(self, text: str) -> str:
        """Elimina etiquetas HTML residuales y entidades comunes."""
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-zA-Z]+;", " ", text)
        return text

    def normalize_whitespace(self, text: str) -> str:
        """Colapsa espacios múltiples y limita saltos de línea a máximo 2."""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def remove_noise_patterns(self, text: str) -> str:
        """Elimina URLs, números largos de control y texto residual de UI."""
        patterns = [
            r"http\S+",
            r"[^\w\s\.,;:()/\-+#áéíóúüñÁÉÍÓÚÜÑ]",
            r"\b\d{9,}\b",
        ]
        for p in patterns:
            text = re.sub(p, " ", text)

        ui_noise = [
            "Ocultaste esta oferta, pulsa",
            "Recuperar oferta",
            "para verla de nuevo en los listados",
            "Eliminado de",
            "Ofertas ocultas",
            "Deshacer",
            "Postularme",
            "Avísame con ofertas similares",
            "Ocultar aviso",
            "Mostrar oferta",
            "Denunciar empleo",
            "Gracias por ayudarnos a mejorar Computrabajo",
            "Nos tomamos muy en serio tus comentarios y lo revisaremos lo antes posible.",
        ]
        for noise in ui_noise:
            text = text.replace(noise, " ")

        return text

    def clean_skills_list(self, skills: list[str]) -> list[str]:
        """Limpia, normaliza a minúsculas, deduplica y ordena la lista de habilidades."""
        if not skills:
            return []
        return sorted(list(set(s.lower().strip() for s in skills if s.strip())))

    def clean_text_field(self, text: str) -> str:
        """Aplica el pipeline completo sobre un campo de texto libre."""
        if not text:
            return ""
        text = self.fix_encoding(text)
        text = self.remove_html_artifacts(text)
        text = self.remove_noise_patterns(text)
        text = self.normalize_whitespace(text)
        return text

    def extract_salary_regex(self, text: str) -> str:
        """Busca patrones de salarios en el texto crudo con soporte multi-moneda LATAM."""
        if not text:
            return ""
        currency_pattern = r"(?:S/\.?|\$|USD|EUR|COP|MXN|CLP|ARS|PEN)"
        num_pattern = r"\d{1,3}(?:[.,\s\']\d{3})*(?:[.,]\d{2})?"
        full_pattern = (
            rf"{currency_pattern}\s*{num_pattern}"
            rf"(?:\s*-\s*{currency_pattern}?\s*{num_pattern})?"
        )
        match = re.search(full_pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
        return ""

    def extract_experience_regex(self, text: str) -> str:
        """Busca patrones de experiencia en el texto crudo."""
        if not text:
            return ""
        match = re.search(
            r"(\d+)\+?\s*(a\s*\d+)?\s*(años|years)\b", text, re.IGNORECASE
        )
        if match:
            return match.group(0).strip()
        return ""

    def clean(self, offer: JobOffer) -> JobOffer:
        """
        Aplica limpieza integral a los campos de JobOffer retornando una nueva instancia.
        """
        clean_desc = self.clean_text_field(offer.full_description)

        salary = offer.salary.strip()
        if not salary or salary.lower() == "no especificado":
            extracted_sal = self.extract_salary_regex(clean_desc)
            if extracted_sal:
                salary = extracted_sal

        experience = offer.experience_years.strip().lower()
        if not experience or experience == "no especificado":
            extracted_exp = self.extract_experience_regex(clean_desc)
            if extracted_exp:
                experience = extracted_exp

        return dc_replace(
            offer,
            job_title=self.clean_text_field(offer.job_title),
            company=self.clean_text_field(offer.company),
            location=self.clean_text_field(offer.location),
            full_description=clean_desc,
            hard_skills=self.clean_skills_list(offer.hard_skills),
            soft_skills=self.clean_skills_list(offer.soft_skills),
            experience_years=experience or "No especificado",
            education_level=offer.education_level.strip().lower() or "No especificado",
            salary=salary or "A convenir",
        )
