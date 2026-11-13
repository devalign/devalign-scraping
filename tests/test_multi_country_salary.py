"""
Tests para verificar el soporte multi-país de Computrabajo (salarios y descarte de ciudades).
"""

from src.parser import ComputrabajoParser


def test_computrabajo_peru_salary():
    parser = ComputrabajoParser(country="pe")
    html = """
    <html><body>
    <h1>Desarrollador Python</h1>
    <span class="tag">S/ 4,500</span>
    <div div-link="oferta">Requisitos: Python, Docker. 3 años de experiencia.</div>
    </body></html>
    """
    offer = parser.parse_job_detail(html, "https://pe.computrabajo.com/oferta-1")
    assert "S/ 4,500" in offer.salary or "4,500" in offer.salary


def test_computrabajo_colombia_salary():
    parser = ComputrabajoParser(country="co")
    html = """
    <html><body>
    <h1>Ingeniero de Software</h1>
    <span class="tag">$ 5.500.000 COP</span>
    <div div-link="oferta">Desarrollador backend en Python.</div>
    </body></html>
    """
    offer = parser.parse_job_detail(html, "https://co.computrabajo.com/oferta-2")
    assert "5.500.000" in offer.salary


def test_computrabajo_mexico_salary():
    parser = ComputrabajoParser(country="mx")
    html = """
    <html><body>
    <h1>Fullstack Developer</h1>
    <p>Salario ofrecido: $ 45,000 - $ 60,000 MXN mensuales</p>
    <div div-link="oferta">Desarrollo en React y Node.</div>
    </body></html>
    """
    offer = parser.parse_job_detail(html, "https://mx.computrabajo.com/oferta-3")
    assert "45,000" in offer.salary


def test_computrabajo_chile_salary():
    parser = ComputrabajoParser(country="cl")
    html = """
    <html><body>
    <h1>DevOps Engineer</h1>
    <span class="tag">$ 1.800.000 CLP</span>
    <div div-link="oferta">Kubernetes, Terraform y AWS.</div>
    </body></html>
    """
    offer = parser.parse_job_detail(html, "https://cl.computrabajo.com/oferta-4")
    assert "1.800.000" in offer.salary


def test_location_exclusion_by_country():
    # En Colombia, 'Bogotá' no debe ser asignada como empresa si viene en OG title
    parser_co = ComputrabajoParser(country="co")
    html = """
    <html>
    <head><meta property="og:title" content="Trabajo de Desarrollador en Bogotá"></head>
    <body><h1>Desarrollador</h1><div div-link="oferta">Detalles</div></body>
    </html>
    """
    offer_co = parser_co.parse_job_detail(html, "https://co.computrabajo.com/oferta-5")
    assert offer_co.company != "Bogotá"
    assert offer_co.company != "bogota"
