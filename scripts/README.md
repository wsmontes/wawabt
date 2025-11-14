# Scripts Directory

This directory contains script templates and utilities for working with the engines.

## Available Templates

### 1. `template_basic.py`
Basic script template for simple data collection tasks.

**Usage:**
```bash
python scripts/template_basic.py
```

### 2. `template_advanced.py`
Advanced pipeline template for complex data collection and analysis workflows.

**Usage:**
```bash
python scripts/template_advanced.py
```

### 3. `batch_collect.py`
Batch data collection for multiple symbols.

**Usage:**
```bash
# Yahoo Finance
python scripts/batch_collect.py AAPL GOOGL MSFT --source yahoo --period 1mo

# Crypto (CCXT)
python scripts/batch_collect.py BTC/USDT ETH/USDT --source ccxt --timeframe 1d --limit 100

# Binance
python scripts/batch_collect.py BTCUSDT ETHUSDT --source binance --interval 1h --limit 500
```

### 4. `scheduled_collect.py`
Template for scheduled/automated data collection (cron jobs, task scheduler).

**Usage:**
```bash
python scripts/scheduled_collect.py
```

**Setup with cron (Linux/macOS):**
```bash
# Edit crontab
crontab -e

# Add line to run every hour
0 * * * * cd /path/to/WawaBackTrader && /path/to/venv/bin/python scripts/scheduled_collect.py

# Run every day at 9 AM
0 9 * * * cd /path/to/WawaBackTrader && /path/to/venv/bin/python scripts/scheduled_collect.py
```

## Creating Your Own Scripts

1. Copy one of the templates
2. Modify the script logic to suit your needs
3. Make the script executable (optional):
   ```bash
   chmod +x scripts/your_script.py
   ```
4. Run your script:
   ```bash
   python scripts/your_script.py
   ```

## Best Practices

- Always close connections in a `finally` block
- Use logging for production scripts
- Save data to database for persistence
- Handle exceptions gracefully
- Use command-line arguments for flexibility

## Engine CLI Commands

All engines support extensive CLI commands:

### Database Engine
```bash
python -m engines.database list-tables
python -m engines.database list-files
python -m engines.database query "SELECT * FROM table_name LIMIT 10"
python -m engines.database load market_data --head 10
```

### Connector Engine
```bash
python -m engines.connector list-sources
python -m engines.connector yahoo AAPL --period 1y --output data.csv
python -m engines.connector ccxt BTC/USDT --timeframe 1h --limit 100
python -m engines.connector binance BTCUSDT --interval 1d --limit 500
```

### RSS Engine
```bash
python -m engines.rss list-sources
python -m engines.rss list-categories
python -m engines.rss fetch-all --output news.csv
python -m engines.rss fetch-category markets --output markets.parquet
```

### Datasets Engine
```bash
python -m engines.datasets list-sources
python -m engines.datasets kaggle-search "stock market"
python -m engines.datasets hf-search "financial data"
python -m engines.datasets alpha-vantage AAPL --outputsize full
python -m engines.datasets polygon AAPL --timespan day --limit 1000
```
