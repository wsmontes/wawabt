# WawaBackTrader Data Engines

## Overview

WawaBackTrader includes a comprehensive data infrastructure for collecting, storing, and managing financial data from multiple sources. The system is designed to handle:

- **Market Data**: OHLCV data from stocks, crypto, and other assets
- **News Data**: RSS feeds and news articles
- **Reference Data**: Symbol metadata, exchange information
- **Analysis Data**: ML predictions and calculated indicators
- **Metrics Data**: Performance metrics and aggregations

## Architecture

The platform uses a **Smart Database Architecture** that:
- ✅ Avoids file explosion through intelligent partitioning
- ✅ Prevents data duplication with automatic deduplication
- ✅ Maintains data integrity by separating different data types
- ✅ Optimizes query performance with strategic indexing
- ✅ Scales to handle terabytes of data

See [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md) for detailed information.

## Quick Start

### 1. Setup

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API keys
# Edit config/connector.json, config/datasets.json, config/rss_sources.json
```

### 2. Basic Usage

```python
from engines.connector import ConnectorEngine
from engines.smart_db import SmartDatabaseManager

# Initialize connector with smart database
connector = ConnectorEngine(use_smart_db=True)

# Fetch and store market data
df = connector.get_yahoo_data('AAPL', period='1mo', interval='1d')
# Data automatically saved to: data/market/yahoo_finance/AAPL/1d.parquet

# Query the data
db = SmartDatabaseManager()
df = db.query_market_data(symbol='AAPL', start_date='2025-01-01')
```

## Available Engines

### 1. Connector Engine (`engines/connector.py`)

**🆕 UPDATED**: Enhanced multi-source market data connector with expanded capabilities:

**Data Sources:**
- **Yahoo Finance**: Stocks, ETFs, indices, historical data
- **CCXT**: 100+ cryptocurrency exchanges (multiple exchanges simultaneously)
- **Binance**: Cryptocurrency klines, order books, tickers
- **Alpaca Markets**: 
  - 📈 **Stocks**: Bars, quotes, trades, latest data
  - 🪙 **Crypto**: Bars, quotes, trades, orderbooks (no auth required!)
  - 📊 **Options**: Bars, trades, option chains, greeks
  - 📰 **News**: Real-time news articles (NO AUTH REQUIRED!)
  - 🏢 **Corporate Actions**: Splits, dividends, mergers (essential for backtesting)

**New Features:**
- ✅ Multiple CCXT exchanges support (not just one)
- ✅ Alpaca news feed (free, no authentication needed)
- ✅ Alpaca corporate actions (splits, dividends)
- ✅ Alpaca crypto and options data
- ✅ Binance order book and ticker data
- ✅ Proper retry logic with exponential backoff
- ✅ Better rate limiting and error handling
- ✅ Latest data endpoints (real-time quotes, trades, bars)

#### CLI Commands

```bash
# List available sources
python -m engines.connector list-sources

# Fetch Yahoo Finance data
python -m engines.connector yahoo --symbol AAPL --period 1mo

# Fetch from CCXT (Binance)
python -m engines.connector ccxt --exchange binance --symbol BTC/USDT --timeframe 1d --limit 100

# Fetch from Binance directly
python -m engines.connector binance --symbol BTCUSDT --interval 1d --limit 500

# Fetch from Alpaca
python -m engines.connector alpaca --symbol AAPL --start 2025-01-01 --timeframe Day

# Query stored data
python -m engines.connector query --sql "SELECT * FROM market_data WHERE symbol='AAPL'"
```

#### Python Usage

```python
from engines.connector import ConnectorEngine
from datetime import datetime, timedelta

connector = ConnectorEngine(use_smart_db=True)

# === Yahoo Finance ===
df = connector.get_yahoo_data('AAPL', period='1y', interval='1d')

# === CCXT (Multiple Exchanges) ===
# List all enabled exchanges
exchanges = connector.get_available_exchanges()
print(exchanges)  # {'ccxt': ['binance', 'coinbase'], 'alpaca': ['stocks', 'crypto', 'options', 'news'], ...}

# Get data from specific exchange
df = connector.get_ccxt_ohlcv('BTC/USDT', timeframe='1h', limit=100, exchange='binance')

# Get order book
orderbook = connector.get_ccxt_orderbook('BTC/USDT', limit=20, exchange='binance')

# Get ticker
ticker = connector.get_ccxt_ticker('BTC/USDT', exchange='binance')

# Get recent trades
trades = connector.get_ccxt_trades('BTC/USDT', limit=50, exchange='binance')

# === Binance Direct ===
df = connector.get_binance_klines('BTCUSDT', interval='1d', limit=365)
ticker = connector.get_binance_ticker('BTCUSDT')
orderbook = connector.get_binance_orderbook('BTCUSDT', limit=100)

