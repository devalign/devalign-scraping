# devalign-scraping — Agent Rules

Job offer collection pipeline targeting Peruvian/LATAM tech listings (`GetOnBoard` API and `Computrabajo` via Playwright + BeautifulSoup).

## Stack & Tooling

- **Runtime:** Python 3.12+ managed with `uv` / `.venv` (`requirements.txt`, `requirements-dev.txt`).
- **Key Dependencies:** Playwright (`chromium`), BeautifulSoup, Supabase client.

## Safe Local Execution & Testing

- Run tests inside `c:\Projects\Devalign\devalign-scraping` with `pytest`.
- When testing `scripts/run_scraper.py` locally, **always** pass `--no-supabase` and a small `--jobs` limit writing to an ignored output path, e.g.:
  `python scripts/run_scraper.py --jobs 5 --no-supabase --output data/test_run.json`
- Never ingest or mutate production Supabase tables from scraper scripts unless explicitly requested by the user.
- Respect `.pre-commit-config.yaml` and never commit `.env` files or large ad-hoc scraped dumps.
