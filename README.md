# 🕷️ DevAlign Scraper

> Recolecta ofertas laborales de portales de empleo para alimentar el **Motor de Alineación de Competencias** de DevAlign.

[![Lint](https://github.com/devalign/devalign-scraping/actions/workflows/lint.yml/badge.svg)](https://github.com/devalign/devalign-scraping/actions/workflows/lint.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 📋 Descripción

Este proyecto extrae datos estructurados de ofertas laborales desde **Computrabajo.com.pe** usando Playwright (para renderizado JS) y BeautifulSoup (para parseo HTML). Los datos se limpian y exportan en formato CSV, listos para ser consumidos por modelos de IA y Sentence Transformers.

### Variables Extraídas

| Campo | Descripción |
|-------|-------------|
| `job_title` | Título del puesto |
| `company` | Empresa |
| `location` | Ubicación |
| `hard_skills` | Competencias técnicas (delimitadas por `\|`) |
| `soft_skills` | Habilidades blandas (delimitadas por `\|`) |
| `experience_years` | Años de experiencia requeridos |
| `education_level` | Nivel formativo mínimo |
| `full_description` | Descripción íntegra de la vacante |
| `source_url` | URL de origen |
| `scraped_at` | Timestamp ISO de extracción |

---

## 🚀 Setup

### Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes recomendado)

### Instalación

```bash
# Clonar el repositorio
git clone https://github.com/devalign/devalign-scraping.git
cd devalign-scraping

# Crear entorno virtual e instalar dependencias
uv venv
uv pip install -r requirements.txt

# Instalar el browser de Playwright
playwright install chromium

# Configurar variables de entorno
cp .env.example .env
```

---

## ⚡ Uso

```bash
# Ejecución por defecto (100 ofertas)
python scripts/run_scraper.py

# Personalizar cantidad y salida
python scripts/run_scraper.py --jobs 50 --output data/processed/custom.csv

# Modo visible (debug)
python scripts/run_scraper.py --jobs 10 --no-headless
```

---

## 🧪 Desarrollo

```bash
# Instalar dependencias de desarrollo
uv pip install -r requirements-dev.txt

# Ejecutar tests
pytest tests/ -v

# Lint
flake8 src/ scripts/ --max-line-length=100

# Formateo
black src/ scripts/ tests/
```

---

## 📁 Estructura del Proyecto

```
devalign-scraping/
├── .github/workflows/lint.yml   # CI: flake8 en cada push
├── data/
│   ├── raw/                     # CSVs sin procesar (gitignored)
│   └── processed/               # CSVs limpios listos para ML
├── src/
│   ├── browser.py               # Configuración de Playwright
│   ├── parser.py                # Extracción con BeautifulSoup
│   ├── cleaner.py               # Pipeline de limpieza de texto
│   └── exporter.py              # Escritura del CSV con pandas
├── scripts/
│   └── run_scraper.py           # Entry point principal
├── tests/
│   ├── test_parser.py
│   └── test_cleaner.py
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```

---

## ⚖️ Ética y Legalidad

Antes de ejecutar el scraper, revisa:
- El archivo `robots.txt` del portal target
- Los Términos de Servicio del sitio

El script incluye delays aleatorios (2.5–5s) entre requests para simular comportamiento humano y respetar la infraestructura del portal.

---

## 📄 Licencia

MIT © [DevAlign](https://github.com/devalign)
