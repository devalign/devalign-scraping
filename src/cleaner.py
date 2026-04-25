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

    def normalize_skills_list(self, skills: list) -> str:
        """
        Convierte lista de skills a string delimitado por '|'.

        Formato elegido porque las comas rompen el CSV y '|' es
        estándar en datasets de NLP para listas dentro de celdas.
        """
        return " | ".join(sorted(set(s.lower().strip() for s in skills if s.strip())))

    def clean_text_field(self, text: str) -> str:
        """Aplica el pipeline completo sobre un campo de texto libre."""
        text = self.fix_encoding(text)
        text = self.remove_html_artifacts(text)
        text = self.remove_noise_patterns(text)
        text = self.normalize_whitespace(text)
        return text

    def clean(self, offer) -> object:
        """
        Aplica limpieza a todos los campos del JobOffer.
        Retorna una nueva instancia (inmutabilidad del dataclass).

        Args:
            offer: JobOffer dataclass instance.

        Returns:
            Nueva instancia de JobOffer con campos limpiados.
        """
        return dc_replace(
            offer,
            job_title=self.clean_text_field(offer.job_title),
            company=self.clean_text_field(offer.company),
            location=self.clean_text_field(offer.location),
            full_description=self.clean_text_field(offer.full_description),
            hard_skills=self.normalize_skills_list(offer.hard_skills),
            soft_skills=self.normalize_skills_list(offer.soft_skills),
            experience_years=offer.experience_years.strip().lower(),
            education_level=offer.education_level.strip().lower(),
        )
