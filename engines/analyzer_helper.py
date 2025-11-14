"""
Analyzer Helper - Facilita uso e armazenamento de resultados de analyzers do backtrader

Features:
- Presets de analyzers comuns (SharpeRatio, DrawDown, Returns, TradeAnalyzer, etc.)
- Salvamento automático de resultados no database
- Comparação de múltiplas estratégias
- Export para diferentes formatos (JSON, CSV, Parquet)
"""
import json
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from pathlib import Path
import backtrader as bt

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from .smart_db import SmartDatabaseManager
except ImportError:
    SmartDatabaseManager = None


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


class AnalyzerPresets:
    """
    Presets de analyzers comuns para backtesting
    """
    
    # Analyzers de Performance
    PERFORMANCE = [
        ('returns', bt.analyzers.Returns),
        ('sharpe', bt.analyzers.SharpeRatio),
        ('drawdown', bt.analyzers.DrawDown),
        ('timereturn', bt.analyzers.TimeReturn),
    ]
    
    # Analyzers de Trading
    TRADING = [
        ('trades', bt.analyzers.TradeAnalyzer),
        ('transactions', bt.analyzers.Transactions),
        ('positions', bt.analyzers.PositionsValue),
    ]
    
    # Analyzers de Qualidade
    QUALITY = [
        ('sqn', bt.analyzers.SQN),  # System Quality Number
        ('vwr', bt.analyzers.VWR),  # Variability-Weighted Return
    ]
    
    # Set completo para análise profunda
    COMPLETE = PERFORMANCE + TRADING + QUALITY
    
    # Set mínimo para análise rápida
    MINIMAL = [
        ('returns', bt.analyzers.Returns),
        ('sharpe', bt.analyzers.SharpeRatio),
        ('drawdown', bt.analyzers.DrawDown),
        ('trades', bt.analyzers.TradeAnalyzer),
    ]


