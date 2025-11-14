# Backtrader Integration Guide

## Overview

WawaBackTrader provides seamless integration between backtrader and the data engines, allowing you to run strategies with automatic data retrieval from the database or connectors.

## Key Features

✅ **Automatic Data Management** - Data fetched from database first, connector if needed
✅ **Multiple Data Sources** - Yahoo, Binance, CCXT, Alpaca, Quandl, Alpha Vantage, Polygon
✅ **Auto-Save** - All fetched data automatically saved to database for reuse
✅ **CLI Interface** - Run strategies from command line with simple commands
✅ **Multi-Symbol Support** - Trade multiple symbols simultaneously
✅ **Built-in Analyzers** - Sharpe ratio, drawdown, returns, trade analysis
✅ **Strategy Templates** - Ready-to-use examples and templates

## Quick Start

### 1. Run a Pre-Built Strategy

```bash
# Simple SMA crossover on AAPL
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL

# RSI mean reversion on Bitcoin
python bt_run.py --strategy strategies/rsi_meanreversion.py --symbols BTCUSDT \
    --source binance --interval 1h

# Multi-symbol portfolio
python bt_run.py --strategy strategies/multi_symbol_portfolio.py \
    --symbols AAPL GOOGL MSFT AMZN TSLA --cash 100000
```

### 2. Create Your Own Strategy

```bash
# Copy template
cp strategies/template.py strategies/my_strategy.py

# Edit your strategy (see template for structure)
nano strategies/my_strategy.py

# Run it
python bt_run.py --strategy strategies/my_strategy.py --symbols AAPL
```

## How It Works

### Data Flow

```
1. bt_run.py loads your strategy
2. AutoFetchData checks database for data
3. If data missing, fetches from connector
4. Fetched data saved to database automatically
5. Data feed created for backtrader
6. Strategy runs with data
7. Results displayed
```

### Architecture

```
bt_run.py (CLI Runner)
    ↓
engines/bt_data.py (Data Feed Integration)
    ↓
engines/smart_db.py (Database) ←→ engines/connector.py (Data Sources)
    ↓
backtrader (Strategy Execution)
```

## CLI Reference

### Basic Usage

```bash
python bt_run.py --strategy PATH --symbols SYMBOL [OPTIONS]
```

### Required Arguments

- `--strategy`, `-s`: Path to strategy file
- `--symbols`, `-y`: Symbol(s) to trade (space-separated)

### Date Range

```bash
# Specific date range
--fromdate 2024-01-01 --todate 2024-12-31

# Default: last 1 year to today
```

### Data Source Options

```bash
# Yahoo Finance (default)
--source yahoo_finance

# Binance cryptocurrency
--source binance --interval 1h

# CCXT (any exchange)
--source ccxt --interval 1d

# Alpaca stocks
--source alpaca --interval 1Day

# Quandl
--source quandl

# Alpha Vantage
--source alpha_vantage

# Polygon.io
--source polygon
```

### Backtest Settings

```bash
# Initial cash
--cash 100000

# Commission (as decimal, e.g., 0.001 = 0.1%)
--commission 0.001
```

### Strategy Parameters

```bash
# Pass parameters to strategy
--params fast_period=10 slow_period=30 printlog=false

# Multiple parameters
--params rsi_period=14 rsi_oversold=30 rsi_overbought=70
```

### Output Options

```bash
# Generate plot
--plot

# Disable analyzers
--no-analyzers

# Disable database (fetch only)
--no-db

# Disable auto-fetch (database only)
--no-fetch
```

## Complete Examples

### Example 1: Simple Run

```bash
python bt_run.py \
    --strategy strategies/sma_cross.py \
    --symbols AAPL
```

**What happens:**
1. Loads SMA crossover strategy
2. Checks database for AAPL data
3. If missing, fetches from Yahoo Finance
4. Saves to database
5. Runs backtest
6. Shows results

### Example 2: Custom Date Range

```bash
python bt_run.py \
    --strategy strategies/sma_cross.py \
    --symbols AAPL \
    --fromdate 2024-01-01 \
    --todate 2024-12-31
```

### Example 3: Crypto Trading

```bash
python bt_run.py \
    --strategy strategies/rsi_meanreversion.py \
    --symbols BTCUSDT ETHUSDT \
    --source binance \
    --interval 1h \
    --cash 50000
```

### Example 4: Multi-Symbol Portfolio

```bash
python bt_run.py \
    --strategy strategies/multi_symbol_portfolio.py \
    --symbols AAPL GOOGL MSFT AMZN TSLA NVDA META \
    --cash 100000 \
    --params top_n=4 rebalance_days=14 \
    --fromdate 2024-01-01
```

### Example 5: Custom Parameters

```bash
python bt_run.py \
    --strategy strategies/sma_cross.py \
    --symbols AAPL \
    --params fast_period=5 slow_period=20 printlog=false \
    --commission 0.002 \
    --cash 25000
```

