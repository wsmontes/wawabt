# Pipeline Runbook

Operational guide for the APScheduler-driven news/sentiment pipeline (Mode B).

## 1. Prerequisites

1. Install dependencies: `make install-core && make install-pipeline`.
2. Configure credentials: `config/connector.json`, `config/rss_sources.json`, `config/datasets.json`.
3. Verify DuckDB write access to `data/market_data.duckdb`.

## 2. Start / Stop

| Action | Command |
| --- | --- |
| Dry run with fixtures | `python engines/pipeline_scheduler.py --mock-pipelines --test --fixtures-dir tests/fixtures/pipeline` |
| Start in foreground | `python engines/pipeline_scheduler.py` |
| Stop | Ctrl+C (SIGINT) or send SIGTERM to the process |

> In production, wrap the scheduler with a supervisor (systemd, pm2, Docker) so restarts are automatic.

## 3. Health Checks

1. **Scheduler heartbeat** – log file `logs/pipeline_YYYYMMDD.log` should contain recent `START/COMPLETE` lines for every job.
2. **DuckDB reachability** – run `python tools/db_inspector.py --summary` (expect non-empty counts) and `python tools/db_inspector.py --contract market_data` to validate schema drift.
3. **Pipeline smoke** – run `make smoke` (skips pipeline step if APScheduler missing) or the explicit mock command above before deployments.

## 4. Common Failure Modes

| Symptom | Likely Cause | Mitigation |
| --- | --- | --- |
| DuckDB "database is locked" | Long-running query or crashed writer kept connection open | Restart scheduler; run `python -m duckdb data/market_data.duckdb "PRAGMA database_list"` to confirm handle; keep only one writer process. |
| Burst of HTTP 5xx/429 | External API outage (Alpaca/Binance/RSS) | The new `run_with_retry` helper backs off automatically. If failures persist, set `--disable-*` flags to keep other jobs running. |
| FinBERT/sentiment errors | Missing model weights or torch CPU OOM | Pre-download models in setup scripts; lower batch sizes; monitor `logs/pipeline_*.log` for stack traces. |
| Scheduler stops silently | Unhandled exception bubbled up | Supervisor should restart; inspect latest log tail and run `python engines/pipeline_scheduler.py --mock-pipelines --test` after fix. |

## 5. Manual Retry / Backfill

1. Use `tools/db_inspector.py --contract news_data` to inspect expected columns before reprocessing.
2. To backfill news, run `python engines/news_collector_pipeline.py --hours 6` (implement CLI wrapper if needed) or use notebooks pointing to `NewsCollectorPipeline`.
3. For sentiment reprocessing, re-run `scripts/sentiment_champion_strategy.py` with the desired time window and ensure outputs land in `data/analysis/`.

## 6. On-Call Checklist

- [ ] Confirm scheduler process is alive (ps/top or supervisor status).
- [ ] Tail `logs/pipeline_YYYYMMDD.log` to ensure new lines arrive at least every 5 minutes.
- [ ] Run `python tools/db_inspector.py --summary` to ensure DuckDB is writable.
- [ ] If restarting, run the mock command once first; then start live mode.

Keep this runbook next to `docs/NEWS_PIPELINE_PLAN.md`. Update it whenever a new job type is added or when operational procedures change.