class AnalyzerHelper:
    """
    Helper para gerenciar analyzers e salvar resultados
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize AnalyzerHelper
        
        Args:
            db_path: Path to database for storing results
        """
        self.db = None
        self.db_path = db_path or 'data/backtest_results.duckdb'
        
        if SmartDatabaseManager:
            try:
                self.db = SmartDatabaseManager(self.db_path)
                print(f"[AnalyzerHelper] Database initialized: {self.db_path}")
            except Exception as e:
                print(f"[AnalyzerHelper] Failed to initialize database: {e}")
    
    @staticmethod
    def add_preset_analyzers(cerebro: bt.Cerebro, 
                            preset: str = 'minimal',
                            custom_params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Add preset analyzers to Cerebro
        
        Args:
            cerebro: Cerebro instance
            preset: Preset name ('minimal', 'performance', 'trading', 'quality', 'complete')
            custom_params: Custom parameters for specific analyzers
                          Example: {'sharpe': {'timeframe': bt.TimeFrame.Years}}
        
        Returns:
            Dictionary mapping analyzer names to their references
        
        Example:
            cerebro = bt.Cerebro()
            analyzers = AnalyzerHelper.add_preset_analyzers(
                cerebro, 
                preset='complete',
                custom_params={'sharpe': {'riskfreerate': 0.01}}
            )
        """
        preset_map = {
            'minimal': AnalyzerPresets.MINIMAL,
            'performance': AnalyzerPresets.PERFORMANCE,
            'trading': AnalyzerPresets.TRADING,
            'quality': AnalyzerPresets.QUALITY,
            'complete': AnalyzerPresets.COMPLETE,
        }
        
        if preset not in preset_map:
            print(f"[AnalyzerHelper] Unknown preset '{preset}', using 'minimal'")
            preset = 'minimal'
        
        analyzer_list = preset_map[preset]
        custom_params = custom_params or {}
        
        added_analyzers = {}
        
        for name, analyzer_cls in analyzer_list:
            params = custom_params.get(name, {})
            cerebro.addanalyzer(analyzer_cls, _name=name, **params)
            added_analyzers[name] = analyzer_cls
            print(f"[AnalyzerHelper] Added analyzer: {name}")
        
        return added_analyzers
    
    def extract_results(self, strat: bt.Strategy) -> Dict[str, Any]:
        """
        Extract all analyzer results from a strategy
        
        Args:
            strat: Strategy instance after backtest run
        
        Returns:
            Dictionary with all analyzer results
        """
        results = {}
        
        # List of method names to skip (these are not analyzers)
        skip_methods = {'append', 'getbyname', 'getitems', 'getnames', 'getanalyzers', '_getrecurse'}
        
        for name in dir(strat.analyzers):
            if not name.startswith('_') and name not in skip_methods:
                analyzer = getattr(strat.analyzers, name)
                # Check if it's actually an analyzer (has get_analysis method)
                if hasattr(analyzer, 'get_analysis'):
                    try:
                        analysis = analyzer.get_analysis()
                        results[name] = self._serialize_analysis(analysis)
                    except Exception as e:
                        print(f"[AnalyzerHelper] Failed to extract {name}: {e}")
                        results[name] = None
        
        return results
    
    def _serialize_analysis(self, analysis: Any) -> Any:
        """
        Convert analyzer results to JSON-serializable format
        """
        if isinstance(analysis, dict):
            # Convert datetime keys to ISO format strings
            serialized = {}
            for k, v in analysis.items():
                if isinstance(k, (datetime, date)):
                    key = k.isoformat()
                else:
                    key = k
                serialized[key] = self._serialize_analysis(v)
            return serialized
        elif isinstance(analysis, (list, tuple)):
            return [self._serialize_analysis(item) for item in analysis]
        elif hasattr(analysis, '_asdict'):  # Named tuple
            return self._serialize_analysis(analysis._asdict())
        elif isinstance(analysis, (datetime, date)):
            return analysis.isoformat()
        elif pd and isinstance(analysis, pd.Timestamp):
            return analysis.isoformat()
        else:
            return analysis
    
    def save_results(self,
                    strategy_name: str,
                    symbols: List[str],
                    results: Dict[str, Any],
                    parameters: Optional[Dict] = None,
                    metadata: Optional[Dict] = None) -> bool:
        """
        Save analyzer results to database
        
        Args:
            strategy_name: Name of the strategy
            symbols: List of symbols tested
            results: Analyzer results from extract_results()
            parameters: Strategy parameters used
            metadata: Additional metadata (start_date, end_date, etc.)
        
        Returns:
            True if saved successfully
        """
        if not self.db:
            print("[AnalyzerHelper] No database available")
            return False
        
        try:
            # Prepare record
            record = {
                'timestamp': datetime.now().isoformat(),
                'strategy_name': strategy_name,
                'symbols': ','.join(symbols) if isinstance(symbols, list) else symbols,
                'parameters': json.dumps(parameters) if parameters else '{}',
                'results': json.dumps(results),
                'metadata': json.dumps(metadata) if metadata else '{}',
            }
            
            # Create DataFrame
            if pd:
                df = pd.DataFrame([record])
                
                # Save to database
                self.db.save_backtest_results(df)
                print(f"[AnalyzerHelper] Results saved for {strategy_name}")
                return True
            else:
                print("[AnalyzerHelper] Pandas not available")
                return False
                
        except Exception as e:
            print(f"[AnalyzerHelper] Failed to save results: {e}")
            return False
    
    def export_results(self,
                      results: Dict[str, Any],
                      output_path: str,
                      format: str = 'json') -> bool:
        """
        Export results to file
        
        Args:
            results: Analyzer results
            output_path: Output file path
            format: Export format ('json', 'csv')
        
        Returns:
            True if exported successfully
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == 'json':
                with open(output_path, 'w') as f:
                    json.dump(results, f, indent=2, cls=DateTimeEncoder)
            
            elif format == 'csv' and pd:
                # Flatten results for CSV
                flat_results = self._flatten_dict(results)
                df = pd.DataFrame([flat_results])
                df.to_csv(output_path, index=False)
            
            else:
                print(f"[AnalyzerHelper] Unsupported format: {format}")
                return False
            
            print(f"[AnalyzerHelper] Results exported to {output_path}")
            return True
            
        except Exception as e:
            print(f"[AnalyzerHelper] Export failed: {e}")
            return False
    
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """
        Flatten nested dictionary for CSV export
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def compare_strategies(self, 
                          results_list: List[Dict[str, Any]],
                          strategy_names: List[str]) -> Optional[pd.DataFrame]:
        """
        Compare results from multiple strategy runs
        
        Args:
            results_list: List of analyzer results
            strategy_names: List of strategy names
        
        Returns:
            DataFrame with comparison
        """
        if not pd:
            print("[AnalyzerHelper] Pandas not available")
            return None
        
        try:
            comparison_data = []
            
            for name, results in zip(strategy_names, results_list):
                flat_results = self._flatten_dict(results)
                flat_results['strategy'] = name
                comparison_data.append(flat_results)
            
            df = pd.DataFrame(comparison_data)
            return df
            
        except Exception as e:
            print(f"[AnalyzerHelper] Comparison failed: {e}")
            return None
    
    def print_results(self, results: Dict[str, Any], title: str = "Backtest Results"):
        """
        Print analyzer results in a readable format
        
        Args:
            results: Analyzer results
            title: Title for the output
        """
        print("\n" + "="*60)
        print(f"  {title}")
        print("="*60)
        
        for analyzer_name, analysis in results.items():
            print(f"\n{analyzer_name.upper()}:")
            print("-" * 40)
            self._print_nested(analysis, indent=2)
        
        print("\n" + "="*60 + "\n")
    
    def _print_nested(self, obj: Any, indent: int = 0):
        """
        Recursively print nested structures
        """
        prefix = " " * indent
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, (dict, list)):
                    print(f"{prefix}{key}:")
                    self._print_nested(value, indent + 2)
                else:
                    print(f"{prefix}{key}: {value}")
        
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                print(f"{prefix}[{i}]:")
                self._print_nested(item, indent + 2)
        
        else:
            print(f"{prefix}{obj}")


# Extension to SmartDatabaseManager for backtest results
def _extend_smart_db():
    """
    Extend SmartDatabaseManager with backtest results storage
    """
    if SmartDatabaseManager is None:
        return
    
    def save_backtest_results(self, df: pd.DataFrame) -> bool:
        """
        Save backtest results to database
        """
        try:
            table_name = 'backtest_results'
            
            # Ensure table exists
            self.conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    timestamp VARCHAR,
                    strategy_name VARCHAR,
                    symbols VARCHAR,
                    parameters VARCHAR,
                    results VARCHAR,
                    metadata VARCHAR,
                    PRIMARY KEY (timestamp, strategy_name, symbols)
                )
            """)
            
            # Insert data
            self.conn.execute(f"""
                INSERT OR REPLACE INTO {table_name}
                SELECT * FROM df
            """)
            
            print(f"[SmartDB] Saved {len(df)} backtest result(s)")
            return True
            
        except Exception as e:
            print(f"[SmartDB] Failed to save backtest results: {e}")
            return False
    
    # Add method to class
    SmartDatabaseManager.save_backtest_results = save_backtest_results


# Execute extension
_extend_smart_db()
