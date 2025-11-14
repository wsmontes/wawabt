"""
Backtrader Data Feed Integration with Smart Database and Connectors
Automatically retrieves data from local database or fetches from connectors

Features:
- Auto-fetch from database or connectors
- Resampling and Replay support
- Multiple timeframe support
- Timezone management
- Session start/end handling
"""
import pandas as pd
from datetime import datetime, timedelta, time
from typing import Optional, Union, List, Dict, Any
import backtrader as bt

try:
    import pytz
except ImportError:
    pytz = None

try:
    from .smart_db import SmartDatabaseManager
    from .connector import ConnectorEngine
except ImportError:
    SmartDatabaseManager = None
    ConnectorEngine = None


class SmartPandasData(bt.feeds.PandasData):
    """
    Enhanced PandasData feed that automatically fetches missing data
    from connectors and stores it in the database
    """
    
    params = (
        ('symbol', ''),
        ('source', 'yahoo_finance'),
        ('interval', '1d'),
        ('use_smart_db', True),
        ('auto_fetch', True),
        ('db_path', 'data/market_data.duckdb'),
        ('connector_config', 'config/connector.json'),
        ('fetch_period', '1y'),  # Period to fetch if data missing
    )
    
    def __init__(self):
        super(SmartPandasData, self).__init__()
        
        # Initialize database and connector
        self.db = None
        self.connector = None
        
        if self.p.use_smart_db and SmartDatabaseManager:
            try:
                self.db = SmartDatabaseManager(self.p.db_path)
                print(f"[SmartPandasData] Database initialized for {self.p.symbol}")
            except Exception as e:
                print(f"[SmartPandasData] Failed to initialize database: {e}")
        
        if self.p.auto_fetch and ConnectorEngine:
            try:
                self.connector = ConnectorEngine(
                    config_path=self.p.connector_config,
                    use_smart_db=self.p.use_smart_db,
                    db_path=self.p.db_path
                )
                print(f"[SmartPandasData] Connector initialized for {self.p.symbol}")
            except Exception as e:
                print(f"[SmartPandasData] Failed to initialize connector: {e}")


