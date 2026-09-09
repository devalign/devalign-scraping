"""
Pipeline de limpieza de texto para NLP/ML.

Principio: limpiar ruido, NUNCA perder contexto semántico.
Cada método de limpieza es independiente y componible.
"""

import re

import ftfy
import html2text
from dataclasses import replace as dc_replace


class TextCleaner:
    """
    Pipeline de limpieza encadenada para textos de ofertas laborales.

    Aplica transformaciones en orden:
    1. fix_encoding — Repara unicode roto (mojibake)
    2. remove_html_artifacts — Elimina etiquetas residuales
    3. remove_noise_patterns — URLs, chars raros, IDs largos
    4. normalize_whitespace — Colapsa espacios múltiples
    """

    def __init__(self):
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = True
        self.h2t.ignore_images = True
        self.h2t.body_width = 0  # Sin saltos de línea artificiales

    def fix_encoding(self, text: str) -> str:
        """ftfy repara: â€™ → ', Ã³ → ó, caracteres mojibake."""
        return ftfy.fix_text(text)

    def remove_html_artifacts(self, text: str) -> str:
        """Elimina etiquetas HTML residuales y entidades."""
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&[a-zA-Z]+;", " ", text)  # &nbsp; &amp; etc.
        return text

    def normalize_whitespace(self, text: str) -> str:
        """Colapsa espacios múltiples y normaliza saltos de línea."""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)  # Máximo 2 saltos seguidos
        return text.strip()

    def remove_noise_patterns(self, text: str) -> str:
        """Elimina patrones que no aportan valor semántico."""
        patterns = [
            r"http\S+",  # URLs
            r"[^\w\s\.,;:()/\-+#áéíóúüñÁÉÍÓÚÜÑ]",  # Chars raros, preserva español
            r"\b\d{9,}\b",  # Números muy largos (IDs, teléfonos)
        ]
        for p in patterns:
            text = re.sub(p, " ", text)

        # Limpiar textos residuales de UI específicos de Computrabajo
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

    def clean_skills_list(self, skills: list) -> list:
        """
        Limpia y normaliza la lista de habilidades, eliminando duplicados
        y retornando una lista de Python limpia (que se mapea a ARRAY en Postgres).
        """
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
        """Busca patrones comunes de salarios en el texto crudo con soporte multi-moneda LATAM."""
        if not text:
            return ""
        # Buscar S/., $, USD, EUR, COP, MXN, CLP, ARS, PEN seguido de números (ej. S/ 3000, $ 2.500.000, COP 5'000.000)
        currency_pattern = r'(?:S/\.?|\$|USD|EUR|COP|MXN|CLP|ARS|PEN)'
        match = re.search(
            rf'{currency_pattern}\s*\d{{1,3}}(?:[.,\']\d{{3}})*(?:\s*-\s*{currency_pattern}?\s*\d{{1,3}}(?:[.,\']\d{{3}})*)?',
            text,
            re.IGNORECASE
        )
        if match:
            return match.group(0).strip()
        return ""

    def extract_experience_regex(self, text: str) -> str:
        """Busca patrones comunes de experiencia en el texto crudo."""
        if not text:
            return ""
        # Buscar X+ años, X a Y años, X years
        match = re.search(r'(\d+)\+?\s*(a\s*\d+)?\s*(años|years)\b', text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
        return ""

    def clean(self, offer) -> object:
        """
        Aplica limpieza a todos los campos del JobOffer.
        Retorna una nueva instancia (inmutabilidad del dataclass).

        Args:
            offer: JobOffer dataclass instance.

        Returns:
            Nueva instancia de JobOffer con campos limpiados.
        """
        clean_desc = self.clean_text_field(offer.full_description)
        
        salary = offer.salary.strip()
        if not salary:
            salary = self.extract_salary_regex(clean_desc)
            
        experience = offer.experience_years.strip().lower()
        if not experience:
            experience = self.extract_experience_regex(clean_desc)
            
        return dc_replace(
            offer,
            job_title=self.clean_text_field(offer.job_title),
            company=self.clean_text_field(offer.company),
            location=self.clean_text_field(offer.location),
            full_description=clean_desc,
            hard_skills=self.clean_skills_list(offer.hard_skills),
            soft_skills=self.clean_skills_list(offer.soft_skills),
            experience_years=experience,
            education_level=offer.education_level.strip().lower(),
            salary=salary,
        )