### Example 6: With Plotting

```bash
python bt_run.py \
    --strategy strategies/sma_cross.py \
    --symbols AAPL \
    --fromdate 2024-01-01 \
    --plot
```

## Creating Strategies

### Strategy Structure

Every strategy must:
1. Extend `bt.Strategy`
2. Define parameters in `params` tuple
3. Implement `__init__()` for indicators
4. Implement `next()` for trading logic

### Minimal Strategy

```python
import backtrader as bt

class MinimalStrategy(bt.Strategy):
    params = (
        ('period', 20),
    )
    
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

### Using the Template

```bash
# Copy template
cp strategies/template.py strategies/my_strategy.py
```

Template includes:
- Parameter definition
- Logging function
- Order notification handling
- Trade notification handling
- Indicator setup
- Trading logic structure
- Test harness

### Available Indicators

Backtrader includes 100+ built-in indicators:

```python
# Moving Averages
bt.indicators.SMA(period=20)
bt.indicators.EMA(period=20)
bt.indicators.WMA(period=20)

# Oscillators
bt.indicators.RSI(period=14)
bt.indicators.MACD()
bt.indicators.Stochastic()
bt.indicators.CCI(period=20)

# Volatility
bt.indicators.BollingerBands()
bt.indicators.ATR(period=14)
bt.indicators.StdDev(period=20)

# Volume
bt.indicators.Volume()
bt.indicators.OBV()

# Trend
bt.indicators.ADX(period=14)
bt.indicators.Aroon(period=25)
bt.indicators.ParabolicSAR()

# Crossovers
bt.indicators.CrossOver(ind1, ind2)
bt.indicators.CrossUp(ind1, ind2)
bt.indicators.CrossDown(ind1, ind2)
```

## Python Integration

### Using AutoFetchData Directly

```python
from datetime import datetime, timedelta
from engines.bt_data import AutoFetchData
import backtrader as bt

# Create data feed
data = AutoFetchData.create(
    symbol='AAPL',
    fromdate=datetime(2024, 1, 1),
    todate=datetime(2024, 12, 31),
    source='yahoo_finance',
    interval='1d'
)

# Add to cerebro
cerebro = bt.Cerebro()
cerebro.adddata(data)
cerebro.addstrategy(MyStrategy)
cerebro.run()
```

### Multiple Symbols

```python
from engines.bt_data import create_multiple_feeds

# Create multiple feeds at once
feeds = create_multiple_feeds(
    symbols=['AAPL', 'GOOGL', 'MSFT'],
    fromdate=datetime(2024, 1, 1),
    todate=datetime(2024, 12, 31)
)

# Add all to cerebro
for symbol, feed in feeds.items():
    cerebro.adddata(feed, name=symbol)
```

### Convenience Functions

```python
from engines.bt_data import create_data_feed

# Quick single symbol
data = create_data_feed('AAPL', fromdate=datetime(2024, 1, 1))
cerebro.adddata(data)
```

## Advanced Usage

### Custom Data Source

```python
# Use specific source and interval
data = AutoFetchData.create(
    symbol='BTCUSDT',
    source='binance',
    interval='1h',
    fromdate=datetime.now() - timedelta(days=30)
)
```

### Disable Auto-Fetch

```python
# Only use database, don't fetch if missing
data = AutoFetchData.create(
    symbol='AAPL',
    auto_fetch=False
)
```

### Custom Database Path

```python
data = AutoFetchData.create(
    symbol='AAPL',
    db_path='custom/path/data.duckdb',
    connector_config='custom/config.json'
)
```

## Output and Results

### Standard Output

```
============================================================
Backtrader Strategy Runner
============================================================

✓ Loaded strategy: SMACrossStrategy

Backtest Period: 2024-01-01 to 2024-12-31
Symbols: AAPL
Data Source: yahoo_finance
Interval: 1d

✓ Added strategy: SMACrossStrategy
  Parameters: {'fast_period': 10, 'slow_period': 30}

------------------------------------------------------------
Loading Data...
------------------------------------------------------------
[AutoFetchData] Attempting to load AAPL from database...
[AutoFetchData] Loaded 252 rows from database for AAPL
✓ Added data feed: AAPL

✓ Initial Cash: $10,000.00
✓ Commission: 0.1%
✓ Added analyzers: Sharpe, DrawDown, Returns, TradeAnalyzer

============================================================
Running Backtest...
============================================================

[2024-01-02] Close: 184.30
[2024-01-03] BUY CREATE, 183.88
[2024-01-04] BUY EXECUTED, Price: 184.35, Cost: 18435.00, Comm: 18.44
...

============================================================
Backtest Results
============================================================

Portfolio:
  Initial Value:  $10,000.00
  Final Value:    $12,345.67
  P&L:            $2,345.67 (+23.46%)

