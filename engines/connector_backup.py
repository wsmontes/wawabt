"""
Connector Engine for multiple data sources
Supports: CCXT, Alpaca, Binance, and Yahoo Finance
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

try:
    from .database import DatabaseEngine
    from .smart_db import SmartDatabaseManager
except ImportError:
    DatabaseEngine = None
    SmartDatabaseManager = None

try:
    import ccxt
except ImportError:
    ccxt = None

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame
except ImportError:
    StockHistoricalDataClient = None

try:
    from binance.client import Client as BinanceClient
    from binance.exceptions import BinanceAPIException
except ImportError:
    BinanceClient = None

try:
    import yfinance as yf
except ImportError:
    yf = None


class ConnectorEngine:
    """
    Multi-source data connector for financial market data
    """
    
    def __init__(self, config_path: str = "config/connector.json", 
                 use_database: bool = True,
                 db_config_path: str = "config/database.json",
                 use_smart_db: bool = True):
        """
        Initialize the connector engine
        
        Args:
            config_path: Path to the connector configuration JSON file
            use_database: Whether to enable database integration
            db_config_path: Path to database configuration
            use_smart_db: Use SmartDatabaseManager (recommended) vs legacy DatabaseEngine
        """
        self.config = self._load_config(config_path)
        self.connections = {}
        
        # Initialize database if enabled
        self.db = None
        self.use_database = use_database
        if use_database:
            if use_smart_db and SmartDatabaseManager is not None:
                try:
                    self.db = SmartDatabaseManager(db_config_path)
                    print("Smart Database integration enabled for Connector")
                except Exception as e:
                    print(f"Failed to initialize Smart Database: {e}")
                    self.db = None
            elif DatabaseEngine is not None:
                try:
                    self.db = DatabaseEngine(db_config_path)
                    print("Database integration enabled for Connector")
                except Exception as e:
                    print(f"Failed to initialize database: {e}")
                    self.db = None
        
        # Initialize connections based on available libraries
        self._init_ccxt()
        self._init_alpaca()
        self._init_binance()
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file {config_path} not found, using defaults")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "ccxt": {
                "exchanges": ["binance"],
                "default_exchange": "binance",
                "rate_limit": True
            },
            "alpaca": {
                "base_url": "https://paper-api.alpaca.markets",
                "api_key": "",
                "api_secret": ""
            },
            "binance": {
                "api_key": "",
                "api_secret": "",
                "testnet": False
            },
            "yahoo_finance": {
                "timeout": 30
            },
            "settings": {
                "retry_attempts": 3,
                "backoff_factor": 2
            }
        }
    
    def _init_ccxt(self):
        """Initialize CCXT exchange connections"""
        if ccxt is None:
            print("CCXT not installed. Install with: pip install ccxt")
            return
        
        ccxt_config = self.config.get("ccxt", {})
        default_exchange = ccxt_config.get("default_exchange", "binance")
        
        try:
            exchange_class = getattr(ccxt, default_exchange)
            self.connections['ccxt'] = exchange_class({
                'enableRateLimit': ccxt_config.get("rate_limit", True),
                'timeout': ccxt_config.get("timeout", 30000),
                'apiKey': ccxt_config.get("api_key", ""),
                'secret': ccxt_config.get("api_secret", "")
            })
            print(f"CCXT {default_exchange} initialized")
        except Exception as e:
            print(f"Failed to initialize CCXT: {e}")
    
    def _init_alpaca(self):
        """Initialize Alpaca connection"""
        if StockHistoricalDataClient is None:
            print("Alpaca not installed. Install with: pip install alpaca-py")
            return
        
        alpaca_config = self.config.get("alpaca", {})
        api_key = alpaca_config.get("api_key", "")
        api_secret = alpaca_config.get("api_secret", "")
        
        if api_key and api_secret:
            try:
                self.connections['alpaca'] = StockHistoricalDataClient(
                    api_key=api_key,
                    secret_key=api_secret
                )
                print("Alpaca initialized")
            except Exception as e:
                print(f"Failed to initialize Alpaca: {e}")
        else:
            print("Alpaca API credentials not provided in config")
    
    def _init_binance(self):
        """Initialize Binance connection"""
        if BinanceClient is None:
            print("Binance not installed. Install with: pip install python-binance")
            return
        
        binance_config = self.config.get("binance", {})
        api_key = binance_config.get("api_key", "")
        api_secret = binance_config.get("api_secret", "")
        
        try:
            self.connections['binance'] = BinanceClient(
                api_key=api_key,
                api_secret=api_secret,
                testnet=binance_config.get("testnet", False)
            )
            print("Binance initialized")
        except Exception as e:
            print(f"Failed to initialize Binance: {e}")
    
    # CCXT Methods
    def get_ccxt_markets(self, exchange: Optional[str] = None) -> List[str]:
        """Get list of available markets from CCXT exchange"""
        if 'ccxt' not in self.connections:
            raise RuntimeError("CCXT not initialized")
        
        exchange_conn = self.connections['ccxt']
        markets = exchange_conn.load_markets()
        return list(markets.keys())
    
    def get_ccxt_ohlcv(self, symbol: str, timeframe: str = '1d', 
                       since: Optional[int] = None, limit: int = 100,
                       save_to_db: bool = True) -> pd.DataFrame:
        """
        Get OHLCV data from CCXT exchange
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '1m', '5m', '1h', '1d')
            since: Timestamp in milliseconds
            limit: Number of candles to fetch
            save_to_db: Whether to save data to database
        
        Returns:
            DataFrame with OHLCV data
        """
        if 'ccxt' not in self.connections:
            raise RuntimeError("CCXT not initialized")
        
        exchange = self.connections['ccxt']
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since, limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['symbol'] = symbol
        df['source'] = 'ccxt'
        df['timeframe'] = timeframe
        
        # Save to database if enabled
        if save_to_db and self.db:
            try:
                # Use smart database manager methods
                if hasattr(self.db, 'store_market_data'):
                    self.db.store_market_data(df, source='ccxt', symbol=symbol, interval=timeframe)
                else:
                    # Fallback to legacy database
                    table_name = f"ccxt_{symbol.replace('/', '_')}_{timeframe}"
                    self.db.insert_dataframe(table_name, df, if_exists='append')
                    filename = f"ccxt_{symbol.replace('/', '_')}_{timeframe}"
                    self.db.save_to_parquet(df, filename)
                print(f"Data saved to database: {symbol}")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return df
    
    # Alpaca Methods
    def get_alpaca_bars(self, symbol: str, start: datetime, end: datetime,
                        timeframe: str = '1Day', save_to_db: bool = True) -> pd.DataFrame:
        """
        Get bar data from Alpaca
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start: Start datetime
            end: End datetime
            timeframe: Timeframe (e.g., '1Min', '1Hour', '1Day')
            save_to_db: Whether to save data to database
        
        Returns:
            DataFrame with bar data
        """
        if 'alpaca' not in self.connections:
            raise RuntimeError("Alpaca not initialized")
        
        # Map timeframe string to Alpaca TimeFrame
        timeframe_map = {
            '1Min': TimeFrame.Minute,
            '5Min': TimeFrame.Minute * 5,
            '15Min': TimeFrame.Minute * 15,
            '1Hour': TimeFrame.Hour,
            '1Day': TimeFrame.Day,
        }
        
        tf = timeframe_map.get(timeframe, TimeFrame.Day)
        
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end
        )
        
        bars = self.connections['alpaca'].get_stock_bars(request_params)
        df = bars.df.reset_index()
        df['source'] = 'alpaca'
        
        # Save to database if enabled
        if save_to_db and self.db:
            try:
                if hasattr(self.db, 'store_market_data'):
                    self.db.store_market_data(df, source='alpaca', symbol=symbol, interval=timeframe)
                else:
                    table_name = f"alpaca_{symbol}_{timeframe}"
                    self.db.insert_dataframe(table_name, df, if_exists='append')
                    filename = f"alpaca_{symbol}_{timeframe}"
                    self.db.save_to_parquet(df, filename)
                print(f"Data saved to database: {symbol}")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return df
    
    # Binance Methods
    def get_binance_klines(self, symbol: str, interval: str = '1d',
                          start_str: Optional[str] = None, 
                          end_str: Optional[str] = None,
                          limit: int = 500, save_to_db: bool = True) -> pd.DataFrame:
        """
        Get kline/candlestick data from Binance
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT')
            interval: Kline interval (e.g., '1m', '5m', '1h', '1d')
            start_str: Start date string (e.g., "1 Jan, 2023")
            end_str: End date string
            limit: Number of klines to fetch (max 1000)
            save_to_db: Whether to save data to database
        
        Returns:
            DataFrame with kline data
        """
        if 'binance' not in self.connections:
            raise RuntimeError("Binance not initialized")
        
        client = self.connections['binance']
        
        try:
            klines = client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_str=start_str,
                end_str=end_str,
                limit=limit
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['symbol'] = symbol
            df['source'] = 'binance'
            df['interval'] = interval
            
            # Convert price columns to float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            result_df = df[['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'source', 'interval']]
            
            # Save to database if enabled
            if save_to_db and self.db:
                try:
                    if hasattr(self.db, 'store_market_data'):
                        self.db.store_market_data(result_df, source='binance', symbol=symbol, interval=interval)
                    else:
                        table_name = f"binance_{symbol}_{interval}"
                        self.db.insert_dataframe(table_name, result_df, if_exists='append')
                        filename = f"binance_{symbol}_{interval}"
                        self.db.save_to_parquet(result_df, filename)
                    print(f"Data saved to database: {symbol}")
                except Exception as e:
                    print(f"Failed to save to database: {e}")
            
            return result_df
            
        except BinanceAPIException as e:
            print(f"Binance API error: {e}")
            raise
    
    # Yahoo Finance Methods
    def get_yahoo_data(self, symbol: str, start: Optional[str] = None,
                      end: Optional[str] = None, period: str = '1mo',
                      interval: str = '1d', save_to_db: bool = True) -> pd.DataFrame:
        """
        Get data from Yahoo Finance
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'MSFT')
            start: Start date string (YYYY-MM-DD)
            end: End date string (YYYY-MM-DD)
            period: Period to download (e.g., '1d', '5d', '1mo', '1y', 'max')
            interval: Data interval (e.g., '1m', '5m', '1h', '1d', '1wk', '1mo')
            save_to_db: Whether to save data to database
        
        Returns:
            DataFrame with price data
        """
        if yf is None:
            raise RuntimeError("yfinance not installed. Install with: pip install yfinance")
        
        ticker = yf.Ticker(symbol)
        
        if start and end:
            df = ticker.history(start=start, end=end, interval=interval)
        else:
            df = ticker.history(period=period, interval=interval)
        
        df = df.reset_index()
        df.columns = df.columns.str.lower()
        
        if 'date' in df.columns:
            df.rename(columns={'date': 'timestamp'}, inplace=True)
        elif 'datetime' in df.columns:
            df.rename(columns={'datetime': 'timestamp'}, inplace=True)
        
        df['symbol'] = symbol
        df['source'] = 'yahoo_finance'
        df['interval'] = interval
        
        result_df = df[['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'source', 'interval']]
        
        # Save to database if enabled
        if save_to_db and self.db:
            try:
                if hasattr(self.db, 'store_market_data'):
                    self.db.store_market_data(result_df, source='yahoo_finance', symbol=symbol, interval=interval)
                else:
                    table_name = f"yahoo_{symbol}_{interval}"
                    self.db.insert_dataframe(table_name, result_df, if_exists='append')
                    filename = f"yahoo_{symbol}_{interval}"
                    self.db.save_to_parquet(result_df, filename)
                print(f"Data saved to database: {symbol}")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return result_df
    
    def get_yahoo_info(self, symbol: str) -> Dict[str, Any]:
        """Get ticker information from Yahoo Finance"""
        if yf is None:
            raise RuntimeError("yfinance not installed")
        
        ticker = yf.Ticker(symbol)
        return ticker.info
    
    # Utility Methods
    def get_available_sources(self) -> List[str]:
        """Get list of available data sources"""
        sources = []
        if 'ccxt' in self.connections:
            sources.append('ccxt')
        if 'alpaca' in self.connections:
            sources.append('alpaca')
        if 'binance' in self.connections:
            sources.append('binance')
        if yf is not None:
            sources.append('yahoo_finance')
        return sources
    
    def query_saved_data(self, table_name: str, sql_filter: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Query saved data from database
        
        Args:
            table_name: Name of the table to query
            sql_filter: Optional SQL WHERE clause filter
        
        Returns:
            DataFrame with query results or None if database not available
        """
        if not self.db:
            print("Database not initialized")
            return None
        
        try:
            if sql_filter:
                return self.db.query(f"SELECT * FROM {table_name} WHERE {sql_filter}")
            else:
                return self.db.query(f"SELECT * FROM {table_name}")
        except Exception as e:
            print(f"Query failed: {e}")
            return None
    
    def list_saved_tables(self) -> List[str]:
        """List all saved data tables"""
        if not self.db:
            return []
        return self.db.list_tables()
    
    def list_saved_parquet_files(self) -> List[str]:
        """List all saved parquet files"""
        if not self.db:
            return []
        return self.db.list_parquet_files()
    
    def close(self):
        """Close all connections"""
        if 'ccxt' in self.connections:
            try:
                self.connections['ccxt'].close()
            except:
                pass
        
        if self.db:
            self.db.close()
        
        print("Connections closed")


