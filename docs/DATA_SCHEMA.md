# Data Schema Contracts

This document is the single source of truth for the DuckDB/Parquet tables managed by `SmartDatabaseManager`. Keep it in sync with `engines/schema_contracts.py` whenever columns change.

| Table | Description | Storage Pattern | Unique Key | Fixture |
| --- | --- | --- | --- | --- |
| `market_data` | OHLCV bars fetched via connectors or ingested CSVs. | `data/market/{source}/{symbol}/{interval}.parquet` | `symbol`, `timestamp`, `source`, `interval` | `tests/fixtures/sample_market_data.csv` |
| `news_data` | Normalized RSS/news articles. | `data/news/{source}/{year}/{month}.parquet` | `link`, `timestamp` | `tests/fixtures/pipeline/news_sample.parquet` |
| `analysis_data` | Model outputs / FinBERT scores. | `data/analysis/{analysis_type}/{symbol}/{timestamp}.parquet` | `symbol`, `timestamp`, `analysis_type`, `model_version` | `tests/fixtures/pipeline/sentiment_sample.parquet` |
| `metrics_data` | Aggregated metrics / performance trackers. | `data/metrics/{metric_type}/{symbol}.parquet` | `symbol`, `timestamp`, `metric_type` | (Add fixture when metrics pipeline lands) |

## Column Layouts

### `market_data`

| Column | Type | Notes |
| --- | --- | --- |
| `timestamp` | TIMESTAMP | Always timezone-naive UTC.
| `symbol` | TEXT | Uppercase ticker/pair.
| `source` | TEXT | e.g., `yahoo_finance`, `binance`.
| `interval` | TEXT | e.g., `1d`, `1h`.
| `open`, `high`, `low`, `close` | DOUBLE | OHLC values.
| `volume` | DOUBLE | Base volume.
| `vwap` | DOUBLE | Optional; calculators can drop.
| `trades` | BIGINT | Optional trade count.
| `data_hash` | TEXT | Dedup helper.
| `created_at` | TIMESTAMP | Insert timestamp.

### `news_data`

| Column | Type | Notes |
| --- | --- | --- |
| `timestamp` | TIMESTAMP | UTC publication time.
| `source` | TEXT | RSS source alias.
| `category` | TEXT | Optional tag (tech, macro...).
| `title` | TEXT | Headline.
| `link` | TEXT | Canonical URL.
| `description` | TEXT | Summary/body.
| `author` | TEXT | Optional author string.
| `tags` | TEXT[] | Optional tag list.
| `content_hash` | TEXT | Dedup helper.
| `created_at` | TIMESTAMP | Ingestion time.

### `analysis_data`

| Column | Type | Notes |
| --- | --- | --- |
| `timestamp` | TIMESTAMP | When the signal applies.
| `symbol` | TEXT | Ticker/pair.
| `analysis_type` | TEXT | e.g., `finbert_sentiment`.
| `model_name` | TEXT | Model ID.
| `model_version` | TEXT | Semantic version.
| `prediction` | DOUBLE | Main score.
| `confidence` | DOUBLE | Optional probability.
| `features` | JSON | Serialized feature vector.
| `metadata` | JSON | Extra context.
| `created_at` | TIMESTAMP | Ingestion time.

### `metrics_data`

| Column | Type | Notes |
| --- | --- | --- |
| `timestamp` | TIMESTAMP | Aggregation window end.
| `symbol` | TEXT | Optional; may be `NULL` for global metrics.
| `metric_type` | TEXT | Category (drawdown, pnl, coverage).
| `metric_name` | TEXT | More precise label.
| `value` | DOUBLE | Numeric value.
| `period` | TEXT | Textual window (e.g., `1d`).
| `metadata` | JSON | Additional payload.
| `created_at` | TIMESTAMP | Ingestion time.

## Programmatic Access

Import `TableContract` objects from `engines/schema_contracts.py` whenever you need canonical column names:

```python
from engines.schema_contracts import TABLE_CONTRACTS

market_cols = list(TABLE_CONTRACTS['market_data'].columns.keys())
```

When adding a new table:

1. Update `config/database.json` with the path pattern and deduplication keys.
2. Extend `engines/schema_contracts.py` with the new contract.
3. Document it here (description, columns, fixture).
4. Add/refresh fixtures under `tests/fixtures/` so smoke tests stay offline.

Keeping the docs and constants synchronized prevents accidental schema drift across pipelines.
