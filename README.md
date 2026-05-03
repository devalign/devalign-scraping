# 🕷️ DevAlign Scraper

> Recolecta ofertas laborales de portales de empleo para alimentar el **Motor de Alineación de Competencias** de DevAlign.

[![Lint](https://github.com/devalign/devalign-scraping/actions/workflows/lint.yml/badge.svg)](https://github.com/devalign/devalign-scraping/actions/workflows/lint.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 📋 Descripción

Este proyecto extrae datos estructurados de ofertas laborales desde **Computrabajo.com.pe** usando Playwright y BeautifulSoup. 

**Características principales:**
- **Resiliencia:** Sistema de checkpoints cada 20 ofertas. Si el proceso se interrumpe, no se pierden los datos.
- **Auto-Resume:** Detecta automáticamente sesiones interrumpidas y ofrece continuar desde donde se dejó.
- **Filtro IT Inteligente:** Pre-filtrado por título/URL antes de navegar, ahorrando ~40% del tiempo de scraping al ignorar puestos no relacionados.
- **Exportación Robusta:** Upsert automático a **Supabase**, evitando duplicados y manteniendo la integridad de los datos para modelos de ML.

### Variables Extraídas

| Campo | Descripción |
|-------|-------------|
| `job_title` | Título del puesto |
| `company` | Empresa contratante |
| `location` | Ubicación geográfica |
| `salary` | Salario (limpio de metadatos irrelevantes) |
| `modality` | Modalidad de trabajo (Remoto, Presencial, Híbrido) |
| `date_posted` | Fecha de publicación |
| `hard_skills` | Competencias técnicas extraídas vía NLP (Formato `TEXT[]`) |
| `soft_skills` | Habilidades blandas extraídas (Formato `TEXT[]`) |
| `experience_years` | Años de experiencia requeridos |
| `education_level` | Nivel formativo mínimo |
| `full_description` | Descripción íntegra de la vacante (Limpiada de ruido UI) |
| `source_url` | URL de origen (Clave Única) |
| `scraped_at` | Timestamp ISO de extracción |

---

## 🚀 Setup

### Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (gestor de paquetes recomendado)
- Cuenta en [Supabase](https://supabase.com)

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

# Configurar variables de entorno (Añadir SUPABASE_URL y SUPABASE_KEY)
cp .env.example .env
```

---

## ⚡ Uso

```bash
# Ejecución por defecto (Detección de checkpoints automática)
python scripts/run_scraper.py --jobs 300

# Prueba local (Exporta a JSON sin tocar Supabase)
python scripts/run_scraper.py --jobs 5 --no-supabase --output data/test_run.json

# Modo visible (debug)
python scripts/run_scraper.py --jobs 10 --no-headless
```

> [!TIP]
> Si el scraper se detiene con **Ctrl+C**, se guardará el progreso actual. Al reiniciarlo, el script te preguntará si deseas retomar la sesión anterior.

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
├── data/
│   ├── checkpoints/             # Sesiones interrumpidas (auto-limpieza)
│   └── test_run.json            # Resultados locales
├── src/
│   ├── browser.py               # Ciclo de vida de Playwright
│   ├── parser.py                # Extracción con BeautifulSoup y Regex
│   ├── cleaner.py               # Pipeline de limpieza NLP
│   ├── job_filter.py            # Pre/Post filtrado de calidad IT
│   ├── session.py               # Orquestación de persistencia y checkpoints
│   └── supabase_exporter.py     # Cliente Supabase (Upsert)
├── scripts/
│   └── run_scraper.py           # Entry point con Graceful Shutdown
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