# === Alpaca Stocks ===
end = datetime.now()
start = end - timedelta(days=30)

# Bars (OHLCV)
df = connector.get_alpaca_bars('AAPL', start=start, end=end, timeframe='1Day')

# Quotes (bid/ask)
df = connector.get_alpaca_quotes('AAPL', start=start, end=end)

# Trades
df = connector.get_alpaca_trades('AAPL', start=start, end=end)

# Latest data (real-time)
latest_bar = connector.get_alpaca_latest_bar('AAPL')
latest_quote = connector.get_alpaca_latest_quote('AAPL')
latest_trade = connector.get_alpaca_latest_trade('AAPL')

# === Alpaca Crypto ===
df = connector.get_alpaca_crypto_bars('BTC/USD', start=start, end=end, timeframe='1Hour')

# === Alpaca Options ===
df = connector.get_alpaca_option_bars('AAPL250117C00150000', start=start, end=end)
chain = connector.get_alpaca_option_chain('AAPL')  # Get all option contracts

# === Alpaca News (NO AUTH REQUIRED!) ===
# Get news for specific symbols
news_df = connector.get_alpaca_news(symbols=['AAPL', 'GOOGL'], limit=50)

# Get all news
news_df = connector.get_alpaca_news(start=start, end=end, limit=50)

# === Alpaca Corporate Actions ===
# Get splits, dividends, mergers, etc.
actions_df = connector.get_alpaca_corporate_actions(
    symbols=['AAPL', 'TSLA'],
    start=datetime(2024, 1, 1),
    end=datetime.now()
)
```

**Adjustment Types (Alpaca):**
- `'raw'`: Unadjusted data
- `'split'`: Adjusted for stock splits
- `'dividend'`: Adjusted for dividends
- `'all'`: Adjusted for all corporate actions

**Data Feeds (Alpaca):**
- `'iex'`: IEX (default, free)
- `'sip'`: SIP (consolidated, requires subscription)

### 2. RSS Engine (`engines/rss.py`)

News feed reader with proxy support and database integration.

#### Supported Sources

- Bloomberg
- Reuters
- Yahoo Finance
- MarketWatch
- CNBC
- Seeking Alpha
- CoinDesk
- CryptoCompare

#### CLI Commands

```bash
# Fetch all sources
python -m engines.rss fetch-all

# Fetch by category
python -m engines.rss fetch-category --category markets

# Fetch specific URL
python -m engines.rss fetch-url --url "https://feeds.bloomberg.com/markets/news.rss"

# Add new source
python -m engines.rss add-source --name "Custom" --url "https://..." --category markets

# List sources
python -m engines.rss list-sources

# Query news
python -m engines.rss query --sql "SELECT * FROM news_data WHERE source='Bloomberg'"
```

#### Python Usage

```python
from engines.rss import RSSEngine

rss = RSSEngine(use_smart_db=True)

# Fetch all sources
df = rss.fetch_all_sources()
# Data saved to: data/news/{source}/{year}/{month}.parquet

# Fetch by category
df = rss.fetch_by_category('markets')

# Fetch specific URL
df = rss.fetch_feed('https://feeds.bloomberg.com/markets/news.rss')
```

### 3. Datasets Engine (`engines/datasets.py`)

Massive dataset access from multiple platforms.

#### Supported Sources

- **Kaggle**: Financial datasets from Kaggle
- **Hugging Face**: ML and financial datasets
- **Quandl**: Economic and financial time series
- **Alpha Vantage**: Stock market data
- **Polygon.io**: Real-time and historical market data

#### CLI Commands

```bash
# === KAGGLE ===
# Search datasets
python -m engines.datasets kaggle-search --query "stock market"

# Download dataset
python -m engines.datasets kaggle-download --dataset "username/dataset-name"

# === HUGGING FACE ===
# Search datasets
python -m engines.datasets hf-search --query "financial"

# Load dataset
python -m engines.datasets hf-load --dataset "financial_phrasebank"

# === QUANDL ===
# Get Quandl data
python -m engines.datasets quandl --database WIKI --dataset AAPL

# === ALPHA VANTAGE ===
# Get stock data
python -m engines.datasets alpha-vantage --symbol AAPL --function TIME_SERIES_DAILY

# === POLYGON.IO ===
# Get aggregates
python -m engines.datasets polygon --ticker AAPL --timespan day --from 2024-01-01

# Get ticker list
python -m engines.datasets polygon-tickers --market stocks --limit 100

# === UTILITY ===
# List available sources
python -m engines.datasets list-sources

# Query data
python -m engines.datasets query --sql "SELECT * FROM market_data LIMIT 10"
```

#### Python Usage

```python
from engines.datasets import DatasetsEngine

datasets = DatasetsEngine(use_smart_db=True)