def main():
    """CLI interface for connector engine"""
    import argparse
    from datetime import datetime, timedelta
    
    parser = argparse.ArgumentParser(description='Connector Engine CLI for financial data sources')
    parser.add_argument('--config', default='config/connector.json', help='Path to config file')
    parser.add_argument('--no-db', action='store_true', help='Disable database integration')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List sources command
    subparsers.add_parser('list-sources', help='List available data sources')
    
    # Yahoo Finance command
    yahoo_parser = subparsers.add_parser('yahoo', help='Get data from Yahoo Finance')
    yahoo_parser.add_argument('symbol', help='Stock symbol (e.g., AAPL)')
    yahoo_parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
    yahoo_parser.add_argument('--end', help='End date (YYYY-MM-DD)')
    yahoo_parser.add_argument('--period', default='1mo', help='Period (1d, 5d, 1mo, 1y, max)')
    yahoo_parser.add_argument('--interval', default='1d', help='Interval (1m, 5m, 1h, 1d, 1wk, 1mo)')
    yahoo_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    yahoo_parser.add_argument('--output', help='Output file path (csv/parquet/json)')
    
    # CCXT command
    ccxt_parser = subparsers.add_parser('ccxt', help='Get data from CCXT exchange')
    ccxt_parser.add_argument('symbol', help='Trading pair (e.g., BTC/USDT)')
    ccxt_parser.add_argument('--timeframe', default='1d', help='Timeframe (1m, 5m, 1h, 1d)')
    ccxt_parser.add_argument('--limit', type=int, default=100, help='Number of candles')
    ccxt_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    ccxt_parser.add_argument('--output', help='Output file path')
    
    # Binance command
    binance_parser = subparsers.add_parser('binance', help='Get data from Binance')
    binance_parser.add_argument('symbol', help='Trading pair (e.g., BTCUSDT)')
    binance_parser.add_argument('--interval', default='1d', help='Interval (1m, 5m, 1h, 1d)')
    binance_parser.add_argument('--start', help='Start date (e.g., "1 Jan, 2024")')
    binance_parser.add_argument('--end', help='End date')
    binance_parser.add_argument('--limit', type=int, default=500, help='Number of klines')
    binance_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    binance_parser.add_argument('--output', help='Output file path')
    
    # Alpaca command
    alpaca_parser = subparsers.add_parser('alpaca', help='Get data from Alpaca')
    alpaca_parser.add_argument('symbol', help='Stock symbol (e.g., AAPL)')
    alpaca_parser.add_argument('--start', required=True, help='Start datetime (YYYY-MM-DD)')
    alpaca_parser.add_argument('--end', required=True, help='End datetime (YYYY-MM-DD)')
    alpaca_parser.add_argument('--timeframe', default='1Day', help='Timeframe (1Min, 5Min, 1Hour, 1Day)')
    alpaca_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    alpaca_parser.add_argument('--output', help='Output file path')
    
    # List saved tables command
    subparsers.add_parser('list-tables', help='List saved data tables')
    
    # List saved files command
    subparsers.add_parser('list-files', help='List saved parquet files')
    
    # Query saved data command
    query_parser = subparsers.add_parser('query', help='Query saved data')
    query_parser.add_argument('table_name', help='Table name to query')
    query_parser.add_argument('--filter', help='SQL WHERE clause filter')
    query_parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize connector
    connector = ConnectorEngine(args.config, use_database=not args.no_db)
    
    try:
        if args.command == 'list-sources':
            sources = connector.get_available_sources()
            print(f"Available sources ({len(sources)}):")
            for source in sources:
                print(f"  - {source}")
        
        elif args.command == 'yahoo':
            df = connector.get_yahoo_data(
                args.symbol,
                start=args.start,
                end=args.end,
                period=args.period,
                interval=args.interval,
                save_to_db=not args.no_save
            )
            print(f"Retrieved {len(df)} rows for {args.symbol}")
            print(df.head())
            if args.output:
                _save_output(df, args.output)
        
        elif args.command == 'ccxt':
            df = connector.get_ccxt_ohlcv(
                args.symbol,
                timeframe=args.timeframe,
                limit=args.limit,
                save_to_db=not args.no_save
            )
            print(f"Retrieved {len(df)} rows for {args.symbol}")
            print(df.head())
            if args.output:
                _save_output(df, args.output)
        
        elif args.command == 'binance':
            df = connector.get_binance_klines(
                args.symbol,
                interval=args.interval,
                start_str=args.start,
                end_str=args.end,
                limit=args.limit,
                save_to_db=not args.no_save
            )
            print(f"Retrieved {len(df)} rows for {args.symbol}")
            print(df.head())
            if args.output:
                _save_output(df, args.output)
        
        elif args.command == 'alpaca':
            start_dt = datetime.strptime(args.start, '%Y-%m-%d')
            end_dt = datetime.strptime(args.end, '%Y-%m-%d')
            df = connector.get_alpaca_bars(
                args.symbol,
                start=start_dt,
                end=end_dt,
                timeframe=args.timeframe,
                save_to_db=not args.no_save
            )
            print(f"Retrieved {len(df)} rows for {args.symbol}")
            print(df.head())
            if args.output:
                _save_output(df, args.output)
        
        elif args.command == 'list-tables':
            tables = connector.list_saved_tables()
            print(f"Saved tables ({len(tables)}):")
            for table in tables:
                print(f"  - {table}")
        
        elif args.command == 'list-files':
            files = connector.list_saved_parquet_files()
            print(f"Saved parquet files ({len(files)}):")
            for file in files:
                print(f"  - {file}")
        
        elif args.command == 'query':
            df = connector.query_saved_data(args.table_name, args.filter)
            if df is not None:
                print(df)
                if args.output:
                    _save_output(df, args.output)
    
    finally:
        connector.close()


def _save_output(df, output_path):
    """Helper function to save DataFrame to file"""
    if output_path.endswith('.csv'):
        df.to_csv(output_path, index=False)
    elif output_path.endswith('.parquet'):
        df.to_parquet(output_path, index=False)
    elif output_path.endswith('.json'):
        df.to_json(output_path, orient='records')
    print(f"Data saved to {output_path}")


if __name__ == "__main__":
    main()
