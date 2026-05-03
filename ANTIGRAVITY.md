# 🤖 Antigravity / Agentic Directives

Este archivo define las reglas de oro, contexto arquitectónico y convenciones de código para que los agentes de IA (Antigravity, Claude Code, etc.) operen en el proyecto **DevAlign Scraper** de forma segura, eficiente y alineada con los objetivos de ingeniería.

---

## 🎯 1. Contexto del Proyecto

*   **Objetivo Principal:** Extraer datos estructurados de ofertas laborales IT para alimentar el **Motor de Alineación de Competencias (NLP/ML)** de DevAlign.
*   **Prioridad Absoluta:** Calidad de datos sobre cantidad. Preferimos descartar una oferta dudosa que ensuciar el dataset de entrenamiento.
*   **Fuentes Soportadas:** `pe.computrabajo.com` (Playwright + HTML) y `getonbrd.com` (API REST pública, sin browser).

---

## 🏗️ 2. Reglas Arquitectónicas (No Romper)

1.  **Patrón Strategy Multi-Portal (`src/base_parser.py`)**:
    *   Todos los parsers heredan de `BaseParser` e implementan `fetch_job_listings` y `fetch_and_parse_job`.
    *   El orquestador (`scripts/run_scraper.py`) trabaja **exclusivamente** con la interfaz `BaseParser`. Nunca llames métodos específicos del parser concreto desde `run_scraper.py`.
    *   La factory `_build_parser(site, categories)` es el único punto de creación de parsers.
    *   *Directiva IA:* Para agregar un nuevo portal, crea un archivo `src/{portal}_parser.py` con una clase que herede `BaseParser`. **Nunca** añadas lógica de portal en `run_scraper.py`.
2.  **GetOnBoard usa API REST, NO Playwright**:
    *   `GetOnBoardParser` usa `requests.Session` para llamar a `/api/v0/categories/{slug}/jobs`.
    *   El único GET adicional al HTML del detalle es para extraer nombres de tags (`a.gb-tags__item`).
    *   *Directiva IA:* **Nunca** añadas `page.goto()` o cualquier llamada a Playwright en `getonboard_parser.py`.
3.  **Filtrado en Dos Capas (`src/job_filter.py`)**:
    *   **Pre-filtro (Rápido):** Evalúa el título y la URL en la página de listado.
    *   **Post-filtro (Profundo):** Evalúa la oferta parseada (`hard_skills`, longitud de descripción).
    *   Para GetOnBoard, el pre-filtro de título aún aplica (verificación de seguridad), pero el filtro de URL no se usa.
    *   *Directiva IA:* Si necesitas agregar una nueva regla de exclusión, hazlo **siempre** en `JobFilter`.
4.  **Resiliencia y Estado (`src/session.py`)**:
    *   Nunca uses variables globales para el estado del scraping.
    *   Todo el estado, conteo de errores, y lógica de guardado vive en `SessionManager`.
    *   *Directiva IA:* Las interrupciones (`SIGINT`) deben ser manejadas limpiamente (`request_shutdown`).
5.  **Extracción de Datos (`src/parser.py`)**:
    *   La página de detalle de Computrabajo utiliza un sistema de "Prioridades" (Fallbacks).
    *   `JobOffer` es el schema compartido por **todos** los parsers; vive en `src/parser.py`.
    *   `JobParser` es un alias de `ComputrabajoParser` para compatibilidad.
6.  **Exportación (`src/supabase_exporter.py`)**:
    *   El exportador es **"tonto"**; solo hace Upsert. No realiza limpieza ni validación.

---

## 💻 3. Convenciones de Código (Code Style)

*   **Lenguaje:** Python 3.12+.
*   **Tipado:** Uso estricto de **Type Hints** (`list[str]`, `Path`, `bool`).
*   **Librerías Core:** `playwright` (Sync API), `BeautifulSoup4` (parser `lxml`), `tenacity` (reintentos).
*   **Inmutabilidad:** Preferimos dataclasses inmutables o retornos de nuevas instancias (como se ve en `cleaner.clean()`).
*   **Linter/Formatter:** El código debe cumplir con `black` y `flake8` (máximo 100 caracteres por línea).

---

## 🛠️ 4. Flujo de Trabajo y Comandos

*Directiva IA: Usa estos comandos para validar tu trabajo.*

*   **Ejecución de prueba — Computrabajo (Sin Supabase):**
    ```bash
    python scripts/run_scraper.py --jobs 5 --no-supabase --output data/test_run.json
    ```
*   **Ejecución de prueba — GetOnBoard (Sin Supabase):**
    ```bash
    python scripts/run_scraper.py --site getonboard --jobs 5 --no-supabase --output data/gob_test.json
    ```
*   **Con categorías específicas de GetOnBoard:**
    ```bash
    python scripts/run_scraper.py --site getonboard --categories programming mobile-developer --jobs 50
    ```
*   **Verificar Sintaxis y Estilo:**
    ```bash
    flake8 src/ scripts/ --max-line-length=100
    black src/ scripts/ tests/
    ```
*   **Correr Tests Unitarios:**
    ```bash
    pytest tests/ -v
    ```

---

## 🛡️ 5. Directivas Operativas Específicas para la IA

Cuando el usuario te pida realizar una tarea, asume por defecto lo siguiente:

1.  **Investigación antes de Acción:** Antes de proponer arreglar un selector CSS (`src/parser.py`), pide al usuario el HTML crudo de la página que falla o utiliza las herramientas de navegación para leer el DOM actual. No adivines selectores.
2.  **Modificaciones Atómicas:** Si te piden mejorar el pipeline de limpieza (`cleaner.py`), asegúrate de que tus expresiones regulares no eliminen términos del ecosistema IT en español (ej. no romper palabras con tildes).
3.  **Persistencia de Datos:** Bajo NINGUNA circunstancia modifiques un script de tal forma que se sobreescriban los archivos en `data/checkpoints/` o `data/raw/` sin confirmación explícita del usuario.
4.  **Auto-Corrección:** Si una ejecución falla por un timeout de red o ban temporal, no modifiques la lógica central; ajusta la configuración de `tenacity` (reintentos) o el `time.sleep()` anti-ban.
5.  **Mantenimiento de Documentación:** Siempre que implementes una nueva funcionalidad, cambies la arquitectura o modifiques los parámetros de un script, actualiza el `README.md` para reflejar el estado actual del proyecto. La sincronización entre código y documentación es obligatoria.
