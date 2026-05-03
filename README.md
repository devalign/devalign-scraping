# 🕷️ DevAlign Scraper

> Recolecta ofertas laborales de portales de empleo para alimentar el **Motor de Alineación de Competencias** de DevAlign.

[![Lint](https://github.com/devalign/devalign-scraping/actions/workflows/lint.yml/badge.svg)](https://github.com/devalign/devalign-scraping/actions/workflows/lint.yml)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 📋 Descripción

Este proyecto extrae datos estructurados de ofertas laborales desde múltiples portales de empleo usando el **Patrón Strategy** para mantener el código modular y escalable.

**Portales soportados:**
| Portal | Estrategia | Auth |
|---|---|---|
| **Computrabajo.com.pe** | Playwright + BeautifulSoup (HTML rendering) | No |
| **GetOnBoard.com** | API REST pública (`/api/v0/`) + requests | No |

**Características principales:**
- **Patrón Strategy:** Cada portal tiene su propio parser (`ComputrabajoParser`, `GetOnBoardParser`) con una interfaz común (`BaseParser`). Añadir un nuevo portal es simplemente crear un nuevo archivo en `src/`.
- **Resiliencia:** Sistema de checkpoints cada 20 ofertas. Si el proceso se interrumpe, no se pierden los datos.
- **Auto-Resume:** Detecta automáticamente sesiones interrumpidas y ofrece continuar desde donde se dejó.
- **Filtro IT Inteligente:** Pre-filtrado por título antes de fetchear detalles, ahorrando tiempo y requests.
- **Exportación Robusta:** Upsert automático a **Supabase**, evitando duplicados.

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
# Computrabajo — ejecución por defecto
python scripts/run_scraper.py --jobs 300

# GetOnBoard — con categorías por defecto (programming, mobile, sysadmin)
python scripts/run_scraper.py --site getonboard --jobs 100

# GetOnBoard — con categorías específicas
python scripts/run_scraper.py --site getonboard --categories programming mobile-developer --jobs 50

# Prueba local (Exporta a JSON sin tocar Supabase)
python scripts/run_scraper.py --jobs 5 --no-supabase --output data/test_run.json
python scripts/run_scraper.py --site getonboard --jobs 5 --no-supabase --output data/gob_test.json

# Modo visible (debug, solo Computrabajo)
python scripts/run_scraper.py --jobs 10 --no-headless
```

### Argumentos CLI

| Argumento | Default | Descripción |
|---|---|---|
| `--site` | `computrabajo` | Portal: `computrabajo` \| `getonboard` |
| `--jobs` | `100` | Número de ofertas IT válidas a recolectar |
| `--categories` | *(ver abajo)* | [GOB] Categorías a scrapear (espacio-separadas) |
| `--url` | *(por portal)* | Override manual de URL base |
| `--no-headless` | `False` | Browser visible (solo Computrabajo) |
| `--no-supabase` | `False` | Solo guardar localmente |
| `--output` | `data/test_run.json` | Ruta del archivo de salida local |

**Categorías GetOnBoard por defecto:** `programming`, `mobile-developer`, `sysadmin-devops-qa`

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
│   ├── base_parser.py           # 🔑 Interfaz Strategy (BaseParser ABC)
│   ├── parser.py                # ComputrabajoParser + JobOffer dataclass
│   ├── getonboard_parser.py     # GetOnBoardParser (API REST, sin browser)
│   ├── browser.py               # Ciclo de vida de Playwright
│   ├── cleaner.py               # Pipeline de limpieza NLP
│   ├── job_filter.py            # Pre/Post filtrado de calidad IT
│   ├── session.py               # Orquestación de persistencia y checkpoints
│   └── supabase_exporter.py     # Cliente Supabase (Upsert)
├── scripts/
│   └── run_scraper.py           # Entry point multi-portal con Graceful Shutdown
├── tests/
│   ├── test_parser.py           # Tests ComputrabajoParser
│   ├── test_cleaner.py          # Tests TextCleaner
│   └── test_getonboard_parser.py # Tests GetOnBoardParser (26 tests)
├── ANTIGRAVITY.md            # Directivas para agentes de IA
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```

---

## ⚖️ Ética y Legalidad

Antes de ejecutar el scraper, revisa:
- El archivo `robots.txt` del portal target
- Los Términos de Servicio del sitio

El script incluye delays aleatorios entre requests para respetar la infraestructura del portal:
- **Computrabajo:** 2.5–5s (browser headless, más agresivo)
- **GetOnBoard:** 0.5–1.5s (API pública, más liviano)

---

## 📄 Licencia

MIT © [DevAlign](https://github.com/devalign)
