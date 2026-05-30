# Devalign Scraping Agent Notes

## Scope

Applies to the scraper in this folder. Start with:
- [README](README.md)
- [Agent directives](ANTIGRAVITY.md)

For work orchestration, follow the repo harness:
- [.harness overview](../.harness/HARNESS.md)

## Commands

- Run scraper: `python scripts/run_scraper.py`
- Tests: `pytest tests/ -v`
- Lint/format (dev): `flake8 src/ scripts/ --max-line-length=100`, `black src/ scripts/ tests/`

## Conventions

- Strategy pattern per portal parser in `src/`.
- Use checkpointing and resume logic; do not remove session safety guards.

## Workflow

- Do not use `PROGRESS.md` for tracking work status.
- Use .harness workflows, state, and handoffs for tracking and transitions.
