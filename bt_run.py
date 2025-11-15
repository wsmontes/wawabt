#!/usr/bin/env python
"""
Backtrader Strategy Runner with Automatic Data Retrieval
Run backtrader strategies with seamless database and connector integration

Enhanced with:
- CerebroRunner integration for automated setup
- AnalyzerHelper for result storage
- CommissionHelper for flexible commission schemes
- Multiple sizer options
- Observer control
- Result export and storage
"""
import argparse
import sys
import os
from collections import OrderedDict
from datetime import datetime, timedelta, date
from pathlib import Path
import importlib.util

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import backtrader as bt
from backtrader import TimeFrame
from engines import (
    CerebroRunner, 
    quick_backtest,
    AnalyzerHelper,
    CommissionHelper,
    setup_commission
)


TIMEFRAME_NAME_MAP = {
    'notime': TimeFrame.NoTimeFrame,
    'days': TimeFrame.Days,
    'weeks': TimeFrame.Weeks,
    'months': TimeFrame.Months,
    'years': TimeFrame.Years,
}


def _ensure_datetime(value):
    """Normalize analyzer datetime keys to datetime objects."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
    if isinstance(value, (int, float)):
        try:
            return bt.num2date(value)
        except Exception:
            return datetime.fromtimestamp(value)
    raise ValueError(f"Unsupported datetime key: {value}")


def _get_first_strategy(results):
    if not results:
        return None
    first = results[0]
    if isinstance(first, list) and first:
        return first[0]
    return first if isinstance(first, bt.Strategy) else None


def build_monthly_breakdown(results, initial_cash):
    strat = _get_first_strategy(results)
    if strat is None or not hasattr(strat, 'analyzers'):
        return None
    timereturn = getattr(strat.analyzers, 'timereturn', None)
    if timereturn is None:
        return None
    analysis = timereturn.get_analysis()
    if not analysis:
        return None

    sorted_items = sorted(analysis.items(), key=lambda kv: _ensure_datetime(kv[0]))
    monthly_map = OrderedDict()
    for key, ret in sorted_items:
        dt = _ensure_datetime(key)
        month_key = f"{dt.year}-{dt.month:02d}"
        monthly_map.setdefault(month_key, []).append(ret)

    breakdown = []
    equity = float(initial_cash)
    for month, ret_list in monthly_map.items():
        compounded = 1.0
        for value in ret_list:
            compounded *= (1.0 + value)
        month_return = compounded - 1.0
        pnl = equity * month_return
        equity += pnl
        breakdown.append({
            'month': month,
            'return_pct': month_return * 100.0,
            'pnl': pnl,
            'equity': equity,
            'return_decimal': month_return,
        })

    return breakdown


def print_monthly_breakdown(breakdown):
    if not breakdown:
        print("[MonthlyReport] No monthly data available")
        return

    print("\n" + "-" * 70)
    print("  Monthly Performance Breakdown")
    print("-" * 70)
    print(f"{'Month':<12}{'Return %':>12}{'PnL ($)':>16}{'Equity ($)':>18}")
    print("-" * 70)
    for row in breakdown:
        print(
            f"{row['month']:<12}"
            f"{row['return_pct']:>12.2f}"
            f"{row['pnl']:>16,.2f}"
            f"{row['equity']:>18,.2f}"
        )
    print("-" * 70 + "\n")


def load_strategy_from_file(strategy_path: str):
    """
    Dynamically load a strategy class from a Python file
    
    Args:
        strategy_path: Path to the strategy file
    
    Returns:
        Strategy class or None
    """
    try:
        # Create a unique module name based on the file path
        module_name = Path(strategy_path).stem + "_module"
        
        # Load the module from file
        spec = importlib.util.spec_from_file_location(module_name, strategy_path)
        if spec is None or spec.loader is None:
            print(f"Failed to load strategy from {strategy_path}")
            return None
        
        module = importlib.util.module_from_spec(spec)
        
        # Add to sys.modules to avoid KeyError
        sys.modules[module_name] = module
        
        spec.loader.exec_module(module)
        
        # Find the strategy class (look for subclass of bt.Strategy)
        strategy_class = None
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and 
                issubclass(obj, bt.Strategy) and 
                obj != bt.Strategy):
                strategy_class = obj
                break
        
        if strategy_class is None:
            print(f"No strategy class found in {strategy_path}")
            return None
        
        print(f"✓ Loaded strategy: {strategy_class.__name__}")
        return strategy_class
        
    except Exception as e:
        print(f"Error loading strategy: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_strategy(args):
    """
    Run a backtrader strategy with automatic data retrieval using CerebroRunner
    
    Args:
        args: Command-line arguments
    """
    print("=" * 70)
    print("  Backtrader Strategy Runner - Enhanced")
    print("=" * 70)
    
    # Load strategy
    strategy_class = load_strategy_from_file(args.strategy)
    if strategy_class is None:
        return 1
    
    # Parse dates
    if args.fromdate:
        fromdate = datetime.strptime(args.fromdate, '%Y-%m-%d')
    else:
        fromdate = datetime.now() - timedelta(days=365)
    
    if args.todate:
        todate = datetime.strptime(args.todate, '%Y-%m-%d')
    else:
        todate = datetime.now()
    
    print(f"\nConfiguration:")
    print(f"  Period:      {fromdate.date()} to {todate.date()}")
    print(f"  Symbols:     {', '.join(args.symbols)}")
    print(f"  Source:      {args.source}")
    print(f"  Interval:    {args.interval}")
    print(f"  Cash:        ${args.cash:,.2f}")
    print(f"  Commission:  {args.commission_preset or f'{args.commission*100}%'}")
    
    # Initialize CerebroRunner
    runner = CerebroRunner(
        cash=args.cash,
        commission_preset=args.commission_preset,
        db_path=args.db_path
    )
    
    # Add data feeds
    print(f"\n{'─' * 70}")
    print("  Loading Data")
    print(f"{'─' * 70}")
    
    added = runner.add_multiple_data(
        symbols=args.symbols,
        fromdate=fromdate,
        todate=todate,
        source=args.source,
        interval=args.interval
    )
    
    if added == 0:
        print("✗ Failed to add any data feeds")
        return 1
    
    # Parse and add strategy parameters
    strategy_params = {}
    if args.params:
        for param in args.params:
            if '=' not in param:
                continue
            key, value = param.split('=', 1)
            # Try to convert to appropriate type
            try:
                if '.' in value:
                    value = float(value)
                elif value.isdigit():
                    value = int(value)
                elif value.lower() in ['true', 'false']:
                    value = value.lower() == 'true'
            except:
                pass  # Keep as string
            strategy_params[key] = value
    
    # Add strategy
    runner.add_strategy(strategy_class, optimize=args.optimize, **strategy_params)
    
    if strategy_params:
        print(f"\nStrategy Parameters: {strategy_params}")
    
    # Add analyzers
    if not args.no_analyzers:
        analyzer_preset = args.analyzer_preset or 'minimal'
        custom_analyzer_params = {}
        timereturn_params = {}

        timeframe_choice = (args.timereturn_timeframe or 'auto').lower()
        if timeframe_choice != 'auto':
            timeframe_value = TIMEFRAME_NAME_MAP.get(timeframe_choice)
            if timeframe_value is not None:
                timereturn_params['timeframe'] = timeframe_value

        if args.timereturn_compression:
            timereturn_params['compression'] = args.timereturn_compression

        if timereturn_params:
            custom_analyzer_params['timereturn'] = timereturn_params

        runner.add_analyzers(preset=analyzer_preset, **custom_analyzer_params)
    
    # Configure observers
    runner.add_observers(standard=not args.no_observers, drawdown=args.drawdown)
    
    # Configure sizer
    if args.sizer:
        sizer_map = {
            'fixed': bt.sizers.FixedSize,
            'percent': bt.sizers.PercentSizer,
            'allin': bt.sizers.AllInSizer,
        }
        
        sizer_class = sizer_map.get(args.sizer.lower(), bt.sizers.FixedSize)
        sizer_params = {}
        
        if args.sizer.lower() == 'fixed':
            sizer_params['stake'] = args.sizer_value
        elif args.sizer.lower() == 'percent':
            sizer_params['percents'] = args.sizer_value
        
        runner.setup_sizer(sizer_class, **sizer_params)
    
    # Run backtest
    print(f"\n{'=' * 70}")
    print("  Running Backtest")
    print(f"{'=' * 70}\n")
    
    results = runner.run(
        save_results=args.save_results,
        print_results=not args.no_print
    )

    if args.monthly_report:
        breakdown = build_monthly_breakdown(results, args.cash)
        if breakdown:
            print_monthly_breakdown(breakdown)
        else:
            print("[MonthlyReport] Unable to compute breakdown. Ensure TimeReturn analyzer is enabled.")
    
    # Export results if requested
    if args.export and results:
        strat = results[0] if results else None
        if strat is not None and hasattr(strat, 'analyzers'):
            helper = AnalyzerHelper()
            analyzer_results = helper.extract_results(strat)
            
            export_path = args.export
            export_format = Path(export_path).suffix[1:] or 'json'
            
            helper.export_results(
                analyzer_results,
                export_path,
                format=export_format
            )
    
    # Plot if requested
    if args.plot:
        runner.plot(style=args.plot_style)
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Run Backtrader strategies with automatic data retrieval - Enhanced Edition',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run strategy with single symbol
  python bt_run.py --strategy strategies/my_strategy.py --symbols AAPL
  
  # Run with multiple symbols and date range
  python bt_run.py --strategy strategies/my_strategy.py \\
      --symbols AAPL GOOGL MSFT \\
      --fromdate 2024-01-01 --todate 2024-12-31
  
  # Run with Binance crypto data and crypto commission
  python bt_run.py --strategy strategies/crypto_strategy.py \\
      --symbols BTCUSDT ETHUSDT \\
      --source binance --interval 1h \\
      --commission-preset crypto_binance
  
  # Run with custom parameters and analyzer preset
  python bt_run.py --strategy strategies/sma_cross.py \\
      --symbols AAPL \\
      --params fast_period=10 slow_period=30 \\
      --analyzer-preset performance
  
  # Run with plotting and export results
  python bt_run.py --strategy strategies/my_strategy.py \\
      --symbols AAPL --plot --export results.json
  
  # Run with percent sizer and optimization
  python bt_run.py --strategy strategies/my_strategy.py \\
      --symbols AAPL \\
      --sizer percent --sizer-value 10 \\
      --optimize
        """
    )
    
    # Required arguments
    parser.add_argument('--strategy', '-s', required=True,
                       help='Path to strategy file (e.g., strategies/my_strategy.py)')
    parser.add_argument('--symbols', '-y', nargs='+', required=True,
                       help='Symbol(s) to trade (e.g., AAPL GOOGL)')
    
    # Date range
    parser.add_argument('--fromdate', '-f',
                       help='Start date (YYYY-MM-DD), default: 1 year ago')
    parser.add_argument('--todate', '-t',
                       help='End date (YYYY-MM-DD), default: today')
    
    # Data source
    parser.add_argument('--source', default='yahoo_finance',
                       choices=['yahoo_finance', 'yahoo', 'binance', 'ccxt', 'alpaca', 'quandl', 'alpha_vantage', 'polygon'],
                       help='Data source (default: yahoo_finance)')
    parser.add_argument('--interval', '-i', default='1d',
                       help='Time interval (default: 1d)')
    
    # Database options
    parser.add_argument('--db-path',
                       help='Path to backtest results database (default: data/backtest_results.duckdb)')
    parser.add_argument('--save-results', action='store_true',
                       help='Save backtest results to database')
    
    # Backtest settings
    parser.add_argument('--cash', type=float, default=10000.0,
                       help='Initial cash (default: 10000)')
    parser.add_argument('--commission', type=float, default=0.001,
                       help='Commission percentage (default: 0.001 = 0.1%%) - ignored if --commission-preset is used')
    parser.add_argument('--commission-preset',
                       choices=['us_stocks', 'us_stocks_zero', 'us_futures', 'us_forex', 'crypto_binance', 'crypto_coinbase', 
                                'brazil_stocks', 'brazil_bdr', 'latam_stocks', 'european_stocks', 'asian_stocks', 'zero'],
                       help='Use preset commission scheme for specific market')
    
    # Strategy parameters
    parser.add_argument('--params', '-p', nargs='+',
                       help='Strategy parameters (e.g., period=20 threshold=0.5)')
    parser.add_argument('--optimize', action='store_true',
                       help='Enable strategy optimization mode')
    
    # Sizer options
    parser.add_argument('--sizer',
                       choices=['fixed', 'percent', 'allin'],
                       help='Position sizing method (default: FixedSize with stake=1)')
    parser.add_argument('--sizer-value', type=float, default=1.0,
                       help='Sizer parameter value (stake for fixed, percents for percent)')
    
    # Analyzer options
    parser.add_argument('--analyzer-preset',
                       choices=['minimal', 'complete', 'performance', 'trading', 'quality'],
                       help='Analyzer preset to use (default: minimal if not disabled)')
    parser.add_argument('--no-analyzers', action='store_true',
                       help='Disable performance analyzers')
    parser.add_argument('--timereturn-timeframe',
                       choices=['auto', 'notime', 'days', 'weeks', 'months', 'years'],
                       default='auto',
                       help='Override TimeReturn analyzer timeframe (requires TimeReturn analyzer)')
    parser.add_argument('--timereturn-compression', type=int,
                       help='Override TimeReturn analyzer compression when using intraday data')
    parser.add_argument('--monthly-report', action='store_true',
                       help='Print a month-by-month performance breakdown (requires TimeReturn analyzer)')
    
    # Observer options
    parser.add_argument('--no-observers', action='store_true',
                       help='Disable standard observers (Broker, Trades, BuySell)')
    parser.add_argument('--drawdown', action='store_true',
                       help='Add DrawDown observer')
    
    # Output options
    parser.add_argument('--plot', action='store_true',
                       help='Generate plot at the end')
    parser.add_argument('--plot-style', default='candlestick',
                       choices=['candlestick', 'bar', 'line'],
                       help='Plot style (default: candlestick)')
    parser.add_argument('--export',
                       help='Export analyzer results to file (JSON or CSV based on extension)')
    parser.add_argument('--no-print', action='store_true',
                       help='Disable printing results to console')
    
    args = parser.parse_args()
    
    # Validate strategy file exists
    if not os.path.exists(args.strategy):
        print(f"Error: Strategy file not found: {args.strategy}")
        return 1
    
    return run_strategy(args)


if __name__ == '__main__':
    sys.exit(main())
