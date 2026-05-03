# 🤖 Antigravity / Agentic Directives

Este archivo define las reglas de oro, contexto arquitectónico y convenciones de código para que los agentes de IA (Antigravity, Claude Code, etc.) operen en el proyecto **DevAlign Scraper** de forma segura, eficiente y alineada con los objetivos de ingeniería.

---

## 🎯 1. Contexto del Proyecto

*   **Objetivo Principal:** Extraer datos estructurados de ofertas laborales IT para alimentar el **Motor de Alineación de Competencias (NLP/ML)** de DevAlign.
*   **Prioridad Absoluta:** Calidad de datos sobre cantidad. Preferimos descartar una oferta dudosa que ensuciar el dataset de entrenamiento.
*   **Fuente Principal:** `pe.computrabajo.com` (actualmente enfocado en "trabajo de desarrollador").

---

## 🏗️ 2. Reglas Arquitectónicas (No Romper)

1.  **Filtrado en Dos Capas (`src/job_filter.py`)**:
    *   **Pre-filtro (Rápido):** Evalúa el título y la URL en la página de listado para evitar navegar a ofertas no-IT (vendedores, operarios, etc.). Ahorra un 40% de tiempo.
    *   **Post-filtro (Profundo):** Evalúa la oferta parseada (`hard_skills`, longitud de descripción).
    *   *Directiva IA:* Si necesitas agregar una nueva regla de exclusión, hazlo **siempre** en `JobFilter`.
2.  **Resiliencia y Estado (`src/session.py`)**:
    *   Nunca uses variables globales para el estado del scraping.
    *   Todo el estado, conteo de errores, y lógica de guardado vive en `SessionManager`.
    *   *Directiva IA:* Las interrupciones (`SIGINT`) deben ser manejadas limpiamente (`request_shutdown`). Nunca modifiques el flujo principal para hacer un `sys.exit()` abrupto.
3.  **Extracción de Datos (`src/parser.py`)**:
    *   La página de detalle utiliza un sistema de "Prioridades" (Fallbacks) para extraer campos como Empresa y Ubicación (e.g., JSON-LD > Sidebar > H1).
    *   *Directiva IA:* Si falla un selector CSS, **no elimines el fallback anterior**, añade uno nuevo o ajusta la jerarquía.
4.  **Exportación (`src/supabase_exporter.py`)**:
    *   El exportador es **"tonto"**; solo hace Upsert. No realiza limpieza ni validación (eso ocurre antes).

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

*   **Ejecución de prueba (Segura, no toca la BD de producción):**
    ```bash
    python scripts/run_scraper.py --jobs 5 --no-supabase --output data/test_run.json
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
