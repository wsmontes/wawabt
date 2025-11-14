# Enhanced bt_run.py - Complete Guide

## Overview

The `bt_run.py` CLI tool has been completely refactored to use the new helper engines, providing a much more powerful and user-friendly experience for running backtrader strategies.

## New Features

### 1. **CerebroRunner Integration**
- Automated Cerebro setup with intelligent defaults
- Automatic data feed creation with database-first approach
- Built-in analyzer and observer management

### 2. **Commission Presets**
- **US Markets**: `us_stocks`, `us_futures`, `us_forex`
- **Crypto**: `crypto_binance`, `crypto_coinbase`
- **International**: `brazil_stocks`, `brazil_bdr`, `latam_stocks`, `european_stocks`, `asian_stocks`
- **Zero Commission**: `zero` (for testing)

### 3. **Analyzer Presets**
- **minimal**: Returns, Sharpe, DrawDown, TimeReturn (default)
- **performance**: Full performance metrics
- **trading**: Trade analysis and statistics
- **quality**: Quality indicators
- **complete**: All analyzers

### 4. **Position Sizing**
- **fixed**: Fixed number of shares/contracts
- **percent**: Percentage of portfolio
- **allin**: All-in (100% of available cash)

### 5. **Result Management**
- **Export**: JSON/CSV export with datetime serialization
- **Database Storage**: Save results to DuckDB
- **Print Control**: Suppress output with `--no-print`

### 6. **Observer Control**
- Standard observers (Broker, Trades, BuySell) enabled by default
- Disable with `--no-observers`
- Add DrawDown observer with `--drawdown`

### 7. **Enhanced Data Management**
- **Database-First**: Always checks database before external fetch
- **Auto-Save**: Fetched data automatically saved to Parquet
- **Timezone Normalization**: All timestamps normalized to UTC
- **Deduplication**: Automatic deduplication on symbol+timestamp+source+interval

## Command-Line Options

### Required Arguments
```bash
--strategy, -s      Path to strategy file (e.g., strategies/my_strategy.py)
--symbols, -y       Symbol(s) to trade (e.g., AAPL GOOGL)
```

### Date Range
```bash
--fromdate, -f      Start date (YYYY-MM-DD), default: 1 year ago
--todate, -t        End date (YYYY-MM-DD), default: today
```

### Data Source
```bash
--source            Data source (default: yahoo_finance)
                    Choices: yahoo_finance, yahoo, binance, ccxt, alpaca, 
                             quandl, alpha_vantage, polygon
--interval, -i      Time interval (default: 1d)
```

### Database Options
```bash
--db-path           Path to backtest results database
                    (default: data/backtest_results.duckdb)
--save-results      Save backtest results to database
```

### Backtest Settings
```bash
--cash              Initial cash (default: 10000)
--commission        Commission percentage (default: 0.001 = 0.1%)
                    Ignored if --commission-preset is used
--commission-preset Use preset commission scheme
                    Choices: us_stocks, us_futures, us_forex, 
                            crypto_binance, crypto_coinbase,
                            brazil_stocks, brazil_bdr, latam_stocks,
                            european_stocks, asian_stocks, zero
```

### Strategy Parameters
```bash
--params, -p        Strategy parameters (e.g., period=20 threshold=0.5)
--optimize          Enable strategy optimization mode
```

### Position Sizing
```bash
--sizer             Position sizing method
                    Choices: fixed, percent, allin
--sizer-value       Sizer parameter value
                    - stake for fixed (default: 1)
                    - percents for percent (default: 1.0)
```

### Analyzers
```bash
--analyzer-preset   Analyzer preset to use
                    Choices: minimal, complete, performance, trading, quality
--no-analyzers      Disable all analyzers
```

### Observers
```bash
--no-observers      Disable standard observers (Broker, Trades, BuySell)
--drawdown          Add DrawDown observer
```

### Output Options
```bash
--plot              Generate plot at the end
--plot-style        Plot style (default: candlestick)
                    Choices: candlestick, bar, line
--export            Export analyzer results to file
                    Format determined by extension (.json or .csv)
--no-print          Disable printing results to console
```

## Usage Examples

### 1. Basic Run
```bash
python bt_run.py \
  --strategy strategies/sma_cross.py \
  --symbols AAPL
```

### 2. Multiple Symbols with Date Range
```bash
python bt_run.py \
  --strategy strategies/multi_symbol_portfolio.py \
  --symbols AAPL GOOGL MSFT \
  --fromdate 2024-01-01 \
  --todate 2024-12-31
```

### 3. Crypto Trading with Binance Commission
```bash
python bt_run.py \
  --strategy strategies/crypto_strategy.py \
  --symbols BTCUSDT ETHUSDT \
  --source binance \
  --interval 1h \
  --commission-preset crypto_binance
```

### 4. Custom Parameters and Performance Analyzers
```bash
python bt_run.py \
  --strategy strategies/sma_cross.py \
  --symbols AAPL \
  --params fast_period=10 slow_period=30 \
  --analyzer-preset performance
```

