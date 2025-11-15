# WawaBackTrader Workspace Organization

> This document is the single source of truth for "where things live" and how to navigate the project. Keep it updated whenever folders move or responsibilities change.

## Top-Level Map

| Area | Purpose | Primary Owners / Notes |
| --- | --- | --- |
| `backtrader/` | Fork of upstream Backtrader. Only touch when the original behavior needs patching. Document every divergence with `# WawaBackTrader customization` comments. | Core framework maintainers |
| `engines/` | Smart data + orchestration engines (`connector`, `bt_data`, `datasets`, `rss`, `smart_db`, etc.). **Preferred place** for new integrations. | Data platform team |
| `strategies/` | Production-ready Backtrader strategies. Keep each strategy self-contained plus docstring with params. | Quant team |
| `scripts/` | One-off analyses, studies, or batch jobs (e.g., `sentiment_champion_strategy.py`). Prefix experimental scripts with a comment explaining required datasets. | Research/ML |
| `config/` | JSON configs for connectors, datasets, rss, database, commissions, etc. Never hardcode credentials in code—reference these files. | Platform |
| `data/` | Generated DuckDB + parquet outputs. Treat as artifacts; do not commit new data files. | Auto-generated |
| `docs/` | Formal documentation (architecture, engines, pipelines). Cross-link from `README.md` and the AI guide. | Everyone |
| `tests/` | Shared fixtures and reusable tests. Add end-to-end coverage for new engines or strategies here. | All contributors |
| `tools/`, `scripts/`, `contrib/`, `examples/`, etc. | Utilities, samples, and helper assets. Review README inside each folder for details. | Mixed |

## Operating Modes at a Glance

| Mode | Scope | Install command | Default verification |
| --- | --- | --- | --- |
| **Mode A – Backtest & Research** | `bt_run.py`, smart DB, connectors, strategies | `make install-core` (`pip install -r requirements-core.txt`) | `make smoke`, `make test` |
| **Mode B – News & Sentiment Pipeline** | APScheduler scheduler, news collectors, alerting, FinBERT helpers | `make install-pipeline` (after Mode A) | `python engines/pipeline_scheduler.py --mock-pipelines --test --fixtures-dir tests/fixtures/pipeline` |

Use Mode A for research/backtesting tasks, Mode B for 24/7 ingestion/signal work. Contributors can run `make install-dev` for pytest/tooling.

## Editing Guidelines

1. **Prefer engines over core**: If you need a new data source or workflow, implement it inside `engines/` and expose hooks to Backtrader via existing adapters instead of modifying `backtrader/` internals.
2. **Annotate custom Backtrader code**: When you must edit `backtrader/`, add a header comment explaining why and keep the change minimal. This helps future merges from upstream.
3. **One file type per folder**: Follow the convention (feeds in `backtrader/feeds/`, analyzers in `backtrader/analyzers/`, configs in `config/`, etc.). Do not drop files into the repo root unless they are entry points.
4. **Document stage completions**: New documentation is only required when finishing a cohesive stage (feature, subsystem, or workflow). Update this file and `AI_GUIDE.md` as part of those stages.
5. **Data artifacts stay out of Git**: Use `data/`, `results/`, `logs/`, and `temp/` locally. If you need deterministic fixtures, add them under `tests/fixtures/` instead.

## Entry Points & Pipelines

| Entry | Description | Typical Invocation |
| --- | --- | --- |
| `bt_run.py` | Main CLI runner for Backtrader strategies with smart data loading. | `python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL` |
| `engines/cerebro_runner.py` | Programmatic runner for Cerebro pipelines. Use when orchestrating from Python. | Called inside services/scripts |
| `scripts/*.py` | Standalone analytics or batch jobs (e.g., sentiment analysis). Inspect docstring before running. | `python scripts/sentiment_champion_strategy.py` |
| `scripts/health_check.py` | DuckDB + parquet health report (schema coverage + stale alerts). | `python scripts/health_check.py --json` |
| `engines/pipeline_scheduler.py` | Orchestrates periodic data/news ingestion. Requires configured DuckDB + configs. | `python engines/pipeline_scheduler.py` |

## Documentation Map

| Topic | Location |
| --- | --- |
| High-level overview & quick start | `README.md` |
| Engines deep dive | `docs/README_ENGINES.md` |
| Data architecture & storage rules | `docs/DATA_ARCHITECTURE.md` |
| Table/column contracts | `docs/DATA_SCHEMA.md` + `engines/schema_contracts.py` |
| Backtesting usage guide | `docs/BACKTRADER_INTEGRATION.md` |
| Zenguinis CLI + health checks | `docs/ZENGUINIS_CLI.md` |
| Module lookup table | `docs/MODULE_INDEX.md` |
| Pipelines and automation | `docs/ENHANCED_BT_RUN.md`, `docs/NEWS_PIPELINE_PLAN.md` |
| Pipeline runbook / ops | `docs/RUNBOOK_PIPELINE.md` |
| AI-specific guidance | `AI_GUIDE.md` (new)

## Workflow Expectations

1. **Read the relevant doc** for the subsystem you touch (see map above).
2. **Update configs** via JSON in `config/`; never hardcode secrets.
3. **Add reusable tests** under `tests/`—each new engine or strategy should have at least a smoke test that can run offline using fixtures (start with `tests/fixtures/sample_market_data.csv`).
4. **Use the Makefile** for consistency: `make lint`, `make test`, `make smoke` (or call `tools/smoke_check.py` directly) before submitting changes.
5. **Log outputs** to `logs/` or `results/analysis/` via helper utilities instead of printing large payloads.
6. **Verify locally** using the commands listed in `AI_TASK_RECIPES.md`. Document any new command you rely on.

Keep this file short and actionable. If you reorganize the repo, update the tables immediately so both humans and AI assistants have an authoritative map.
