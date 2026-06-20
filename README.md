# 🕷️ Devalign Scraper

> Recolecta ofertas laborales de portales de empleo (Computrabajo) para alimentar el **Motor de Agrupamiento y Clustering** de Devalign.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](#)
![License](https://img.shields.io/badge/license-MIT-green.svg)

---

## 📋 Descripción

Este módulo extrae datos estructurados de ofertas laborales desde **Computrabajo.com.pe** utilizando Playwright (para el renderizado de Javascript y evasión de bloqueos básicos) y BeautifulSoup (para el parseo eficiente del HTML).

Los datos extraídos se consolidan, limpian y exportan en archivos CSV que sirven como entrada para los procesos de entrenamiento UMAP/HDBSCAN y el sembrado de la base de datos central de habilidades.

### Variables Extraídas (Especificaciones del Dataset CSV)

El archivo CSV de salida cuenta con la siguiente estructura de columnas:

| Columna | Tipo | Descripción |
| :--- | :--- | :--- |
| `job_title` | `VARCHAR` | Título oficial de la oferta de trabajo |
| `company` | `VARCHAR` | Nombre de la empresa ofertante |
| `location` | `VARCHAR` | Ubicación geográfica en Perú (ej: Lima) |
| `hard_skills` | `VARCHAR` | Habilidades duras extraídas y normalizadas, delimitadas por `\|` |
| `soft_skills` | `VARCHAR` | Habilidades blandas extraídas, delimitadas por `\|` |
| `experience_years` | `INTEGER` | Años mínimos de experiencia requeridos (estimado) |
| `education_level` | `VARCHAR` | Nivel mínimo educativo (técnico, universitario, etc.) |
| `full_description` | `TEXT` | Texto íntegro de la descripción del puesto |
| `source_url` | `VARCHAR` | Enlace de origen hacia la vacante |
| `scraped_at` | `TIMESTAMP` | Timestamp ISO de extracción de la información |

---

## 🚀 Setup

### Requisitos
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Gestor de paquetes de Python de alta velocidad)

### Instalación

```bash
# Crear entorno virtual e instalar dependencias
uv venv
uv pip install -r requirements.txt

# Instalar navegadores para Playwright
playwright install chromium

# Configurar entorno
cp .env.example .env
```

---

## ⚡ Uso e Ingesta Offline (Proceso de Sembrado)

### 1. Ejecución del Scraper
Para iniciar el proceso de extracción de datos laborales localmente:

```bash
# Extraer 100 ofertas laborales (por defecto)
python scripts/run_scraper.py

# Personalizar cantidad y destino
python scripts/run_scraper.py --jobs 200 --output data/processed/computrabajo_vacancies.csv
```

### 2. Proceso de Ingesta Offline (Backend Seed)
Una vez generado el dataset en formato CSV, para alimentar la base de datos de producción de `devalign-api`:

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
│   ├── raw/                     # Datos en bruto temporales
│   └── processed/               # CSVs limpios consolidados listos para ingesta
├── src/
│   ├── browser.py               # Lógica de sesión con Playwright Chromium
│   ├── parser.py                # Parseo y extracción de selectores HTML con BeautifulSoup
│   ├── cleaner.py               # Limpieza y filtrado básico de texto de la oferta
│   └── exporter.py              # Exportador a estructura tabular (Pandas/CSV)
├── scripts/
│   └── run_scraper.py           # Script ejecutable principal
├── tests/                       # Suite de pruebas unitarias
└── requirements.txt
```

---

## 🔗 Referencias a la Documentación Principal

El diseño del pipeline de datos y su rol en la arquitectura general de Devalign se detallan en el repositorio de documentación central:

- [🏗️ Arquitectura Técnica](../devalign-docs/ARCHITECTURE.md)
- [🎯 Alcance MVP](../devalign-docs/SCOPE.md)
- [🧠 Lógica Core e Inferencia](../devalign-docs/MODEL.md)
