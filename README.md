# 🕷️ Devalign Scraper

> Recolecta ofertas laborales de portales de empleo (Computrabajo) para alimentar el **Motor de Agrupamiento y Clustering** de Devalign.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](#)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 📋 Descripción

Este módulo extrae datos estructurados de ofertas laborales desde **Computrabajo.com.pe** utilizando Playwright (para el renderizado de Javascript y evasión de bloqueos básicos) y BeautifulSoup (para el parseo eficiente del HTML).

Los datos extraídos se consolidan, limpian y exportan en archivos CSV que sirven como entrada para los procesos de entrenamiento UMAP/HDBSCAN y el sembrado de la base de datos central de habilidades.

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
# Crear entorno virtual e instalar dependencias
uv venv
uv pip install -r requirements.txt

# Instalar navegadores para Playwright
playwright install chromium

# Configurar variables de entorno (Añadir SUPABASE_URL y SUPABASE_KEY)
cp .env.example .env
```

---

## ⚡ Uso e Ingesta Offline (Proceso de Sembrado)

### 1. Ejecución del Scraper
Para iniciar el proceso de extracción de datos laborales localmente:

```bash
# GetOnBoard — ejecución por defecto (API, más rápido)
python scripts/run_scraper.py --jobs 300

# Computrabajo — portal secundario (HTML, Playwright)
python scripts/run_scraper.py --site computrabajo --jobs 100

# Computrabajo — buscando múltiples palabras clave
python scripts/run_scraper.py --site computrabajo --keywords python react "node js" --jobs 150

# GetOnBoard — con categorías específicas
python scripts/run_scraper.py --site getonboard --categories programming mobile-developer --jobs 50

# Forzar parada temprana rápida (salta término tras 3 repetidos)
python scripts/run_scraper.py --site computrabajo --keywords angular java --max-duplicates 3 --jobs 80

# Prueba local (Exporta a JSON sin tocar Supabase)
python scripts/run_scraper.py --jobs 5 --no-supabase --output data/test_run.json
python scripts/run_scraper.py --site getonboard --jobs 5 --no-supabase --output data/gob_test.json

# Modo visible (debug, solo Computrabajo)
python scripts/run_scraper.py --jobs 10 --no-headless
```

### Argumentos CLI

| Argumento | Default | Descripción |
|---|---|---|
| `--site` | `getonboard` | Portal: `getonboard` \| `computrabajo` |
| `--jobs` | `100` | Número de ofertas IT válidas a recolectar |
| `--categories` | *(ver abajo)* | [GOB] Categorías a scrapear (espacio-separadas) |
| `--keywords` | `["desarrollador"]` | [Computrabajo] Palabras clave a buscar (espacio-separadas) |
| `--max-duplicates` | `10` | Límite de duplicados consecutivos antes de saltar término |
| `--url` | *(por portal)* | Override manual de URL base |
| `--no-headless` | `False` | Browser visible (solo Computrabajo) |
| `--no-supabase` | `False` | Solo guardar localmente |
| `--output` | `data/test_run.json` | Ruta del archivo de salida local |

**Categorías GetOnBoard por defecto:** `programming`, `mobile-developer`, `sysadmin-devops-qa`

> [!TIP]
> Si el scraper se detiene con **Ctrl+C**, se guardará el progreso actual. Al reiniciarlo, el script te preguntará si deseas retomar la sesión anterior.

---

## 🧪 Desarrollo

1. Mover o copiar el archivo CSV resultante a la carpeta de datos del backend: `c:\Projects\Devalign\devalign-api\data\raw\`.
2. Dirigirse al repositorio del backend (`devalign-api`) y ejecutar el script de sembrado:
   ```bash
   python scripts/seed_demo_data.py --csv data/raw/computrabajo_vacancies.csv
   ```
   *Este proceso normalizará semánticamente las habilidades importadas por lotes y recalculará la información de los clústeres.*

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

El diseño del pipeline de datos y su rol en la arquitectura general de Devalign se detallan en el repositorio de documentación central:

- [🏗️ Arquitectura Técnica](../devalign-docs/ARCHITECTURE.md)
- [🎯 Alcance MVP](../devalign-docs/SCOPE.md)
- [🧠 Lógica Core e Inferencia](../devalign-docs/MODEL.md)
- [📄 Documento de Requerimientos de Producto (PRD)](../devalign-docs/PRD.md)
- [📋 Product Backlog](../devalign-docs/PRODUCT_BACKLOG.md)
- [🏃 Sprint Backlog](../devalign-docs/SPRINT_BACKLOG.md)
