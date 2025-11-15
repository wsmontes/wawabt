# AI Task Recipes

Fast, repeatable playbooks for the most common requests. Use them to structure your plan before touching code.

## 0. Pick the Operating Mode

Before following any recipe, confirm whether the request touches **Mode A (Backtest & Research)** or **Mode B (News/Sentiment Pipeline)**:

- Mode A → ensure `make install-core` (or `pip install -r requirements-core.txt`) has been run.
- Mode B → ensure Mode A deps are present, then run `make install-pipeline` and rely on `tests/fixtures/pipeline/`.

Call out the mode explicitly in your plan/summary so reviewers know which product surface you touched. Then pick the relevant command from the verification matrix in `README.md` (section "✅ Verification Matrix") and skim `docs/ZENGUINIS_CLI.md` for the exact flags (including the DuckDB health check helper).

## 1. Add a New Market Data Source

1. **Read** `docs/README_ENGINES.md` (Connector section) and `config/connector.json`.
2. **Implement** source-specific helpers inside `engines/connector.py` (follow existing method signatures).
3. **Wire up** CLI entry points in `if __name__ == "__main__"` or via argparse subcommands.
4. **Add config knobs** to `config/connector.json` plus validation in `engines/connector.py`.
5. **Test** with:
   ```bash
   make lint
   python -m engines.connector list-sources
   python -m engines.connector <new-source> --help
   ```
6. **Document** summary in `docs/README_ENGINES.md` under the Connector section when the feature is complete.

## 2. Create or Modify a Strategy

1. **Reference** `strategies/template.py` and `docs/BACKTRADER_INTEGRATION.md`.
2. **Place** the new strategy in `strategies/` with a descriptive name and module-level docstring.
3. **Expose parameters** via `params = (...)` and log key events (`printlog` or `logger`).
4. **Add a smoke test** under `tests/strategies/test_<name>.py` using sample data or fixtures.
5. **Verify**:
   ```bash
   make smoke          # runs offline sample strategy + CLI checks
   python bt_run.py --strategy strategies/<name>.py --symbols AAPL --fromdate 2024-01-01 --todate 2024-03-01
   ```

## 3. Extend Sentiment / News Analytics

1. **Inspect** `scripts/sentiment_champion_strategy.py`, `data/analysis/` inputs, and DuckDB schemas via `engines/database.py`.
2. **Add features** in helper methods (`create_sentiment_score`, `generate_trading_signals`, etc.) while keeping transformations composable.
3. **Persist outputs** under `results/analysis/` or `data/analysis/` using `Path.mkdir(parents=True, exist_ok=True)`.
4. **Validate** with a dry run:
   ```bash
   make smoke-fast
   python scripts/sentiment_champion_strategy.py
   ```
5. **Optional**: update `docs/NEWS_PIPELINE_PLAN.md` if new pipeline stages are introduced.

## 4. Update Configurations Safely

1. **Edit** only the relevant JSON file inside `config/` (e.g., `connector.json`, `datasets.json`).
2. **Keep placeholders** for secrets—use environment variables or `.env` lookups in code.
3. **Synchronize** any schema changes with validation code (e.g., `engines/datasets.py`).
4. **Run**:
   ```bash
   python -m json.tool config/connector.json >/dev/null
   python engines/pipeline_scheduler.py --dry-run
   ```

## 5. Add Reusable Tests

1. **Determine scope** (engine, strategy, connector) and pick/create a module under `tests/`.
2. **Use fixtures** in `tests/fixtures/` (start with `sample_market_data.csv`) or add new lightweight parquet/CSV samples (<10 KB).
3. **Prefer pytest** style tests (follow existing convention once added) and avoid network calls.
4. **Execute**:
   ```bash
   make test          # deterministic fixture test
   pytest tests/<target_folder>
   ```

## 6. Run Pipeline Scheduler Offline

1. **Generate fixtures** (already committed under `tests/fixtures/pipeline/`). Add more rows as needed via pandas scripts.
2. **Use mock mode** to avoid hitting live connectors:
   ```bash
   python engines/pipeline_scheduler.py --mock-pipelines --test \
       --fixtures-dir tests/fixtures/pipeline
   ```
3. **Extend mock data** by editing `engines/mock_pipelines.py` or adding parquet/duckdb files in the fixtures folder.
4. **When switching back to real pipelines**, remove `--mock-pipelines` and ensure credentials/configs are loaded.

## 7. DuckDB / Parquet Health Check

Use this when pipelines stall, when CI needs to validate fixtures, or before kicking off Mode B deployments.

1. **Read** `docs/ZENGUINIS_CLI.md` (health check section) to understand the outputs.
2. **Run**:
   ```bash
   python scripts/health_check.py --db-path data/market_data.duckdb --json
   ```
3. **Interpret** the JSON for:
   - Missing DuckDB tables (`status != ok`).
   - Parquet folders with zero files.
   - `stale_active > 0` alerts (indicates hung writers).
4. **Document follow-ups** in your summary (e.g., "missing news_by_symbol" → add fixture or run ingestion).

Keep this file updated as new workflows emerge. Each recipe should list the relevant docs, files, and verification commands so AI assistants can act with confidence.