# Kaggle
results = datasets.search_kaggle("stock market")
datasets.download_kaggle_dataset("username/dataset-name")

# Hugging Face
results = datasets.search_huggingface("financial", limit=5)
df = datasets.load_huggingface_dataset("financial_phrasebank")

# Quandl
df = datasets.get_quandl_data("WIKI", "AAPL", start_date="2024-01-01")

# Alpha Vantage
df = datasets.get_alpha_vantage_data("AAPL", function="TIME_SERIES_DAILY")

# Polygon.io
df = datasets.get_polygon_aggregates("AAPL", timespan="day", from_date="2024-01-01")
tickers = datasets.get_polygon_tickers(market="stocks", limit=100)
```

### 4. Smart Database Manager (`engines/smart_db.py`)

Intelligent database manager that solves the data organization challenge.

#### Features

- **Automatic Partitioning**: Data organized by symbol, date, or type
- **Deduplication**: Hash-based deduplication per data type
- **Virtual Tables**: Query across multiple parquet files
- **Retention Policies**: Automatic cleanup of old data
- **Type Safety**: Enforced schemas per data type

#### Python Usage

```python
from engines.smart_db import SmartDatabaseManager

db = SmartDatabaseManager()

# Store market data (automatically partitioned by symbol)
db.store_market_data(df, source='yahoo_finance', symbol='AAPL', interval='1d')
# Saved to: data/market/yahoo_finance/AAPL/1d.parquet

# Store news data (automatically partitioned by date)
db.store_news_data(df, source='Bloomberg')
# Saved to: data/news/Bloomberg/2025/01.parquet

# Store reference data (single file per entity type)
db.store_reference_data(df, entity_type='symbols')
# Saved to: data/reference/symbols.parquet

# Store analysis results (partitioned by type and symbol)
db.store_analysis_data(df, analysis_type='lstm_prediction', symbol='AAPL')
# Saved to: data/analysis/lstm_prediction/AAPL/{timestamp}.parquet

# Query market data
df = db.query_market_data(symbol='AAPL', start_date='2025-01-01', end_date='2025-01-31')

# Query news data
df = db.query_news_data(source='Bloomberg', start_date='2025-01-01')

# Query analysis data
df = db.query_analysis_data(analysis_type='lstm_prediction', symbol='AAPL')

# Get data summary
summary = db.get_data_summary()

# Cleanup old data
db.cleanup_old_data()
```

## Configuration

All engines are configured through JSON files in the `config/` directory:

### `config/connector.json`
```json
{
  "sources": ["yahoo", "ccxt", "binance", "alpaca"],
  "ccxt": {
    "default_exchange": "binance",
    "rate_limit": true
  },
  "binance": {
    "api_key": "",
    "api_secret": ""
  },
  "alpaca": {
    "api_key": "",
    "secret_key": "",
    "base_url": "https://data.alpaca.markets"
  }
}
```

### `config/rss_sources.json`
```json
{
  "sources": [
    {
      "name": "Bloomberg",
      "url": "https://feeds.bloomberg.com/markets/news.rss",
      "category": "markets",
      "enabled": true
    }
  ],
  "proxy": {
    "enabled": false,
    "rotation": false,
    "proxies": []
  }
}
```

### `config/datasets.json`
```json
{
  "kaggle": {
    "username": "",
    "key": ""
  },
  "quandl": {
    "api_key": ""
  },
  "alpha_vantage": {
    "api_key": ""
  },
  "polygon": {
    "api_key": ""
  },
  "data_folder": "data/datasets"
}
```

### `config/database.json`

See [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md) for complete database configuration.

## Scripts

Ready-to-use script templates are in the `scripts/` directory:

### Basic Template (`scripts/template_basic.py`)
```bash
python scripts/template_basic.py
```

Simple data collection starter.

### Advanced Template (`scripts/template_advanced.py`)
```bash
python scripts/template_advanced.py
```

Complete pipeline with collection, analysis, and export.

### Batch Collection (`scripts/batch_collect.py`)
```bash
# Collect multiple symbols
python scripts/batch_collect.py --symbols AAPL GOOGL MSFT --source yahoo

# Collect from Binance
python scripts/batch_collect.py --symbols BTCUSDT ETHUSDT --source binance
```

### Scheduled Collection (`scripts/scheduled_collect.py`)
```bash
# Run once (for cron jobs)
python scripts/scheduled_collect.py

