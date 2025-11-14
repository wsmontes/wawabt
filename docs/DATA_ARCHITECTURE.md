# Data Architecture Documentation

## Overview

The WawaBackTrader platform implements a **Smart Database Architecture** designed to efficiently manage multiple data types while maintaining data integrity, avoiding duplication, and preventing file explosion.

## Design Principles

### 1. **Separation of Concerns**
Different data types are stored in separate hierarchies:
- **Market Data**: Time-series OHLCV data
- **News Data**: RSS feeds and news articles
- **Reference Data**: Static metadata (symbols, exchanges)
- **Analysis Data**: ML predictions and calculations
- **Metrics Data**: Calculated metrics and aggregations
- **Logs**: System and operation logs

### 2. **Intelligent Partitioning**
Data is partitioned based on its access patterns:
- **By Symbol**: Market data (most queries filter by symbol)
- **By Date**: News and logs (time-based access)
- **By Analysis Type**: ML predictions (grouped by model/type)
- **Single File**: Reference data (small, frequently accessed)

### 3. **Automatic Deduplication**
Each data type has unique constraints:
- **Market Data**: `symbol + timestamp + source + interval`
- **News Data**: `link + timestamp`
- **Reference Data**: `entity_id` (e.g., symbol)
- **Analysis Data**: `symbol + timestamp + analysis_type + model_version`
- **Metrics Data**: `symbol + timestamp + metric_type`

### 4. **Hybrid Storage**
- **DuckDB**: In-memory/persistent database for complex queries
- **Parquet Files**: Efficient columnar storage for time-series data
- **Virtual Tables**: Query parquet files directly without loading

## Directory Structure

```
data/
├── market/                     # Market data (OHLCV)
│   ├── yahoo_finance/
│   │   ├── AAPL/
│   │   │   ├── 1d.parquet     # Daily data for AAPL
│   │   │   ├── 1h.parquet     # Hourly data for AAPL
│   │   │   └── 5m.parquet     # 5-minute data for AAPL
│   │   └── GOOGL/
│   │       └── 1d.parquet
│   ├── binance/
│   │   ├── BTCUSDT/
│   │   │   └── 1d.parquet
│   │   └── ETHUSDT/
│   │       └── 1h.parquet
│   └── ccxt/
│       └── BTC_USDT/
│           └── 1d.parquet
│
├── news/                       # News and RSS feeds
│   ├── Bloomberg/
│   │   ├── 2025/
│   │   │   ├── 01.parquet     # January 2025 news (partitioned by data timestamp)
│   │   │   └── 02.parquet     # February 2025 news (partitioned by data timestamp)
│   │   └── ...
│   ├── Reuters/
│   │   └── 2025/
│   │       └── 01.parquet
│   └── ...
│
├── reference/                  # Static reference data
│   ├── symbols.parquet         # All symbols metadata
│   ├── exchanges.parquet       # Exchange information
│   └── sectors.parquet         # Sector classifications
│
├── analysis/                   # ML predictions and analysis
│   ├── lstm_prediction/
│   │   ├── AAPL/
│   │   │   ├── 20250113_090000.parquet
│   │   │   └── 20250113_150000.parquet
│   │   └── GOOGL/
│   │       └── 20250113_090000.parquet
│   └── technical_indicators/
│       ├── AAPL/
│       │   └── 20250113_090000.parquet
│       └── ...
│
├── metrics/                    # Calculated metrics
│   ├── volatility/
│   │   ├── AAPL.parquet
│   │   └── GOOGL.parquet
│   ├── correlation/
│   │   └── portfolio.parquet
│   └── performance/
│       └── daily_returns.parquet
│
└── logs/                       # System logs
    ├── operations/
    │   └── 2025/
    │       └── 01.parquet
    └── errors/
        └── 2025/
            └── 01.parquet
```

## Data Schemas

### Market Data
```python
{
    "timestamp": "TIMESTAMP",       # Data point time
    "symbol": "VARCHAR",            # Stock/crypto symbol
    "source": "VARCHAR",            # Data source (yahoo, binance, etc.)
    "interval": "VARCHAR",          # Time interval (1d, 1h, 5m)
    "open": "DOUBLE",
    "high": "DOUBLE",
    "low": "DOUBLE",
    "close": "DOUBLE",
    "volume": "DOUBLE",
    "vwap": "DOUBLE",               # Volume weighted average price
    "trades": "BIGINT",             # Number of trades
    "data_hash": "VARCHAR",         # Hash for deduplication
    "created_at": "TIMESTAMP"       # When record was created
}
```

### News Data
```python
{
    "timestamp": "TIMESTAMP",       # Publication time
    "source": "VARCHAR",            # News source
    "category": "VARCHAR",          # markets, finance, crypto, etc.
    "title": "VARCHAR",
    "link": "VARCHAR",              # Unique URL
    "description": "VARCHAR",
    "author": "VARCHAR",
    "tags": "VARCHAR[]",            # Array of tags
    "content_hash": "VARCHAR",      # Hash for deduplication
    "created_at": "TIMESTAMP"
}
```

