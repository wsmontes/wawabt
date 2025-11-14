"""
Cerebro Runner - Orquestra execução completa de backtests com integração total

Features:
- Setup automatizado de Cerebro com todas as configurações
- Integração com ConnectorEngine para dados
- Aplicação automática de analyzers, observers, sizers
- Configuração de commission schemes
- Salvamento automático de resultados
- Suporte a optimization runs
- Plotting e export de resultados
"""
from datetime import datetime, time
from typing import Optional, List, Dict, Any, Type, Union
from pathlib import Path
import backtrader as bt

try:
    from .bt_data import AutoFetchData
    from .analyzer_helper import AnalyzerHelper, AnalyzerPresets
    from .commission_helper import CommissionHelper
    from .smart_db import SmartDatabaseManager
except ImportError:
    AutoFetchData = None
    AnalyzerHelper = None
    CommissionHelper = None
    SmartDatabaseManager = None


class CerebroRunner:
    """
    High-level runner para backtesting com integração completa
    """
    
    def __init__(self,
                 cash: float = 100000.0,
                 commission_preset: Optional[str] = 'us_stocks_zero',
                 db_path: Optional[str] = None):
        """
        Initialize CerebroRunner
        
        Args:
            cash: Initial cash
            commission_preset: Commission preset to use
            db_path: Path to database for storing results
        """
        self.cerebro = bt.Cerebro()
        self.cerebro.broker.setcash(cash)
        
        # Setup helpers
        self.analyzer_helper = AnalyzerHelper(db_path) if AnalyzerHelper else None
        self.commission_helper = CommissionHelper() if CommissionHelper else None
        
        # Apply commission preset
        if commission_preset and self.commission_helper:
            self.commission_helper.apply_to_broker(self.cerebro.broker, commission_preset)
        
        # Track configuration
        self.config = {
            'cash': cash,
            'commission_preset': commission_preset,
            'symbols': [],
            'strategies': [],
            'analyzers': [],
            'observers': [],
        }
        
        print(f"[CerebroRunner] Initialized with cash=${cash:,.2f}")
    
    def add_data(self,
                symbol: str,
                fromdate: Optional[datetime] = None,
                todate: Optional[datetime] = None,
                source: str = 'yahoo_finance',
                interval: str = '1d',
                name: Optional[str] = None,
                **kwargs) -> bool:
        """
        Add data feed to cerebro
        
        Args:
            symbol: Symbol to add
            fromdate: Start date
            todate: End date
            source: Data source
            interval: Time interval
            name: Name for the data feed
            **kwargs: Additional parameters for AutoFetchData
        
        Returns:
            True if data added successfully
        """
        if not AutoFetchData:
            print("[CerebroRunner] AutoFetchData not available")
            return False
        
        try:
            data_feed = AutoFetchData.create(
                symbol=symbol,
                fromdate=fromdate,
                todate=todate,
                source=source,
                interval=interval,
                **kwargs
            )
            
            if data_feed is not None:
                feed_name = name or symbol
                self.cerebro.adddata(data_feed, name=feed_name)
                self.config['symbols'].append(feed_name)
                print(f"[CerebroRunner] Added data feed: {feed_name}")
                return True
            else:
                print(f"[CerebroRunner] Failed to create data feed for {symbol}")
                return False
                
        except Exception as e:
            print(f"[CerebroRunner] Error adding data {symbol}: {e}")
            return False
    
    def add_multiple_data(self,
                         symbols: List[str],
                         fromdate: Optional[datetime] = None,
                         todate: Optional[datetime] = None,
                         source: str = 'yahoo_finance',
                         interval: str = '1d',
                         **kwargs) -> int:
        """
        Add multiple data feeds at once
        
        Args:
            symbols: List of symbols
            fromdate: Start date
            todate: End date
            source: Data source
            interval: Time interval
            **kwargs: Additional parameters
        
        Returns:
            Number of feeds added successfully
        """
        added = 0
        for symbol in symbols:
            if self.add_data(symbol, fromdate, todate, source, interval, **kwargs):
                added += 1
        
        print(f"[CerebroRunner] Added {added}/{len(symbols)} data feeds")
        return added
    
    def add_strategy(self,
                    strategy_class: Type[bt.Strategy],
                    optimize: bool = False,
                    **params) -> bool:
        """
        Add strategy to cerebro
        
        Args:
            strategy_class: Strategy class to add
            optimize: If True, use optstrategy (params should contain iterables)
            **params: Strategy parameters
        
        Returns:
            True if added successfully
        
        Examples:
            # Regular strategy
            runner.add_strategy(MyStrategy, period=20)
            
            # Optimization
            runner.add_strategy(MyStrategy, optimize=True, period=range(10, 30))
        """
        try:
            if optimize:
                self.cerebro.optstrategy(strategy_class, **params)
            else:
                self.cerebro.addstrategy(strategy_class, **params)
            
            strategy_name = strategy_class.__name__
            self.config['strategies'].append({
                'name': strategy_name,
                'params': params,
                'optimize': optimize
            })
            
            print(f"[CerebroRunner] Added strategy: {strategy_name} (optimize={optimize})")
            return True
            
        except Exception as e:
            print(f"[CerebroRunner] Error adding strategy: {e}")
            return False
    
    def add_analyzers(self, preset: str = 'minimal', **custom_params):
        """
        Add preset analyzers
        
        Args:
            preset: Preset name ('minimal', 'performance', 'trading', 'quality', 'complete')
            **custom_params: Custom parameters for specific analyzers
        """
        if not self.analyzer_helper:
            print("[CerebroRunner] AnalyzerHelper not available")
            return
        
        self.analyzer_helper.add_preset_analyzers(
            self.cerebro,
            preset=preset,
            custom_params=custom_params
        )
        self.config['analyzers'].append(preset)
    
    def add_observers(self, standard: bool = True, drawdown: bool = True):
        """
        Configure observers
        
        Args:
            standard: Include standard observers (Broker, Trades, BuySell)
            drawdown: Add DrawDown observer
        """
        if not standard:
            # Disable standard observers
            self.cerebro.stdstats = False
        
        if drawdown:
            self.cerebro.addobserver(bt.observers.DrawDown)
            self.config['observers'].append('DrawDown')
    
    def setup_sizer(self,
                   sizer_class: Type[bt.Sizer] = None,
                   **params):
        """
        Setup position sizer
        
        Args:
            sizer_class: Sizer class (default: FixedSize)
            **params: Sizer parameters
        
        Examples:
            # Fixed size
            runner.setup_sizer(bt.sizers.FixedSize, stake=10)
            
            # Percentage of portfolio
            runner.setup_sizer(bt.sizers.PercentSizer, percents=10)
        """
        if sizer_class is None:
            sizer_class = bt.sizers.FixedSize
        
        self.cerebro.addsizer(sizer_class, **params)
        print(f"[CerebroRunner] Added sizer: {sizer_class.__name__}")
    
    def run(self,
           save_results: bool = True,
           print_results: bool = True,
           **run_params) -> List[bt.Strategy]:
        """
        Run the backtest
        
        Args:
            save_results: Save results to database
            print_results: Print results to console
            **run_params: Additional parameters for cerebro.run()
        
        Returns:
            List of strategy instances
        """
        print("\n" + "="*60)
        print("  Starting Backtest")
        print("="*60)
        
        # Print configuration
        print(f"\nInitial Cash: ${self.config['cash']:,.2f}")
        print(f"Symbols: {', '.join(self.config['symbols'])}")
        print(f"Strategies: {len(self.config['strategies'])}")
        print(f"Analyzers: {', '.join(self.config['analyzers'])}")
        
        # Run backtest
        start_time = datetime.now()
        results = self.cerebro.run(**run_params)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Get final portfolio value
        final_value = self.cerebro.broker.getvalue()
        pnl = final_value - self.config['cash']
        pnl_pct = (pnl / self.config['cash']) * 100
        
        print(f"\n" + "="*60)
        print("  Backtest Complete")
        print("="*60)
        print(f"Duration: {duration:.2f}s")
        print(f"Final Value: ${final_value:,.2f}")
        print(f"P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        print("="*60 + "\n")
        
        # Process results
        if results and len(results) > 0:
            # Handle optimization vs single run
            if isinstance(results[0], list):
                # Optimization run
                print(f"[CerebroRunner] Optimization complete: {len(results)} runs")
                
                if save_results:
                    self._save_optimization_results(results)
                
            else:
                # Single strategy run
                for i, strat in enumerate(results):
                    strategy_name = strat.__class__.__name__
                    
                    # Extract analyzer results
                    if self.analyzer_helper and hasattr(strat, 'analyzers'):
                        analyzer_results = self.analyzer_helper.extract_results(strat)
                        
                        if print_results:
                            self.analyzer_helper.print_results(
                                analyzer_results,
                                title=f"{strategy_name} Results"
                            )
                        
                        if save_results:
                            self.analyzer_helper.save_results(
                                strategy_name=strategy_name,
                                symbols=self.config['symbols'],
                                results=analyzer_results,
                                parameters=self.config['strategies'][i]['params'] if i < len(self.config['strategies']) else {},
                                metadata={
                                    'initial_cash': self.config['cash'],
                                    'final_value': final_value,
                                    'pnl': pnl,
                                    'pnl_pct': pnl_pct,
                                    'duration_seconds': duration,
                                    'start_time': start_time.isoformat(),
                                    'end_time': end_time.isoformat(),
                                }
                            )
        
        return results
    
    def _save_optimization_results(self, results: List[List[bt.Strategy]]):
        """
        Save optimization results
        """
        print("[CerebroRunner] Saving optimization results...")
        
        for i, run in enumerate(results):
            for strat in run:
                if self.analyzer_helper and hasattr(strat, 'analyzers'):
                    analyzer_results = self.analyzer_helper.extract_results(strat)
                    
                    # Get strategy parameters
                    params = {name: getattr(strat.params, name) 
                             for name in dir(strat.params) 
                             if not name.startswith('_')}
                    
                    self.analyzer_helper.save_results(
                        strategy_name=f"{strat.__class__.__name__}_opt_{i}",
                        symbols=self.config['symbols'],
                        results=analyzer_results,
                        parameters=params,
                        metadata={'optimization_run': i}
                    )
    
    def plot(self,
            style: str = 'candlestick',
            **plot_params):
        """
        Plot the results
        
        Args:
            style: Plot style ('candlestick', 'line', 'bar')
            **plot_params: Additional parameters for cerebro.plot()
        """
        try:
            self.cerebro.plot(style=style, **plot_params)
            print("[CerebroRunner] Plot generated")
        except Exception as e:
            print(f"[CerebroRunner] Plot failed: {e}")


# Convenience function for quick backtesting
def quick_backtest(strategy_class: Type[bt.Strategy],
                  symbols: Union[str, List[str]],
                  fromdate: Optional[datetime] = None,
                  todate: Optional[datetime] = None,
                  cash: float = 100000.0,
                  commission: str = 'us_stocks_zero',
                  analyzers: str = 'minimal',
                  plot: bool = True,
                  **strategy_params) -> List[bt.Strategy]:
    """
    Quick function to run a backtest with minimal configuration
    
    Args:
        strategy_class: Strategy class to test
        symbols: Symbol or list of symbols
        fromdate: Start date
        todate: End date
        cash: Initial cash
        commission: Commission preset
        analyzers: Analyzer preset
        plot: Whether to plot results
        **strategy_params: Strategy parameters
    
    Returns:
        List of strategy instances
    
    Example:
        from strategies.sma_cross import SMACrossStrategy
        
        results = quick_backtest(
            SMACrossStrategy,
            symbols=['AAPL', 'GOOGL'],
            fromdate=datetime(2024, 1, 1),
            cash=50000,
            plot=True,
            fast_period=10,
            slow_period=30
        )
    """
    runner = CerebroRunner(cash=cash, commission_preset=commission)
    
    # Add data
    if isinstance(symbols, str):
        symbols = [symbols]
    
    runner.add_multiple_data(symbols, fromdate=fromdate, todate=todate)
    
    # Add strategy
    runner.add_strategy(strategy_class, **strategy_params)
    
    # Add analyzers
    runner.add_analyzers(preset=analyzers)
    
    # Run
    results = runner.run()
    
    # Plot
    if plot:
        runner.plot()
    
    return results
