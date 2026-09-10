"""
Tests unitarios para JobFilter con soporte multilingüe y exenciones IT.
"""

import pytest
from src.job_filter import JobFilter
from src.parser import JobOffer


@pytest.fixture
def job_filter():
    return JobFilter()


def test_is_relevant_discards_spanish_non_it(job_filter):
    assert not job_filter.is_relevant(
        "Vendedor de Campo", "https://pe.computrabajo.com/vendedor-de-campo"
    )
    assert not job_filter.is_relevant(
        "Chofer de Reparto", "https://pe.computrabajo.com/chofer-reparto"
    )
    assert not job_filter.is_relevant(
        "Asesor Comercial Call Center", "https://pe.computrabajo.com/asesor-comercial"
    )


def test_is_relevant_discards_german_non_it(job_filter):
    assert not job_filter.is_relevant(
        "Bilanzbuchhalter / Senior Accountant (m/w/d)", "https://arbeitnow.com/job/123"
    )
    assert not job_filter.is_relevant(
        "Steuerberater (m/w/d)", "https://arbeitnow.com/job/456"
    )
    assert not job_filter.is_relevant(
        "Online Marketing Manager (m/w/d)", "https://arbeitnow.com/job/789"
    )
    assert not job_filter.is_relevant(
        "Teamleiter Logistik (m/w/d)", "https://arbeitnow.com/job/101"
    )


def test_is_relevant_discards_english_non_it(job_filter):
    assert not job_filter.is_relevant(
        "Senior HR Specialist", "https://example.com/hr-specialist"
    )
    assert not job_filter.is_relevant(
        "Inside Sales Representative", "https://example.com/sales-rep"
    )
    assert not job_filter.is_relevant(
        "Content Reviewer - English US", "https://example.com/content-reviewer"
    )


def test_is_relevant_discards_empty_titles(job_filter):
    assert not job_filter.is_relevant("", "https://pe.computrabajo.com/oferta-123")
    assert not job_filter.is_relevant("   ", "https://pe.computrabajo.com/oferta-456")


def test_is_relevant_accepts_valid_tech_and_exemptions(job_filter):
    assert job_filter.is_relevant(
        "Full-Stack Developer", "https://pe.computrabajo.com/full-stack-developer"
    )
    assert job_filter.is_relevant("DevOps Engineer", "https://example.com/devops")
    # Exención tecnológica sobre títulos con palabras clave de ventas o marketing
    assert job_filter.is_relevant(
        "Salesforce Developer", "https://example.com/salesforce-developer"
    )
    assert job_filter.is_relevant(
        "Marketing Data Engineer", "https://example.com/marketing-data-engineer"
    )


def test_is_valid_it_job(job_filter):
    # Oferta válida con hard skills y descripción suficiente
    valid_offer = JobOffer(
        job_title="Backend Developer",
        source_url="https://getonbrd.com/jobs/backend",
        hard_skills=["python", "django", "postgresql"],
        full_description=(
            "Buscamos un desarrollador backend con experiencia sólida en Python y Django "
            "para liderar el diseño de APIs REST escalables y arquitecturas orientadas a eventos."
        ),
    )
    assert job_filter.is_valid_it_job(valid_offer)

    # Oferta sin hard skills técnicas (ej. sólo ofimática descartada)
    no_skills_offer = JobOffer(
        job_title="Steuerberater",
        source_url="https://arbeitnow.com/tax",
        hard_skills=[],
        full_description=(
            "Wir suchen einen engagierten Steuerberater für die Betreuung "
            "mittelständischer Mandanten in steuerlichen Angelegenheiten mit exzellenten "
            "Kenntnissen."
        ),
    )
    assert not job_filter.is_valid_it_job(no_skills_offer)