### Reference Data (Symbols)
```python
{
    "symbol": "VARCHAR PRIMARY KEY",
    "name": "VARCHAR",
    "exchange": "VARCHAR",
    "asset_type": "VARCHAR",        # stock, crypto, etf, etc.
    "currency": "VARCHAR",
    "country": "VARCHAR",
    "sector": "VARCHAR",
    "industry": "VARCHAR",
    "market_cap": "DOUBLE",
    "is_active": "BOOLEAN",
    "first_seen": "TIMESTAMP",
    "last_updated": "TIMESTAMP"
}
```

### Analysis Data
```python
{
    "timestamp": "TIMESTAMP",
    "symbol": "VARCHAR",
    "analysis_type": "VARCHAR",     # lstm_prediction, technical, etc.
    "model_name": "VARCHAR",        # model identifier
    "model_version": "VARCHAR",     # v1.0, v2.0, etc.
    "prediction": "DOUBLE",         # Predicted value
    "confidence": "DOUBLE",         # Confidence score
    "features": "JSON",             # Input features used
    "metadata": "JSON",             # Additional info
    "created_at": "TIMESTAMP"
}
```

### Metrics Data
```python
{
    "timestamp": "TIMESTAMP",
    "symbol": "VARCHAR",
    "metric_type": "VARCHAR",       # volatility, correlation, etc.
    "metric_name": "VARCHAR",       # Specific metric name
    "value": "DOUBLE",
    "period": "VARCHAR",            # 1d, 7d, 30d, etc.
    "metadata": "JSON",
    "created_at": "TIMESTAMP"
}
```

## Usage Examples

### Storing Market Data
```python
from engines.smart_db import SmartDatabaseManager

db = SmartDatabaseManager()

# Automatically handles deduplication and partitioning
db.store_market_data(
    df=market_df,
    source='yahoo_finance',
    symbol='AAPL',
    interval='1d'
)
```

### Querying Market Data
```python
# Query specific symbol across all sources
df = db.query_market_data(
    symbol='AAPL',
    start_date='2025-01-01',
    end_date='2025-01-31'
)

# Query specific source and interval
df = db.query_market_data(
    symbol='BTCUSDT',
    source='binance',
    interval='1h'
)
```

### Storing News Data
```python
# Automatically partitioned by data timestamp (year/month of news items)
# Data with different dates are saved to different files
db.store_news_data(
    df=news_df,  # Can contain news from multiple months
    source='Bloomberg'
)
# Result: Creates separate files like 2025/01.parquet, 2025/02.parquet
```

### Storing Analysis Results
```python
# Partitioned by analysis type and symbol
db.store_analysis_data(
    df=predictions_df,
    analysis_type='lstm_prediction',
    symbol='AAPL'
)
```

### Storing Calculated Metrics
```python
# Partitioned by metric type
db.store_metrics_data(
    df=metrics_df,
    metric_type='volatility',
    symbol='AAPL'
)
```

## Data Retention Policies

Configured in `config/database.json`:

- **Market Data**: `retention_days: 0` (keep forever)
- **News Data**: `retention_days: 365` (1 year)
- **Reference Data**: `retention_days: 0` (keep forever)
- **Analysis Data**: `retention_days: 180` (6 months)
- **Metrics Data**: `retention_days: 365` (1 year)
- **Logs**: `retention_days: 90` (3 months)

## Benefits of This Architecture

### ✅ **Avoids File Explosion**
- Smart partitioning prevents thousands of tiny files
- Related data is consolidated
- Old data is automatically cleaned up

### ✅ **Prevents Data Duplication**
- Automatic hash-based deduplication
- Unique constraints per data type
- Merge strategy for updates

### ✅ **Maintains Data Integrity**
- Separate storage for different data types
- Clear data relationships
- Consistent schemas

### ✅ **Optimizes Query Performance**
- Partitioning matches query patterns
- Virtual tables for efficient parquet queries
- Indexes on common filter columns

### ✅ **Scalable**
- Can handle terabytes of data
- Efficient compression
- Incremental updates

## Migration from Legacy Database

The system supports both legacy `DatabaseEngine` and new `SmartDatabaseManager`:

```python
# Use smart database (recommended)
connector = ConnectorEngine(use_smart_db=True)

# Use legacy database
connector = ConnectorEngine(use_smart_db=False)
```

## Monitoring and Maintenance

```python
# Get data summary
summary = db.get_data_summary()
print(summary)
# Output:
# {
#     'market_data': {'files': 45, 'size_mb': 523.4},
#     'news_data': {'files': 12, 'size_mb': 45.2},
#     ...
# }

# Run cleanup
db.cleanup_old_data()

# Optimize database
db.vacuum()
```

## Best Practices

1. **Always use the smart database** for new projects
2. **Define retention policies** based on your needs
3. **Monitor data growth** regularly
4. **Run cleanup** periodically (e.g., weekly)
5. **Backup critical data** before major operations
6. **Use appropriate partitioning** for your query patterns
7. **Let deduplication work automatically** - don't manually manage it

## Configuration

All settings in `config/database.json`:
- Data structure definitions
- Partition strategies
- Deduplication rules
- Retention policies
- Schema definitions
- Performance settings
