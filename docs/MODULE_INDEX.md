# Module Index

> Quick lookup table for the most frequently touched modules/classes. Use this when you need to locate code without scanning the entire tree.

## Core Entry Points

| Module | Highlights | When to Touch |
| --- | --- | --- |
| `bt_run.py` | CLI wrapper over `CerebroRunner`. Loads strategies dynamically, adds data feeds, analyzers, observers, and exports results. | Command-line improvements, new CLI flags, or orchestration tweaks. |
| `engines/cerebro_runner.py` | Encapsulates Cerebro configuration (cash, commission, analyzers, observers, sizers). | Modify backtesting defaults, add new analyzer/sizer presets. |
| `engines/bt_data.py` (`AutoFetchData`) | Smart data feed creation with DB + connector integration, timezone/session handling, resample/replay metadata. | Changes to how data is loaded/prepared before entering Backtrader. |
| `engines/connector.py` | Market data aggregator (Yahoo, CCXT, Binance, Alpaca, etc.) with CLI support. | Add new sources/endpoints, improve rate limiting, extend CLI. |
| `engines/smart_db.py` | DuckDB/Parquet smart storage: partitioning, dedupe, query helpers, retention cleanup. | Any change to data persistence or schema enforcement. |
| `scripts/sentiment_champion_strategy.py` | Comprehensive sentiment → strategy pipeline (feature engineering, signals, backtest, outputs). | Extend news/sentiment analytics or ML-ready exports. |

## Backtrader Extensions

| Module | Highlights |
| --- | --- |
| `backtrader/engines/__init__.py` | Re-export of custom helpers. Keep consistent with upstream layout. |
| `backtrader/analyzer.py`, `backtrader/trade.py`, etc. | Mostly upstream with selective patches. Look for `# WawaBackTrader customization` markers. |
| `backtrader/feeds/`, `backtrader/indicators/`, `backtrader/stores/` | Mirror of upstream modules. Prefer extending via `engines/` or custom strategies unless you need core changes. |

## Engines & Helpers

| Module | Purpose | Key Classes/Functions |
| --- | --- | --- |
| `engines/analyzer_helper.py` | Aggregates analyzer outputs and saves to disk/DB. | `AnalyzerHelper` |
| `engines/commission_helper.py` | Commission presets & helpers for multiple markets. | `CommissionHelper`, `setup_commission` |
| `engines/analyzer_helper.py` | Converts analyzer data to dicts/JSON, orchestrates exports. | `AnalyzerHelper` |
| `engines/pipeline_scheduler.py` | Orchestrates periodic data/news ingestion (requires config + DB). | `PipelineScheduler` (main class/function) |
| `engines/datasets.py` | Kaggle, HF, Quandl, AlphaVantage, Polygon integration. CLI helpers for searching/downloading datasets. | `DatasetsEngine` |
| `engines/rss.py` | RSS/news ingestion with categories, dedupe, DB storage. | `RSSEngine` |

## Configuration & Data

| Path | Notes |
| --- | --- |
| `config/connector.json` | Source toggles, API credentials placeholders, CCXT/Binance/Alpaca settings. |
| `config/database.json` | Smart DB partitions, retention, dedupe settings. |
| `config/rss_sources.json`, `rss.json`, `rss_stocks.json` | Feed definitions grouped by category. |
| `tests/fixtures/` | Deterministic CSV/Parquet fixtures for offline tests (start with `sample_market_data.csv`). |
| `datas/` | Legacy sample datasets (Yahoo CSVs, ORCL series) used in smoke tests. |

## Testing & Tooling

| Path | Purpose |
| --- | --- |
| `tests/test_auto_fetch_prepare.py` | Fixture-based test for `AutoFetchData` prep logic. Template for new deterministic tests. |
| `tools/smoke_check.py` | Offline smoke harness (compile, sample SBA strategy, CLI check). |
| `Makefile` | Lint/test/smoke entry points (`make lint`, `make test`, `make smoke`, `make smoke-fast`). |

## How to Extend This Index

1. Keep sections alphabetized where practical.
2. Add new modules when they become common touchpoints (e.g., new engines, schedulers, or strategy suites).
3. Link back to source files using relative paths when referencing specific functions.
4. Update cross references in `WORKSPACE_ORGANIZATION.md` and `AI_GUIDE.md` if you add major sections here.
