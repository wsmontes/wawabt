# Zenguinis CLI Overview

Zenguinis is the high-level orchestration layer that wires Backtrader engines (Mode A) and the news/sentiment pipelines (Mode B). Keep this cheat sheet handy before touching CLI code.

## Mode A – Backtest & Research CLI

Entry point: `bt_run.py`

```bash
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --fromdate 2024-01-01 --todate 2024-03-01 \
    --source yahoo_finance --interval 1d \
    --cash 10000 --commission 0.001 \
    --analyzer-preset performance
```

Key arguments:

| Flag | Description |
| --- | --- |
| `--strategy/-s` | Path to the strategy module. Must expose a `bt.Strategy` subclass. |
| `--symbols/-y` | One or more tickers/pairs. |
| `--fromdate/--todate` | ISO date filters; default = auto (1 year ago → today). |
| `--source` & `--interval` | Map directly to `AutoFetchData` engines. Always go DB → connector. |
| `--params` | Arbitrary key=value pairs forwarded to the strategy `params`. |
| `--sizer`, `--analyzer-preset`, `--drawdown`, `--plot` | Compose Backtrader components without editing the strategy file. |

Flow:
1. CLI parses arguments and builds a `Cerebro` instance via engines in `engines/bt_data.py`.
2. Data is pulled from DuckDB/Parquet first and only fetched externally as fallback.
3. Analyzers, observers, and sizers are attached per CLI options.
4. Results can be exported or saved to DuckDB (`--save-results`).

## Mode B – Pipeline Scheduler CLI

Entry point: `engines/pipeline_scheduler.py`

```bash
python engines/pipeline_scheduler.py --mock-pipelines --test \
    --fixtures-dir tests/fixtures/pipeline
```

Common flags:

| Flag | Description |
| --- | --- |
| `--test` | Run each pipeline once and exit (no background loop). |
| `--mock-pipelines` | Replace live engines with deterministic fixture-backed mocks. |
| `--fixtures-dir` | Directory containing parquet/duckdb fixtures for mock mode. |
| `--disable-*` | Disable individual jobs (news, sentiment, alerts, execution, performance). |

Flow:
1. CLI wires APScheduler jobs defined inside `PipelineScheduler`. Each job instantiates the respective engine on first run.
2. With `--mock-pipelines`, the scheduler imports `engines/mock_pipelines.py` instead of live engines, keeping runs fully offline.
3. Logs land in `logs/pipeline_YYYYMMDD.log`. When running live, follow `docs/RUNBOOK_PIPELINE.md` for supervision.

## Experiment Runner Outlook

Future experiment recipes should funnel through these same entry points:
- Mode A experiments = declarative config → `bt_run.py` (or `engines/cerebro_runner.py`).
- Mode B experiments = declarative config → `PipelineScheduler` or dedicated CLI wrappers that reuse the same engines.

When adding new commands:
1. Extend this doc with usage examples and link them from `README.md` and `AI_GUIDE.md`.
2. Expose functionality via CLI flags/recipes instead of bespoke scripts whenever possible.

## DuckDB/Parquet Health Check CLI

Entry point: `scripts/health_check.py`

```bash
python scripts/health_check.py --db-path data/market_data.duckdb --max-stale-hours 8
```

What it does:

1. Walks every storage root described in `engines/schema_contracts.py` and reports file counts / last-write timestamps.
2. Confirms the critical DuckDB tables exist (`realtime_alerts`, `paper_trades`, etc.) and dumps their column names.
3. Flags active alerts that are older than `--max-stale-hours` so you can detect hung producers.

Flags:

| Flag | Description |
| --- | --- |
| `--db-path` | Override the default DuckDB file from `config/database.json`. |
| `--max-stale-hours` | Threshold used when counting stale `realtime_alerts`. |
| `--json` | Emit a machine-readable JSON report for CI/monitoring hooks. |

Exit status is `0` when everything is healthy. Missing tables or stale alerts flip the exit code to `1` so you can wire the script into runbooks or CI smoke tests.