# Add to crontab for daily collection at 6 PM:
# 0 18 * * * cd /path/to/WawaBackTrader && source venv/bin/activate && python scripts/scheduled_collect.py >> logs/cron.log 2>&1
```

See [scripts/README.md](scripts/README.md) for detailed usage.

## Directory Structure

```
WawaBackTrader/
├── engines/                 # Data engines
│   ├── connector.py        # Market data connector
│   ├── rss.py             # RSS feed reader
│   ├── datasets.py        # Massive dataset access
│   ├── smart_db.py        # Smart database manager
│   └── database.py        # Legacy database engine
├── config/                 # Configuration files
│   ├── connector.json     # Connector settings
│   ├── rss_sources.json   # RSS sources
│   ├── datasets.json      # Dataset API keys
│   └── database.json      # Database configuration
├── scripts/               # Ready-to-use templates
│   ├── template_basic.py
│   ├── template_advanced.py
│   ├── batch_collect.py
│   └── scheduled_collect.py
├── data/                  # Data storage (auto-created)
│   ├── market/           # Market data (by symbol)
│   ├── news/             # News data (by date)
│   ├── reference/        # Reference data
│   ├── analysis/         # Analysis results
│   ├── metrics/          # Calculated metrics
│   └── logs/             # System logs
└── venv/                 # Virtual environment
```

## Best Practices

### 1. Always Use Smart Database
```python
# ✅ Recommended
connector = ConnectorEngine(use_smart_db=True)

# ❌ Legacy
connector = ConnectorEngine(use_smart_db=False)
```

### 2. Let Deduplication Work Automatically
Don't manually check for duplicates - the smart database handles it:
```python
# Just store the data, duplicates are automatically handled
connector.get_yahoo_data('AAPL', period='1mo')
connector.get_yahoo_data('AAPL', period='1mo')  # Safe - no duplicates
```

### 3. Use CLI for Quick Tasks
```bash
# Quick data fetch
python -m engines.connector yahoo --symbol AAPL --period 1mo

# Quick query
python -m engines.connector query --sql "SELECT COUNT(*) FROM market_data"
```

### 4. Use Python for Complex Pipelines
```python
# Complex multi-source collection
connector = ConnectorEngine(use_smart_db=True)
rss = RSSEngine(use_smart_db=True)

# Collect market data
for symbol in ['AAPL', 'GOOGL', 'MSFT']:
    connector.get_yahoo_data(symbol, period='1mo')

# Collect news
rss.fetch_by_category('markets')

# Query and analyze
db = SmartDatabaseManager()
market_df = db.query_market_data(symbol='AAPL')
news_df = db.query_news_data(source='Bloomberg')
```

### 5. Monitor Data Growth
```python
db = SmartDatabaseManager()

# Check data summary
summary = db.get_data_summary()
print(f"Market data: {summary['market_data']['size_mb']} MB")
print(f"News data: {summary['news_data']['size_mb']} MB")

# Run cleanup periodically
db.cleanup_old_data()
```

### 6. Configure Retention Policies
Edit `config/database.json`:
```json
{
  "data_structure": {
    "market_data": {
      "retention_days": 0  // Keep forever
    },
    "news_data": {
      "retention_days": 365  // 1 year
    }
  }
}
```

## Troubleshooting

### Import Errors
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Install missing packages
pip install -r requirements.txt
```

### API Key Errors
```bash
# Check configuration files
cat config/connector.json
cat config/datasets.json

# Ensure API keys are set
```

### Database Errors
```bash
# Check database file
ls -lh data/market_data.duckdb

# If corrupted, delete and recreate
rm data/market_data.duckdb
python -m engines.smart_db  # Will recreate
```

### Data Not Saving
```python
# Ensure save_to_db=True (default)
connector.get_yahoo_data('AAPL', save_to_db=True)

# Check database initialization
connector = ConnectorEngine(use_smart_db=True)
print(f"Database initialized: {connector.db is not None}")
```

## Performance Tips

### 1. Batch Operations
```python
# ✅ Efficient: Batch collection
symbols = ['AAPL', 'GOOGL', 'MSFT']
for symbol in symbols:
    connector.get_yahoo_data(symbol, period='1mo')

# ❌ Inefficient: Multiple small collections
connector.get_yahoo_data('AAPL', period='1d')  # Many API calls
```

### 2. Use Appropriate Intervals
```python
# For backtesting: daily data is usually sufficient
df = connector.get_yahoo_data('AAPL', period='1y', interval='1d')

# For intraday: use appropriate interval
df = connector.get_binance_klines('BTCUSDT', interval='5m', limit=100)
```

### 3. Query Efficiently
```python
# ✅ Filter early
df = db.query_market_data(
    symbol='AAPL',
    start_date='2025-01-01',
    end_date='2025-01-31'
)

# ❌ Load everything then filter
df = db.query_market_data(symbol='AAPL')
df = df[df['timestamp'] > '2025-01-01']
```

## Contributing

When adding new data sources:

1. Add methods to appropriate engine
2. Update configuration files
3. Add CLI commands
4. Use smart database storage methods
5. Document in README
6. Add to requirements.txt if needed

## License

See [LICENSE](LICENSE) file.

## Support

For issues, questions, or contributions, please open an issue on GitHub.
