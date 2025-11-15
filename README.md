# WawaBackTrader - Enhanced Backtrader with Smart Data Engines

An enhanced version of [backtrader](https://www.backtrader.com/) with seamless data management, multiple data sources, and intelligent database integration.

## 🧭 Choose Your Operating Mode

| Mode | When to use | Install | Primary docs | Quick verification |
| --- | --- | --- | --- | --- |
| **Mode A – Backtest & Research Engine** | You only need `bt_run.py`, connectors, and the smart DB for historical analysis. | `pip install -r requirements-core.txt` or `make install-core` | `BACKTRADER_INTEGRATION.md`, `WORKSPACE_ORGANIZATION.md` | `make smoke` (runs offline SMA sample + CLI help) |
| **Mode B – News & Sentiment Pipeline** | You need the APScheduler-driven pipelines (news collector, FinBERT sentiment, alerting, execution). Install on top of Mode A. | `pip install -r requirements-pipeline.txt` or `make install-pipeline` | `docs/NEWS_PIPELINE_PLAN.md`, `docs/README_ENGINES.md` (pipeline sections) | `python engines/pipeline_scheduler.py --mock-pipelines --test --fixtures-dir tests/fixtures/pipeline` |

> Contributors can layer tooling with `pip install -r requirements-dev.txt` or `make install-dev` (includes pytest and keeps Mode A ready for tests).

> 📋 **New to the project?** Check out [WORKSPACE_ORGANIZATION.md](WORKSPACE_ORGANIZATION.md) for workspace structure and best practices.

## 🚀 Quick Start

### Mode A – Run Your First Backtest

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Run a strategy (data fetched automatically)
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL

# 3. Run with plotting
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL --plot
```

That's it! Data is automatically fetched from Yahoo Finance and saved locally for future use.

### Mode B – Dry-Run the Pipeline (Offline)

```bash
# 1. Install pipeline extras on top of core requirements
make install-pipeline

# 2. Execute every pipeline once in mock mode using fixtures
python engines/pipeline_scheduler.py --mock-pipelines --test \
    --fixtures-dir tests/fixtures/pipeline
```

The mock mode uses committed parquet fixtures so you can validate scheduling without hitting external APIs.

## ✅ Verification Matrix

| Capability | Command | Offline? | Requirements |
| --- | --- | --- | --- |
| Backtest happy path (Mode A) | `make smoke` (runs compile → SMA sample → `bt_run.py --help`) | ✅ yes (uses bundled CSV) | `make install-core` |
| Deterministic unit suite | `make test` | ✅ yes | `make install-core` + pytest (via `make install-dev`) |
| Pipeline scheduler mock cycle (Mode B) | `python engines/pipeline_scheduler.py --mock-pipelines --test --fixtures-dir tests/fixtures/pipeline` (also covered by `make smoke`) | ✅ yes (fixtures) | `make install-pipeline` |
| Live pipeline sanity | `python engines/pipeline_scheduler.py` | ❌ needs network + API keys | Mode B + real configs |

Document any new verification command in `AI_TASK_RECIPES.md` so future contributors can find it quickly.

## ✨ Key Features

### 🔄 Automatic Data Management
- **Database First**: Checks local database before fetching
- **Auto-Fetch**: Fetches from connector if data missing
- **Auto-Save**: Saves fetched data automatically
- **No Manual Setup**: Just run your strategy!

### 📊 Multiple Data Sources
- **Yahoo Finance**: Stocks, ETFs, indices
- **Binance**: Cryptocurrency data
- **CCXT**: 100+ crypto exchanges
- **Alpaca**: US stock market
- **Quandl**: Economic data
- **Alpha Vantage**: Stock data
- **Polygon.io**: Market data

### 🎯 Strategy Templates
- SMA Crossover Strategy
- RSI Mean Reversion
- Multi-Symbol Portfolio
- Custom Template

### 📰 News & RSS Integration
- Bloomberg, Reuters, Yahoo Finance
- CNBC, MarketWatch, CoinDesk
- Automatic storage and deduplication

### 🗄️ Smart Database
- Intelligent data partitioning
- Automatic deduplication
- Efficient parquet storage
- DuckDB for fast queries

## 📦 Installation

```bash
# Clone repository
git clone https://github.com/yourusername/WawaBackTrader.git
cd WawaBackTrader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install only what you need
pip install -r requirements-core.txt          # Mode A
pip install -r requirements-pipeline.txt      # (Optional) layer Mode B
pip install -r requirements-dev.txt           # (Optional) contributor tooling

# Configure API keys (optional, for specific sources)
# Edit config/connector.json, config/datasets.json, config/rss_sources.json
```

## 🎓 Usage Examples

### Example 1: Basic Strategy Run

```bash
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL
```

### Example 2: Custom Date Range

```bash
python bt_run.py \
    --strategy strategies/sma_cross.py \
    --symbols AAPL \
    --fromdate 2024-01-01 \
    --todate 2024-12-31
```

### Example 3: Cryptocurrency Trading

```bash
python bt_run.py \
    --strategy strategies/rsi_meanreversion.py \
    --symbols BTCUSDT ETHUSDT \
    --source binance \
    --interval 1h
```

### Example 4: Multi-Symbol Portfolio

```bash
python bt_run.py \
    --strategy strategies/multi_symbol_portfolio.py \
    --symbols AAPL GOOGL MSFT AMZN TSLA \
    --cash 100000 \
    --params top_n=3 rebalance_days=30
```

### Example 5: Custom Strategy Parameters

```bash
python bt_run.py \
    --strategy strategies/sma_cross.py \
    --symbols AAPL \
    --params fast_period=5 slow_period=20 \
    --cash 50000 \
    --commission 0.002
```

## 🛠️ Creating Your Own Strategy

### Method 1: Use Template

```bash
# Copy template
cp strategies/template.py strategies/my_strategy.py

# Edit your strategy
nano strategies/my_strategy.py

# Run it
python bt_run.py --strategy strategies/my_strategy.py --symbols AAPL
```

### Method 2: Minimal Example

```python
# strategies/my_strategy.py
import backtrader as bt

class MyStrategy(bt.Strategy):
    params = (('period', 20),)
    
    def __init__(self):
        self.sma = bt.indicators.SMA(self.datas[0], period=self.params.period)
    
    def next(self):
        if not self.position:
            if self.data.close[0] > self.sma[0]:
                self.buy()
        else:
            if self.data.close[0] < self.sma[0]:
                self.sell()
```

Run it:
```bash
python bt_run.py --strategy strategies/my_strategy.py --symbols AAPL
```

## 📚 Documentation

- **[Backtrader Integration Guide](BACKTRADER_INTEGRATION.md)** - Complete guide to running strategies
- **[Strategy Examples](strategies/README.md)** - Available strategies and how to create your own
- **[Data Architecture](DATA_ARCHITECTURE.md)** - How the smart database works
- **[Data Schema Contracts](docs/DATA_SCHEMA.md)** - Canonical columns/fixtures
- **[Engine Documentation](README_ENGINES.md)** - Data sources and CLI commands
- **[Zenguinis CLI Cheat Sheet](docs/ZENGUINIS_CLI.md)** - Mode A/B entry points, DuckDB health check
- **[Pipeline Runbook](docs/RUNBOOK_PIPELINE.md)** - 24/7 ops guide

## 🏗️ Architecture

```
WawaBackTrader/
├── bt_run.py                   # Strategy runner CLI
├── engines/
│   ├── bt_data.py             # Backtrader integration
│   ├── smart_db.py            # Smart database manager
│   ├── connector.py           # Market data connector
│   ├── rss.py                 # News/RSS engine
│   └── datasets.py            # Massive datasets engine
├── strategies/
│   ├── sma_cross.py           # SMA crossover
│   ├── rsi_meanreversion.py   # RSI strategy
│   ├── multi_symbol_portfolio.py
│   └── template.py            # Strategy template
├── config/
│   ├── connector.json         # API credentials
│   ├── rss_sources.json       # RSS feeds
│   ├── datasets.json          # Dataset APIs
│   └── database.json          # Database config
├── data/                      # Auto-created data storage
│   ├── market/               # Market data by symbol
│   ├── news/                 # News data by date
│   ├── reference/            # Reference data
│   └── analysis/             # Analysis results
└── scripts/                   # Helper scripts
    ├── template_basic.py
    ├── template_advanced.py
    ├── batch_collect.py
    └── scheduled_collect.py
```

## 🎯 Core Components

### 1. Strategy Runner (`bt_run.py`)
CLI tool for running strategies with automatic data management.

### 2. Smart Database (`engines/smart_db.py`)
Intelligent data storage with partitioning and deduplication.

### 3. Data Feed Integration (`engines/bt_data.py`)
Seamless connection between database, connectors, and backtrader.

### 4. Market Data Connector (`engines/connector.py`)
Multi-source market data with Yahoo, Binance, CCXT, Alpaca support.

### 5. RSS Engine (`engines/rss.py`)
News feed reader with proxy support and database storage.

### 6. Datasets Engine (`engines/datasets.py`)
Access to massive datasets from Kaggle, HuggingFace, Quandl, etc.

## 📊 Data Flow

```
1. User runs strategy → bt_run.py
2. Check database for data → smart_db.py
3. If missing, fetch → connector.py
4. Save to database → smart_db.py
5. Create data feed → bt_data.py
6. Run backtest → backtrader
7. Display results → CLI
```

## 🔧 CLI Commands

### Strategy Runner

```bash
# Basic
python bt_run.py --strategy PATH --symbols SYMBOL

# With options
python bt_run.py \
    --strategy strategies/sma_cross.py \
    --symbols AAPL GOOGL \
    --fromdate 2024-01-01 \
    --todate 2024-12-31 \
    --source yahoo_finance \
    --interval 1d \
    --cash 10000 \
    --commission 0.001 \
    --params fast_period=10 slow_period=30 \
    --plot
```

### Data Collection

```bash
# Fetch Yahoo Finance data
python -m engines.connector yahoo --symbol AAPL --period 1y

# Fetch Binance crypto
python -m engines.connector binance --symbol BTCUSDT --interval 1d

# Fetch RSS feeds
python -m engines.rss fetch-all

# Query database
python -m engines.connector query --sql "SELECT * FROM market_data LIMIT 10"
```

## 🌟 Example Output

```
============================================================
Backtrader Strategy Runner
============================================================

✓ Loaded strategy: SMACrossStrategy
✓ Added data feed: AAPL

============================================================
Running Backtest...
============================================================

Portfolio:
  Initial Value:  $10,000.00
  Final Value:    $12,345.67
  P&L:            $2,345.67 (+23.46%)

Performance Metrics:
  Sharpe Ratio:   1.45
  Max Drawdown:   8.32%
  Total Return:   23.46%

Trade Statistics:
  Total Trades:   12
  Won:            8
  Lost:           4
  Win Rate:       66.67%
```

## 🔍 Troubleshooting

### Data Not Loading
```bash
# Check database
python -m engines.connector query --sql "SELECT COUNT(*) FROM market_data"

# Force fetch
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL --no-db
```

### Import Errors
```bash
# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### Strategy Not Found
```bash
# Check file exists
ls strategies/my_strategy.py

# Check strategy class
grep "class.*bt.Strategy" strategies/my_strategy.py
```

## 📈 Performance Tips

1. **Use Database**: Data loads instantly from cache
2. **Disable Logging**: `--params printlog=false`
3. **Batch Operations**: Run multiple strategies in loop
4. **Database Cleanup**: Run `db.cleanup_old_data()` periodically

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch
3. Add your strategy or enhancement
4. Test thoroughly
5. Submit a pull request

## 📄 License

See [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- Built on top of [backtrader](https://www.backtrader.com/)
- Uses [DuckDB](https://duckdb.org/) for analytics
- Integrates [CCXT](https://github.com/ccxt/ccxt) for crypto data
- Supports [Alpaca](https://alpaca.markets/), [Quandl](https://www.quandl.com/), and more

## 📞 Support

- **Documentation**: See docs in this repository
- **Issues**: Open an issue on GitHub
- **Community**: Join backtrader community for general questions

## 🚦 Getting Started Checklist

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run example strategy: `python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL`
- [ ] Check output and results
- [ ] Try with different symbols or date ranges
- [ ] Copy template and create your own strategy
- [ ] Configure API keys for additional data sources (optional)
- [ ] Set up scheduled collection for regular data updates (optional)

## 🎉 What's Next?

1. **Explore Strategies**: Try all example strategies
2. **Create Custom Strategy**: Copy template and implement your logic
3. **Add Data Sources**: Configure APIs in config files
4. **Optimize Parameters**: Test different parameter combinations
5. **Schedule Collection**: Set up cron jobs for automated data updates
6. **Build Portfolio**: Create multi-symbol strategies
7. **Integrate News**: Use RSS data in your strategies

Happy trading! 🚀📊💰
