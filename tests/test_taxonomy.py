"""
Tests para SkillTaxonomyService: carga, sincronización con TTL y extracción precisa.
"""

from unittest.mock import MagicMock
import pytest

from src.taxonomy import SkillTaxonomyService


@pytest.fixture
def taxonomy_service():
    # Instancia aislada para tests
    service = SkillTaxonomyService(
        hard_skills=["python", "react", "c#", ".net", "docker", "qa"],
        soft_skills=["liderazgo", "trabajo en equipo", "comunicación"],
    )
    return service


def test_extract_skills_standard(taxonomy_service):
    text = (
        "Buscamos desarrollador con experiencia en Python y Docker, "
        "orientado al trabajo en equipo y liderazgo."
    )
    hard, soft = taxonomy_service.extract_skills(text)
    assert "python" in hard
    assert "docker" in hard
    assert "trabajo en equipo" in soft
    assert "liderazgo" in soft


def test_extract_skills_with_technical_symbols(taxonomy_service):
    text = "Experiencia sólida en C# y desarrollo sobre .NET 8.0 con microservicios."
    hard, soft = taxonomy_service.extract_skills(text)
    assert "c#" in hard
    assert ".net" in hard


def test_extract_skills_avoids_substring_false_positives(taxonomy_service):
    # 'react' no debe coincidir en 'reactivar'
    text = "El candidato debe reactivar cuentas y liderar procesos."
    hard, soft = taxonomy_service.extract_skills(text)
    assert "react" not in hard
    assert "liderazgo" not in hard or "liderar" not in soft


def test_sync_with_supabase_ttl(tmp_path):
    temp_file = tmp_path / "skills_taxonomy.json"
    service = SkillTaxonomyService(
        hard_skills=["python"],
        soft_skills=["liderazgo"],
        file_path=temp_file,
    )
    mock_exporter = MagicMock()
    mock_exporter.get_standard_skills.return_value = [
        "Kubernetes",
        "TypeScript",
        "Python",
    ]

    service.sync_with_supabase(mock_exporter, force_refresh=True)
    assert "kubernetes" in service.hard_skills
    assert "typescript" in service.hard_skills
    assert mock_exporter.get_standard_skills.call_count == 1
    assert temp_file.exists()
