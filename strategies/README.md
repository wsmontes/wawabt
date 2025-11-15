# Backtrader Strategies

This folder contains backtrader strategy implementations with seamless data integration.

## Available Strategies

### 1. SMA Cross Strategy (`sma_cross.py`)
Simple Moving Average crossover strategy - buy when fast SMA crosses above slow SMA, sell when it crosses below.

**Parameters:**
- `fast_period`: Fast SMA period (default: 10)
- `slow_period`: Slow SMA period (default: 30)

**Usage:**
```bash
# Run with default parameters
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL

# Run with custom parameters
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --params fast_period=5 slow_period=20

# Run with multiple symbols (each gets same strategy)
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL GOOGL MSFT
```

### 2. RSI Mean Reversion (`rsi_meanreversion.py`)
RSI-based mean reversion strategy - buy when oversold, sell when overbought.

**Parameters:**
- `rsi_period`: RSI calculation period (default: 14)
- `rsi_oversold`: Oversold threshold (default: 30)
- `rsi_overbought`: Overbought threshold (default: 70)

**Usage:**
```bash
# Run with default parameters
python bt_run.py --strategy strategies/rsi_meanreversion.py --symbols AAPL

# Run with custom RSI levels
python bt_run.py --strategy strategies/rsi_meanreversion.py --symbols AAPL \
    --params rsi_oversold=25 rsi_overbought=75

# Run on crypto
python bt_run.py --strategy strategies/rsi_meanreversion.py --symbols BTCUSDT \
    --source binance --interval 1h
```

### 3. Multi-Symbol Portfolio (`multi_symbol_portfolio.py`)
Portfolio strategy that trades multiple symbols with momentum-based rotation.

**Parameters:**
- `momentum_period`: Lookback for momentum (default: 20)
- `rebalance_days`: Days between rebalancing (default: 30)
- `top_n`: Number of top stocks to hold (default: 3)

**Usage:**
```bash
# Run with tech stocks
python bt_run.py --strategy strategies/multi_symbol_portfolio.py \
    --symbols AAPL GOOGL MSFT AMZN TSLA \
    --cash 100000

# Run with custom parameters
python bt_run.py --strategy strategies/multi_symbol_portfolio.py \
    --symbols AAPL GOOGL MSFT AMZN TSLA NVDA META \
    --params top_n=4 rebalance_days=14 \
    --cash 100000
```

### 4. Regime-Adaptive Rotation (`regime_adaptive_rotation.py`)
Adaptive multi-factor strategy that ranks symbols using trend, momentum, and volatility filters, then allocates capital with ATR-based position sizing and dynamic stops.

**Parameters:**
- `fast_period`: Fast EMA period for trend signal (default: 50)
- `slow_period`: Slow EMA period (default: 200)
- `roc_period`: Rate-of-change lookback for momentum (default: 63)
- `atr_period`: ATR window for volatility sizing (default: 20)
- `max_positions`: Maximum concurrent holdings (default: 4)
- `rebalance_days`: Bars between ranking cycles (default: 5)
- `risk_per_trade`: Fraction of equity risked per position (default: 0.02)
- `atr_stop_multiple`: ATR multiple for trailing stop (default: 2.5)
- `take_profit`: Fractional profit target relative to entry (default: 0.10)

**Usage:**
```bash
# Run on core mega-cap symbols with 2-year window
python bt_run.py --strategy strategies/regime_adaptive_rotation.py \
    --symbols AAPL MSFT GOOGL AMZN META NVDA TSLA JPM \
    --fromdate 2023-11-14 --todate 2025-11-14 \
    --cash 100000 --commission 0.0005

# Tighten rotation frequency and cap risk-per-trade
python bt_run.py --strategy strategies/regime_adaptive_rotation.py \
    --symbols AAPL MSFT NVDA TSLA \
    --params rebalance_days=3 risk_per_trade=0.015 max_positions=3
```

### 5. Template (`template.py`)
Empty template for creating your own strategies.

## Creating Your Own Strategy

### Method 1: Copy Template
```bash
# Copy template
cp strategies/template.py strategies/my_strategy.py

# Edit the file and implement your logic
# Then run it:
python bt_run.py --strategy strategies/my_strategy.py --symbols AAPL
```

### Method 2: From Scratch

Create a new file in `strategies/` folder:

```python
import backtrader as bt

class MyCustomStrategy(bt.Strategy):
    params = (
        ('my_param', 10),
    )
    
    def __init__(self):
        # Initialize indicators
        self.sma = bt.indicators.SMA(self.datas[0], period=self.params.my_param)
    
    def next(self):
        # Your trading logic here
        if not self.position:
            if self.data.close[0] > self.sma[0]:
                self.buy()
        else:
            if self.data.close[0] < self.sma[0]:
                self.sell()
```

## Running Strategies

### Basic Usage

```bash
# Simple run
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL

# With date range
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --fromdate 2024-01-01 --todate 2024-12-31

# With plotting
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL --plot
```

### Data Sources

```bash
# Yahoo Finance (default)
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL

# Binance crypto
python bt_run.py --strategy strategies/sma_cross.py --symbols BTCUSDT \
    --source binance --interval 1h

# CCXT (any exchange)
python bt_run.py --strategy strategies/sma_cross.py --symbols BTC/USDT \
    --source ccxt --interval 1d

# Alpaca
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --source alpaca --interval 1Day
```

### Custom Parameters