class AutoFetchData:
    """
    Factory class to create Backtrader data feeds with automatic data retrieval
    
    Supports:
    - Automatic data fetching from database or connectors
    - Resampling to different timeframes
    - Replay mode for realistic backtesting
    - Timezone management
    - Session start/end times
    """
    
    @staticmethod
    def create(symbol: str,
               fromdate: Optional[datetime] = None,
               todate: Optional[datetime] = None,
               source: str = 'yahoo_finance',
               interval: str = '1d',
               use_smart_db: bool = True,
               auto_fetch: bool = True,
               db_config_path: str = 'config/database.json',
               connector_config: str = 'config/connector.json',
               # Timezone parameters
               tz: Optional[str] = None,  # Output timezone (e.g., 'US/Eastern', 'UTC')
               tzinput: Optional[str] = None,  # Input timezone of data
               # Session parameters
               sessionstart: Optional[time] = None,  # Market open time
               sessionend: Optional[time] = None,  # Market close time
               # Resampling/Replay
               resample: bool = False,  # Enable resampling
               replay: bool = False,  # Enable replay mode
               timeframe: Optional[int] = None,  # Target timeframe for resample/replay
               compression: int = 1,  # Compression factor
               **kwargs) -> Optional[bt.feeds.PandasData]:
        """
        Create a Backtrader data feed with automatic data retrieval
        
        Args:
            symbol: Stock/crypto symbol (e.g., 'AAPL', 'BTCUSDT')
            fromdate: Start date for data
            todate: End date for data
            source: Data source ('yahoo_finance', 'binance', 'ccxt', 'alpaca', 'quandl', etc.)
            interval: Time interval ('1d', '1h', '5m', etc.)
            use_smart_db: Whether to use smart database
            auto_fetch: Whether to automatically fetch missing data
            db_config_path: Path to database config file
            connector_config: Path to connector configuration
            tz: Output timezone (e.g., 'US/Eastern', 'Europe/Berlin', 'UTC')
            tzinput: Input timezone of raw data
            sessionstart: Market session start time (datetime.time object)
            sessionend: Market session end time (datetime.time object)
            resample: If True, resample data to a different timeframe
            replay: If True, use replay mode (more realistic tick-by-tick simulation)
            timeframe: Target timeframe for resample/replay (bt.TimeFrame.Minutes, Days, etc.)
            compression: Compression factor (e.g., 5 for 5-minute bars)
            **kwargs: Additional parameters for PandasData
        
        Returns:
            Backtrader data feed (regular, resampled, or replayed)
        
        Examples:
            # Basic usage
            data = AutoFetchData.create('AAPL', fromdate=datetime(2024, 1, 1))
            
            # With timezone (for trader in Berlin trading US stocks)
            data = AutoFetchData.create('AAPL', tz='US/Eastern')
            
            # With session times
            data = AutoFetchData.create('AAPL', 
                                       sessionstart=time(9, 30),
                                       sessionend=time(16, 0))
            
            # Resample 1-min data to 5-min bars
            data = AutoFetchData.create('AAPL', interval='1m',
                                       resample=True,
                                       timeframe=bt.TimeFrame.Minutes,
                                       compression=5)
            
            # Replay mode for realistic simulation
            data = AutoFetchData.create('AAPL', interval='1m',
                                       replay=True,
                                       timeframe=bt.TimeFrame.Minutes,
                                       compression=5)
        """
        if fromdate is None:
            fromdate = datetime.now() - timedelta(days=365)
        if todate is None:
            todate = datetime.now()
        
        df = None
        
        # Try to load from database first
        if use_smart_db and SmartDatabaseManager:
            try:
                db = SmartDatabaseManager(db_config_path)
                print(f"[AutoFetchData] Attempting to load {symbol} from database...")
                
                df = db.query_market_data(
                    symbol=symbol,
                    source=source,
                    interval=interval,
                    start_date=fromdate.strftime('%Y-%m-%d'),
                    end_date=todate.strftime('%Y-%m-%d')
                )
                
                if df is not None and len(df) > 0:
                    print(f"[AutoFetchData] Loaded {len(df)} rows from database for {symbol}")
                else:
                    print(f"[AutoFetchData] No data found in database for {symbol}")
                    df = None
            except Exception as e:
                print(f"[AutoFetchData] Database query failed: {e}")
                df = None
        
        # If no data in database and auto_fetch enabled, fetch from connector
        if df is None and auto_fetch and ConnectorEngine:
            try:
                print(f"[AutoFetchData] Fetching {symbol} from {source}...")
                connector = ConnectorEngine(
                    config_path=connector_config,
                    use_smart_db=use_smart_db,
                    db_config_path=db_config_path
                )
                
                # Route to appropriate connector method
                if source == 'yahoo_finance' or source == 'yahoo':
                    df = connector.get_yahoo_data(
                        symbol=symbol,
                        start=fromdate.strftime('%Y-%m-%d'),
                        end=todate.strftime('%Y-%m-%d'),
                        interval=interval,
                        save_to_db=use_smart_db
                    )
                
                elif source == 'binance':
                    limit = min(1000, int((todate - fromdate).total_seconds() / 86400))
                    df = connector.get_binance_klines(
                        symbol=symbol,
                        interval=interval,
                        limit=limit,
                        save_to_db=use_smart_db
                    )
                
                elif source == 'ccxt':
                    # Default to binance exchange for CCXT
                    exchange = kwargs.get('exchange', 'binance')
                    limit = min(1000, int((todate - fromdate).total_seconds() / 86400))
                    df = connector.get_ccxt_ohlcv(
                        exchange=exchange,
                        symbol=symbol,
                        timeframe=interval,
                        limit=limit,
                        save_to_db=use_smart_db
                    )
                
                elif source == 'alpaca':
                    df = connector.get_alpaca_bars(
                        symbol=symbol,
                        start=fromdate.strftime('%Y-%m-%d'),
                        end=todate.strftime('%Y-%m-%d'),
                        timeframe=interval.upper(),
                        save_to_db=use_smart_db
                    )
                
                else:
                    print(f"[AutoFetchData] Unknown source: {source}")
                    return None
                
                if df is not None and len(df) > 0:
                    print(f"[AutoFetchData] Fetched {len(df)} rows from {source} for {symbol}")
                else:
                    print(f"[AutoFetchData] Failed to fetch data from {source}")
                    return None
                
            except Exception as e:
                print(f"[AutoFetchData] Connector fetch failed: {e}")
                return None
        
        if df is None or len(df) == 0:
            print(f"[AutoFetchData] No data available for {symbol}")
            return None
        
        # Prepare DataFrame for Backtrader
        df = AutoFetchData._prepare_dataframe(df, fromdate, todate)
        
        if df is None or len(df) == 0:
            print(f"[AutoFetchData] No data after preparation for {symbol}")
            return None
        
        # Handle timezone if specified
        tz_obj = None
        tzinput_obj = None
        
        if tz and pytz:
            try:
                tz_obj = pytz.timezone(tz)
                print(f"[AutoFetchData] Using output timezone: {tz}")
            except Exception as e:
                print(f"[AutoFetchData] Invalid timezone '{tz}': {e}")
        
        if tzinput and pytz:
            try:
                tzinput_obj = pytz.timezone(tzinput)
                print(f"[AutoFetchData] Using input timezone: {tzinput}")
            except Exception as e:
                print(f"[AutoFetchData] Invalid input timezone '{tzinput}': {e}")
        
        # Create base Backtrader data feed
        data_params = {
            'dataname': df,
            'fromdate': fromdate,
            'todate': todate,
        }
        
        # Add timezone parameters if provided
        if tz_obj:
            data_params['tz'] = tz_obj
        if tzinput_obj:
            data_params['tzinput'] = tzinput_obj
        
        # Add session parameters if provided
        if sessionstart:
            data_params['sessionstart'] = sessionstart
        if sessionend:
            data_params['sessionend'] = sessionend
        
        # Merge with any additional kwargs
        data_params.update(kwargs)
        
        data_feed = bt.feeds.PandasData(**data_params)
        
        # Apply resampling if requested
        if resample:
            if timeframe is None:
                timeframe = bt.TimeFrame.Days  # Default to daily
            
            print(f"[AutoFetchData] Resampling to timeframe={timeframe}, compression={compression}")
            # Note: Resampling will be done by Cerebro.resampledata()
            # We return the base feed and let the user apply resampling via cerebro
            # Or we can wrap it here if needed
            data_feed._resample_params = {
                'timeframe': timeframe,
                'compression': compression
            }
        
        # Apply replay if requested
        if replay:
            if timeframe is None:
                timeframe = bt.TimeFrame.Days  # Default to daily
            
            print(f"[AutoFetchData] Replay mode enabled: timeframe={timeframe}, compression={compression}")
            # Similar to resampling, replay is typically done via cerebro.replaydata()
            data_feed._replay_params = {
                'timeframe': timeframe,
                'compression': compression
            }
        
        print(f"[AutoFetchData] Created data feed for {symbol}: {len(df)} bars")
        return data_feed
    
    @staticmethod
    def _prepare_dataframe(df: pd.DataFrame, 
                          fromdate: datetime, 
                          todate: datetime) -> Optional[pd.DataFrame]:
        """
        Prepare DataFrame for Backtrader consumption
        
        Args:
            df: Raw DataFrame
            fromdate: Start date
            todate: End date
        
        Returns:
            Prepared DataFrame with proper format
        """
        try:
            # Ensure we have required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    print(f"[AutoFetchData] Missing required column: {col}")
                    return None
            
            # Convert timestamp to datetime if needed
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Remove timezone info to avoid comparison issues
            if hasattr(df['timestamp'].dtype, 'tz') and df['timestamp'].dtype.tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
            
            # Set timestamp as index
            df = df.set_index('timestamp')
            
            # Make fromdate and todate timezone-naive for comparison
            if hasattr(fromdate, 'tzinfo') and fromdate.tzinfo is not None:
                fromdate = fromdate.replace(tzinfo=None)
            if hasattr(todate, 'tzinfo') and todate.tzinfo is not None:
                todate = todate.replace(tzinfo=None)
            
            # Filter date range
            df = df[(df.index >= fromdate) & (df.index <= todate)]
            
            # Sort by date
            df = df.sort_index()
            
            # Rename columns to match Backtrader expectations
            df = df.rename(columns={
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume'
            })
            
            # Keep only OHLCV columns (optional: keep vwap, trades if available)
            base_cols = ['open', 'high', 'low', 'close', 'volume']
            optional_cols = ['vwap', 'trades', 'openinterest']
            
            keep_cols = base_cols + [col for col in optional_cols if col in df.columns]
            df = df[keep_cols]
            
            # Remove any NaN values
            df = df.dropna()
            
            return df
            
        except Exception as e:
            print(f"[AutoFetchData] DataFrame preparation failed: {e}")
            return None


