# AI Assistant Guide

This guide condenses the must-know rules for any AI pair programming agent working on **WawaBackTrader**. Read it before writing code, and keep a tab open while you work.

## Pick a Track Before You Code

WawaBackTrader ships two products in one repo. Always state which mode you're working on:

| Mode | Scope | Install baseline | Default checks |
| --- | --- | --- | --- |
| **Mode A – Backtest & Research** | `bt_run.py`, smart DB, market connectors | `make install-core` or `pip install -r requirements-core.txt` | `make smoke`, `make test` |
| **Mode B – News/Sentiment Pipeline** | APScheduler pipelines, news collector, FinBERT helpers | Mode A + `make install-pipeline` | `python engines/pipeline_scheduler.py --mock-pipelines --test --fixtures-dir tests/fixtures/pipeline` |

Contributors can layer tools with `make install-dev` (pytest, etc.). Mention the chosen mode in your summary so reviewers know which surface area changed.

## Core Rules (from `.github/copilot-instructions.md`)

1. **Leia a documentação antes de tomar decisões** – Always consult the relevant doc listed in [Workspace Organization](WORKSPACE_ORGANIZATION.md) before modifying code.
2. **Confie nos padrões do Backtrader** – When unsure, follow upstream Backtrader conventions. Keep changes minimal when touching `backtrader/`.
3. **Use the engines architecture** – New integrations or data flows belong in `engines/` instead of ad-hoc scripts.
4. **Cada arquivo tem seu módulo** – Respect folder boundaries (feeds, indicators, configs, etc.).
5. **Pergunte quando não souber** – If context is missing, surface assumptions explicitly in your summary.
6. **Documente apenas ao final de uma etapa** – Create/extend documentation only when closing out a cohesive milestone (like this AI enablement effort).
7. **Testes devem ser reutilizáveis** – Prefer deterministic fixtures and reusable tests under `tests/`.

## How to Get Oriented Quickly

1. Skim `WORKSPACE_ORGANIZATION.md` for the authoritative folder map.
2. Open the doc that matches your task:
   - Engines/data pipelines → `docs/README_ENGINES.md`
   - Storage rules → `docs/DATA_ARCHITECTURE.md`
   - Schema contract reference → `docs/DATA_SCHEMA.md`
   - Strategy runner usage → `docs/BACKTRADER_INTEGRATION.md`
   - Zenguinis CLI overview + health checks → `docs/ZENGUINIS_CLI.md`
   - Pipeline runbook / ops → `docs/RUNBOOK_PIPELINE.md`
3. Inspect the target file’s module-level docstring or README for local conventions.
4. List recent instructions (`git log -1`, PR template, issue text) to confirm scope.

## Editing Checklist for AI Assistants

- [ ] Clarify assumptions in the response before coding if requirements are ambiguous.
- [ ] Avoid editing `backtrader/` unless the change is impossible elsewhere. If you must, add `# WawaBackTrader customization` above the diff.
- [ ] Keep configs (`config/*.json`) as the single source for runtime settings—don’t hardcode keys or endpoints.
- [ ] When adding files, follow existing naming conventions (snake_case for Python, UPPERCASE for docs referencing reports, etc.).
- [ ] Write or update reusable tests in `tests/` (or leverage fixtures) whenever functionality changes.
- [ ] Run at least one relevant verification command (see below) if the change touches runnable code.

## Quick Verification Commands

These commands are safe defaults for validation. Use them or extend as needed.

```bash
# Preferred: use Makefile targets
make lint              # compileall on engines + scripts
make test              # deterministic fixture-based unit suite
make smoke             # compile + sample SMA strategy + bt_run CLI + pipeline mock (if deps present)
make install-core      # install Mode A deps (idempotent)
make install-pipeline  # layer Mode B deps (idempotent)
make install-dev       # add pytest + tooling

# Manual equivalents
source venv/bin/activate
python -m compileall backtrader engines scripts
python tools/smoke_check.py --skip-strategy   # when time-constrained
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL --fromdate 2024-01-01 --todate 2024-03-01 --plot 0
python scripts/health_check.py --json        # DuckDB + parquet sanity report
python scripts/sentiment_champion_strategy.py --help
python engines/pipeline_scheduler.py --mock-pipelines --test
```

> If a command requires data that is not available in CI, document the assumption and point to fixtures under `tests/fixtures/` or describe how to seed them.

## Common Danger Zones

- **Large data files**: Never commit changes under `data/`, `results/`, `logs/`, or `temp/`.
- **Secrets**: API keys live in `config/*.json` placeholders. Do not paste real credentials into code or docs.
- **Overwriting reports**: Reports under `archive/` track history. Copy / suffix with dates instead of replacing in-place.
- **Mixed languages**: Comments and logs may switch between Portuguese and English. Preserve the tone/style already used in a file.

## When to Update This Guide

Update `AI_GUIDE.md` whenever:
- A new subsystem or convention is introduced.
- Instructions in `.github/copilot-instructions.md` change.
- Validation commands or tooling evolves (add `make` targets, new linters, etc.).

Keeping this guide accurate is the fastest way to help future AI collaborators stay productive.