```bash
# Pass parameters to strategy
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --params fast_period=5 slow_period=20 printlog=false

# Multiple parameters
python bt_run.py --strategy strategies/rsi_meanreversion.py --symbols AAPL \
    --params rsi_period=14 rsi_oversold=30 rsi_overbought=70
```

### Portfolio Settings

```bash
# Set initial cash
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --cash 50000

# Set commission
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --commission 0.002  # 0.2%
```

### Performance Analysis

```bash
# Run with full analysis
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL

# Disable analyzers for faster runs
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --no-analyzers
```

## Automatic Data Management

All strategies automatically:
1. ✅ **Check database first** - Load existing data from local database
2. ✅ **Auto-fetch if missing** - Fetch from connector if data not available
3. ✅ **Auto-save** - Save fetched data to database for future use
4. ✅ **Handle multiple sources** - Yahoo, Binance, CCXT, Alpaca, etc.

You don't need to worry about data management - just run your strategy!

## Strategy Development Tips

### 1. Start with Template
```bash
cp strategies/template.py strategies/my_new_strategy.py
```

### 2. Test Locally First
```python
# Add test code at bottom of your strategy file
if __name__ == '__main__':
    # Test code here
    pass
```

Run directly:
```bash
python strategies/my_new_strategy.py
```

### 3. Use Built-in Indicators
```python
# Moving Averages
self.sma = bt.indicators.SMA(period=20)
self.ema = bt.indicators.EMA(period=20)

# Oscillators
self.rsi = bt.indicators.RSI(period=14)
self.macd = bt.indicators.MACD()
self.stoch = bt.indicators.Stochastic()

# Volatility
self.bbands = bt.indicators.BollingerBands()
self.atr = bt.indicators.ATR(period=14)

# Volume
self.volume_sma = bt.indicators.SMA(self.data.volume, period=20)

# Crossovers
self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)
```

### 4. Add Logging
```python
def log(self, txt, dt=None):
    if self.params.printlog:
        dt = dt or self.datas[0].datetime.date(0)
        print(f'[{dt.isoformat()}] {txt}')

def next(self):
    self.log(f'Close: {self.data.close[0]:.2f}')
```

### 5. Handle Multiple Symbols
```python
def __init__(self):
    # Create indicators for each data feed
    self.smas = {}
    for i, d in enumerate(self.datas):
        self.smas[d] = bt.indicators.SMA(d, period=20)

def next(self):
    for d in self.datas:
        if self.data.close[0] > self.smas[d][0]:
            self.buy(data=d)
```

### 6. Use Analyzers
```python
# In your run code
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

results = cerebro.run()
strat = results[0]

# Access results
sharpe = strat.analyzers.sharpe.get_analysis()
drawdown = strat.analyzers.drawdown.get_analysis()
```

## Common Patterns

### Pattern 1: Simple Entry/Exit
```python
def next(self):
    if not self.position:
        if self.buy_signal():
            self.buy()
    else:
        if self.sell_signal():
            self.sell()
```

### Pattern 2: Stop Loss / Take Profit
```python
def __init__(self):
    self.stop_loss_pct = 0.02  # 2%
    self.take_profit_pct = 0.05  # 5%

def next(self):
    if self.position:
        pnl_pct = (self.data.close[0] - self.buyprice) / self.buyprice
        if pnl_pct <= -self.stop_loss_pct or pnl_pct >= self.take_profit_pct:
            self.sell()
```

### Pattern 3: Position Sizing
```python
def next(self):
    if not self.position:
        if self.buy_signal():
            # Risk 1% of portfolio
            risk_amount = self.broker.getvalue() * 0.01
            size = int(risk_amount / self.data.close[0])
            self.buy(size=size)
```

### Pattern 4: Time-based Exits
```python
def __init__(self):
    self.entry_bar = None
    self.hold_period = 10

def next(self):
    if not self.position:
        if self.buy_signal():
            self.buy()
            self.entry_bar = len(self)
    else:
        if len(self) - self.entry_bar >= self.hold_period:
            self.sell()
```

## Troubleshooting

### No Data Available
```bash
# Check if data exists in database
python -m engines.connector query --sql "SELECT * FROM market_data LIMIT 10"

# Force fetch from connector
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL --no-db
```

### Strategy Not Loading
```bash
# Check strategy file has a class that extends bt.Strategy
grep "class.*bt.Strategy" strategies/my_strategy.py

# Check for syntax errors
python strategies/my_strategy.py
```

### Parameter Errors
```bash
# Check parameter names in strategy file
grep "params = " strategies/my_strategy.py

# Pass parameters correctly
python bt_run.py --strategy strategies/sma_cross.py --symbols AAPL \
    --params fast_period=10 slow_period=30
```

## Advanced Topics

### Optimization
```python
# Run parameter optimization
cerebro.optstrategy(MyStrategy, fast_period=range(5, 20), slow_period=range(20, 50))
```

### Walk-Forward Analysis
```python
# Implement walk-forward testing by running multiple backtests with rolling windows
```

### Live Trading Integration
```python
# Use Cerebro with live feeds (requires additional setup)
cerebro.adddata(LiveDataFeed(...))
```

## Resources

- [Backtrader Documentation](https://www.backtrader.com/docu/)
- [Backtrader Indicators](https://www.backtrader.com/docu/indautoref/)
- [Example Strategies](https://github.com/mementum/backtrader/tree/master/samples)

## Contributing

To add your strategy to this repository:
1. Create your strategy file in `strategies/`
2. Add documentation to this README
3. Test with multiple symbols and date ranges
4. Submit a pull request