### 5. Export Results and Save to Database
```bash
python bt_run.py \
  --strategy strategies/my_strategy.py \
  --symbols AAPL \
  --export results.json \
  --save-results
```

### 6. Percent Sizer with Optimization
```bash
python bt_run.py \
  --strategy strategies/my_strategy.py \
  --symbols AAPL \
  --sizer percent \
  --sizer-value 10 \
  --optimize
```

### 7. Plot with Custom Style
```bash
python bt_run.py \
  --strategy strategies/my_strategy.py \
  --symbols AAPL \
  --plot \
  --plot-style candlestick
```

### 8. Silent Mode with CSV Export
```bash
python bt_run.py \
  --strategy strategies/my_strategy.py \
  --symbols AAPL GOOGL \
  --analyzer-preset complete \
  --export results.csv \
  --no-print
```

## Integration with Helper Engines

### CerebroRunner
The CLI now uses `CerebroRunner` for all Cerebro operations:
- Automated data feed creation via `add_multiple_data()`
- Strategy management via `add_strategy()`
- Analyzer setup via `add_analyzers(preset='...')`
- Result extraction and storage via `run(save_results=True)`

### AnalyzerHelper
Result management is handled by `AnalyzerHelper`:
- Automatic result extraction from strategy
- Datetime serialization for JSON/CSV export
- Database storage with metadata
- Comparison utilities

### CommissionHelper
Commission schemes are applied via `CommissionHelper`:
- Preset loading from `config/commission.json`
- Automatic broker configuration
- Multi-market support

### AutoFetchData
Data feeds are created via `AutoFetchData`:
- Database-first approach
- Auto-fetch from external sources if needed
- Timezone normalization
- Automatic save to Parquet

## Architecture Flow

```
User Command
    ↓
bt_run.py (CLI Parser)
    ↓
run_strategy(args)
    ↓
CerebroRunner.init()
    ↓
├─ CommissionHelper.apply_preset()
├─ AutoFetchData.create() × N symbols
│   ├─ Check SmartDatabaseManager
│   └─ Fetch from ConnectorEngine if needed
├─ CerebroRunner.add_strategy()
├─ AnalyzerHelper.add_preset_analyzers()
└─ CerebroRunner.run()
    ↓
├─ Extract Results (AnalyzerHelper)
├─ Save to Database (if --save-results)
├─ Export to File (if --export)
└─ Plot (if --plot)
```

## Technical Details

### Timezone Handling
All timestamps are normalized to timezone-naive UTC format when saved to the database. This ensures consistent date filtering and prevents timezone comparison issues.

### Deduplication
Market data is deduplicated based on:
- `symbol`
- `timestamp`
- `source`
- `interval`

This prevents duplicate data from being saved to the database.

### Database Structure
```
data/
├── market/                      # Market data (Parquet)
│   └── {source}/
│       └── {symbol}/
│           └── {interval}.parquet
└── backtest_results.duckdb      # Backtest results (DuckDB)
```

### Result Export Formats

#### JSON Format
```json
{
  "drawdown": {
    "len": 0,
    "drawdown": 0.0,
    "moneydown": 0.0,
    "max": {
      "len": 0.0,
      "drawdown": 0.0,
      "moneydown": 0.0
    }
  },
  "returns": {
    "rtot": 0.0,
    "ravg": 0.0,
    "rnorm": 0.0,
    "rnorm100": 0.0
  },
  "sharpe": {
    "sharperatio": null
  },
  "timereturn": {
    "2024-01-02T00:00:00": 0.0,
    "2024-01-03T00:00:00": 0.0
    ...
  }
}
```

#### CSV Format
Flattened structure with column names like:
```
drawdown_len, drawdown_drawdown, drawdown_moneydown, drawdown_max_len, ...
```

## Troubleshooting

### Issue: "No data after preparation"
**Solution**: Check that your date range matches available data. The system fetches data using start/end dates, not periods.

### Issue: "AttributeError: 'NoneType' object has no attribute 'addindicator'"
**Solution**: This occurs when using truthy checks on backtrader LineRoot objects. Use `is None` instead of `if obj:`.

### Issue: "keys must be str, int, float, bool or None, not datetime"
**Solution**: This has been fixed in the latest version. Datetime keys are now automatically converted to ISO format strings.

### Issue: Data not loading from database
**Solution**: Ensure the date range in your query matches the dates in the database. Use `--fromdate` and `--todate` explicitly.

## Performance Tips

1. **Use Database Cache**: Run once to fetch and save data, subsequent runs will be much faster
2. **Limit Date Range**: Use specific date ranges instead of fetching years of data
3. **Disable Plotting**: Use `--no-print` for automated runs
4. **Use CSV for Large Results**: CSV exports are faster than JSON for large datasets

## Next Steps

For live trading support, see:
- `docs/LIVE_TRADING.md` (coming soon)
- `engines/live_helper.py` (coming soon)

For custom strategies, see:
- `docs/STRATEGY_DEVELOPMENT.md`
- `strategies/template.py`

For advanced analyzer customization, see:
- `docs/README_ENGINES.md`
- `engines/analyzer_helper.py`