Performance Metrics:
  Sharpe Ratio:   1.45
  Max Drawdown:   8.32%
  Total Return:   23.46%
  Avg Return:     0.09%

Trade Statistics:
  Total Trades:   12
  Won:            8
  Lost:           4
  Win Rate:       66.67%
  Net P&L:        $2,345.67

Execution Time: 1.23 seconds

============================================================
```

### Plotting Output

With `--plot` flag, generates an interactive matplotlib chart showing:
- Price candlesticks
- Indicators
- Buy/sell signals
- Portfolio value
- Trade markers

## Troubleshooting

### "Failed to load data"

**Problem:** Data not available in database or from connector

**Solutions:**
```bash
# Check database
python -m engines.connector query --sql "SELECT * FROM market_data WHERE symbol='AAPL'"

# Force fetch
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL --no-db

# Check connector configuration
cat config/connector.json
```

### "No strategy class found"

**Problem:** Strategy file doesn't have a class extending bt.Strategy

**Solution:**
```python
# Ensure your strategy looks like this:
import backtrader as bt

class MyStrategy(bt.Strategy):  # Must extend bt.Strategy
    # ... rest of strategy
```

### "Import pandas could not be resolved"

**Problem:** Virtual environment not activated or dependencies not installed

**Solution:**
```bash
# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Parameters Not Working

**Problem:** Strategy parameters not being applied

**Solution:**
```bash
# Check parameter names match strategy definition
grep "params = " strategies/my_strategy.py

# Use correct format
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --params fast_period=10 slow_period=30  # No quotes, use underscores
```

## Best Practices

### 1. Test Locally First

```python
# Add test code to your strategy file
if __name__ == '__main__':
    # Test code here
    pass
```

Run: `python strategies/my_strategy.py`

### 2. Start with Template

```bash
cp strategies/template.py strategies/my_new_strategy.py
```

### 3. Use Logging

```python
def log(self, txt, dt=None):
    if self.params.printlog:
        dt = dt or self.datas[0].datetime.date(0)
        print(f'[{dt.isoformat()}] {txt}')
```

### 4. Handle Orders Properly

```python
def notify_order(self, order):
    # Always check order status
    if order.status in [order.Completed]:
        # Order filled
        pass
    elif order.status in [order.Canceled, order.Margin, order.Rejected]:
        # Order failed
        pass
```

### 5. Check Position Before Trading

```python
def next(self):
    if not self.position:
        # Not in market - can buy
        if self.buy_signal():
            self.buy()
    else:
        # In market - can sell
        if self.sell_signal():
            self.sell()
```

### 6. Use Analyzers

```bash
# Always run with analyzers for performance metrics
python bt_run.py --strategy strategies/my_strategy.py --symbols AAPL
# (analyzers enabled by default)
```

## Integration with Existing Backtrader Code

### Migrate Existing Strategy

If you have existing backtrader strategies:

1. Copy your strategy file to `strategies/` folder
2. No code changes needed!
3. Run with bt_run.py:

```bash
python bt_run.py --strategy strategies/your_existing_strategy.py --symbols AAPL
```

### Use with Existing Cerebro Setup

```python
import backtrader as bt
from engines.bt_data import create_data_feed

# Your existing cerebro setup
cerebro = bt.Cerebro()
cerebro.addstrategy(YourExistingStrategy)

# Just change data loading
# OLD: data = bt.feeds.YahooFinanceData(...)
# NEW: data = create_data_feed('AAPL', fromdate=datetime(2024, 1, 1))
data = create_data_feed('AAPL', fromdate=datetime(2024, 1, 1))

cerebro.adddata(data)
cerebro.run()
```

## Performance Tips

### 1. Use Database

The smart database caches data locally for instant loading:

```bash
# First run: fetches from connector (~5-10 seconds)
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL

# Subsequent runs: loads from database (~0.5 seconds)
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL
```

### 2. Disable Logging for Speed

```bash
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --params printlog=false
```

### 3. Disable Analyzers

```bash
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --no-analyzers
```

### 4. Batch Multiple Runs

```bash
# Run multiple strategies in a loop
for strategy in strategies/*.py; do
    python bt_run.py --strategy $strategy --symbols AAPL
done
```

## Resources

- [Backtrader Documentation](https://www.backtrader.com/docu/)
- [Strategy Examples](strategies/README.md)
- [Data Architecture](DATA_ARCHITECTURE.md)
- [Engine Documentation](README_ENGINES.md)

## Next Steps

1. **Try Examples**: Run the pre-built strategies
2. **Create Strategy**: Copy template and implement your logic
3. **Optimize**: Test different parameters
4. **Scale**: Add more symbols or data sources
5. **Automate**: Schedule strategy runs with cron

## Support

For issues or questions:
- Check [strategies/README.md](strategies/README.md) for strategy-specific help
- Check [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md) for data issues
- Check [README_ENGINES.md](README_ENGINES.md) for engine configuration