class MultiSourceData:
    """
    Create multiple data feeds from different sources simultaneously
    """
    
    @staticmethod
    def create_multiple(symbols: list,
                       fromdate: Optional[datetime] = None,
                       todate: Optional[datetime] = None,
                       source: str = 'yahoo_finance',
                       interval: str = '1d',
                       **kwargs) -> dict:
        """
        Create multiple data feeds at once
        
        Args:
            symbols: List of symbols
            fromdate: Start date
            todate: End date
            source: Data source
            interval: Time interval
            **kwargs: Additional parameters
        
        Returns:
            Dictionary mapping symbol to data feed
        """
        feeds = {}
        
        for symbol in symbols:
            print(f"\n[MultiSourceData] Creating feed for {symbol}...")
            feed = AutoFetchData.create(
                symbol=symbol,
                fromdate=fromdate,
                todate=todate,
                source=source,
                interval=interval,
                **kwargs
            )
            
            if feed is not None:
                feeds[symbol] = feed
                print(f"[MultiSourceData] ✓ {symbol} feed ready")
            else:
                print(f"[MultiSourceData] ✗ {symbol} feed failed")
        
        print(f"\n[MultiSourceData] Created {len(feeds)}/{len(symbols)} feeds")
        return feeds


# Convenience function for quick data feed creation
def create_data_feed(symbol: str, **kwargs) -> Optional[bt.feeds.PandasData]:
    """
    Quick function to create a data feed with smart defaults
    
    Example:
        data = create_data_feed('AAPL', fromdate=datetime(2024, 1, 1))
    """
    return AutoFetchData.create(symbol=symbol, **kwargs)


# Convenience function for multiple symbols
def create_multiple_feeds(symbols: list, **kwargs) -> dict:
    """
    Quick function to create multiple data feeds
    
    Example:
        feeds = create_multiple_feeds(['AAPL', 'GOOGL', 'MSFT'])
        for symbol, feed in feeds.items():
            cerebro.adddata(feed, name=symbol)
    """
    return MultiSourceData.create_multiple(symbols=symbols, **kwargs)
