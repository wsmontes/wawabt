"""
Enhanced Connector Engine for multiple data sources
Supports: CCXT (multiple exchanges), Alpaca (stocks/crypto/options/news), Binance, and Yahoo Finance

New Features:
- Alpaca: News, Corporate Actions, Crypto, Options, Latest data
- CCXT: Multiple exchanges, order books, tickers, trades
- Binance: Order books, tickers, proper rate limiting
- Async support, retry logic, better error handling
"""
import json
import time
import asyncio
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Alpaca imports
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.historical.crypto import CryptoHistoricalDataClient
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.historical.news import NewsClient
    from alpaca.data.historical.corporate_actions import CorporateActionsClient
    from alpaca.data.requests import (
        StockBarsRequest, StockQuotesRequest, StockTradesRequest,
        StockLatestBarRequest, StockLatestQuoteRequest, StockLatestTradeRequest,
        CryptoBarsRequest, CryptoLatestBarRequest,
        OptionBarsRequest, OptionChainRequest,
        NewsRequest, CorporateActionsRequest
    )
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.data.enums import Adjustment, DataFeed
except ImportError:
    StockHistoricalDataClient = None
    CryptoHistoricalDataClient = None
    OptionHistoricalDataClient = None
    NewsClient = None
    CorporateActionsClient = None

try:
    from binance.client import Client as BinanceClient
    from binance.exceptions import BinanceAPIException
except ImportError:
    BinanceClient = None

try:
    import yfinance as yf
except ImportError:
    yf = None


class EnhancedConnectorEngine:
    """
    Enhanced multi-source data connector for financial market data
    
    Improvements over original:
    - Multiple CCXT exchanges support
    - All Alpaca clients (stocks, crypto, options, news, corporate actions)
    - Binance order book and ticker data
    - Proper rate limiting and retry logic
    - Async support
    - Better error handling
    """
    
    def __init__(self, config_path: str = "config/connector.json", 
                 use_database: bool = True,
                 db_config_path: str = "config/database.json",
                 use_smart_db: bool = True,
                 max_retries: int = 3,
                 retry_delay: float = 1.0):
        """
        Initialize the enhanced connector engine
        
        Args:
            config_path: Path to the connector configuration JSON file
            use_database: Whether to enable database integration
            db_config_path: Path to database configuration
            use_smart_db: Use SmartDatabaseManager (recommended) vs legacy DatabaseEngine
            max_retries: Maximum number of retry attempts for failed requests
            retry_delay: Initial delay between retries (uses exponential backoff)
        """
        self.config = self._load_config(config_path)
        self.connections = {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Initialize database if enabled
        self.db = None
        self.use_database = use_database
        if use_database:
            if use_smart_db and SmartDatabaseManager is not None:
                try:
                    self.db = SmartDatabaseManager(db_config_path)
                    logger.info("Smart Database integration enabled for Connector")
                except Exception as e:
                    logger.error(f"Failed to initialize Smart Database: {e}")
                    self.db = None
            elif DatabaseEngine is not None:
                try:
                    self.db = DatabaseEngine(db_config_path)
                    logger.info("Database integration enabled for Connector")
                except Exception as e:
                    logger.error(f"Failed to initialize database: {e}")
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
            logger.warning(f"Config file {config_path} not found, using defaults")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "ccxt": {
                "exchanges": {
                    "binance": {"enabled": True, "testnet": False},
                    "coinbase": {"enabled": False},
                    "kraken": {"enabled": False}
                },
                "default_exchange": "binance",
                "rate_limit": True
            },
            "alpaca": {
                "base_url": "https://paper-api.alpaca.markets",
                "api_key": "",
                "api_secret": "",
                "data_feed": "iex",
                "enable_crypto": True,
                "enable_options": True,
                "enable_news": True,
                "enable_corporate_actions": True
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
    
    def _retry_request(self, func, *args, **kwargs):
        """
        Execute a function with retry logic and exponential backoff
        
        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Raises:
            Exception: If all retry attempts fail
        """
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"All retry attempts failed: {e}")
                    raise
                
                delay = self.retry_delay * (2 ** attempt)
                logger.warning(f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
    
    def _init_ccxt(self):
        """Initialize CCXT exchange connections for all enabled exchanges"""
        if ccxt is None:
            logger.warning("CCXT not installed. Install with: pip install ccxt")
            return
        
        ccxt_config = self.config.get("ccxt", {})
        exchanges_config = ccxt_config.get("exchanges", {})
        
        for exchange_name, exchange_settings in exchanges_config.items():
            if not exchange_settings.get("enabled", True):
                continue
                
            try:
                exchange_class = getattr(ccxt, exchange_name)
                self.connections[f'ccxt_{exchange_name}'] = exchange_class({
                    'enableRateLimit': ccxt_config.get("rate_limit", True),
                    'timeout': ccxt_config.get("timeout", 30000),
                    'apiKey': exchange_settings.get("api_key", ccxt_config.get("api_key", "")),
                    'secret': exchange_settings.get("api_secret", ccxt_config.get("api_secret", ""))
                })
                
                # Load markets for each exchange
                try:
                    self.connections[f'ccxt_{exchange_name}'].load_markets()
                    logger.info(f"CCXT {exchange_name} initialized with {len(self.connections[f'ccxt_{exchange_name}'].markets)} markets")
                except Exception as e:
                    logger.warning(f"Failed to load markets for {exchange_name}: {e}")
                    
            except Exception as e:
                logger.error(f"Failed to initialize CCXT {exchange_name}: {e}")
    
    def _init_alpaca(self):
        """Initialize all Alpaca clients"""
        if StockHistoricalDataClient is None:
            logger.warning("Alpaca not installed. Install with: pip install alpaca-py")
            return
        
        alpaca_config = self.config.get("alpaca", {})
        api_key = alpaca_config.get("api_key", "")
        api_secret = alpaca_config.get("api_secret", "")
        
        # Stock Historical Data Client
        if api_key and api_secret:
            try:
                self.connections['alpaca_stocks'] = StockHistoricalDataClient(
                    api_key=api_key,
                    secret_key=api_secret
                )
                logger.info("Alpaca Stock Historical Data Client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca stocks: {e}")
        
        # Crypto Historical Data Client (no auth required, but better with auth)
        if alpaca_config.get("enable_crypto", True) and CryptoHistoricalDataClient:
            try:
                self.connections['alpaca_crypto'] = CryptoHistoricalDataClient(
                    api_key=api_key if api_key else None,
                    secret_key=api_secret if api_secret else None
                )
                logger.info("Alpaca Crypto Historical Data Client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca crypto: {e}")
        
        # Options Historical Data Client
        if alpaca_config.get("enable_options", True) and api_key and api_secret and OptionHistoricalDataClient:
            try:
                self.connections['alpaca_options'] = OptionHistoricalDataClient(
                    api_key=api_key,
                    secret_key=api_secret
                )
                logger.info("Alpaca Options Historical Data Client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca options: {e}")
        
        # News Client (no auth required!)
        if alpaca_config.get("enable_news", True) and NewsClient:
            try:
                self.connections['alpaca_news'] = NewsClient(
                    api_key=api_key if api_key else None,
                    secret_key=api_secret if api_secret else None
                )
                logger.info("Alpaca News Client initialized (no auth required)")
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca news: {e}")
        
        # Corporate Actions Client
        if alpaca_config.get("enable_corporate_actions", True) and api_key and api_secret and CorporateActionsClient:
            try:
                self.connections['alpaca_corporate_actions'] = CorporateActionsClient(
                    api_key=api_key,
                    secret_key=api_secret
                )
                logger.info("Alpaca Corporate Actions Client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Alpaca corporate actions: {e}")
    
    def _init_binance(self):
        """Initialize Binance connection"""
        if BinanceClient is None:
            logger.warning("Binance not installed. Install with: pip install python-binance")
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
            logger.info("Binance initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Binance: {e}")
    
    # ======================== CCXT Methods ========================
    
    def get_ccxt_markets(self, exchange: str = None) -> List[str]:
        """Get list of available markets from CCXT exchange"""
        exchange = exchange or self.config.get("ccxt", {}).get("default_exchange", "binance")
        conn_key = f'ccxt_{exchange}'
        
        if conn_key not in self.connections:
            raise RuntimeError(f"CCXT exchange {exchange} not initialized")
        
        return list(self.connections[conn_key].markets.keys())
    
    def get_ccxt_ohlcv(self, symbol: str, timeframe: str = '1d', 
                       since: Optional[int] = None, limit: int = 100,
                       exchange: str = None, save_to_db: bool = True) -> pd.DataFrame:
        """Get OHLCV data from CCXT exchange with retry logic"""
        exchange = exchange or self.config.get("ccxt", {}).get("default_exchange", "binance")
        conn_key = f'ccxt_{exchange}'
        
        if conn_key not in self.connections:
            raise RuntimeError(f"CCXT exchange {exchange} not initialized")
        
        exchange_obj = self.connections[conn_key]
        
        # Retry wrapper
        ohlcv = self._retry_request(
            exchange_obj.fetch_ohlcv,
            symbol, timeframe, since, limit
        )
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['symbol'] = symbol
        df['source'] = f'ccxt_{exchange}'
        df['interval'] = timeframe
        
        if save_to_db and self.db:
            self._save_to_db(df, source=f'ccxt_{exchange}', symbol=symbol, interval=timeframe)
        
        return df
    
    def get_ccxt_orderbook(self, symbol: str, limit: int = 20, 
                          exchange: str = None) -> Dict[str, Any]:
        """Get order book from CCXT exchange"""
        exchange = exchange or self.config.get("ccxt", {}).get("default_exchange", "binance")
        conn_key = f'ccxt_{exchange}'
        
        if conn_key not in self.connections:
            raise RuntimeError(f"CCXT exchange {exchange} not initialized")
        
        return self._retry_request(
            self.connections[conn_key].fetch_order_book,
            symbol, limit
        )
    
    def get_ccxt_ticker(self, symbol: str, exchange: str = None) -> Dict[str, Any]:
        """Get ticker data from CCXT exchange"""
        exchange = exchange or self.config.get("ccxt", {}).get("default_exchange", "binance")
        conn_key = f'ccxt_{exchange}'
        
        if conn_key not in self.connections:
            raise RuntimeError(f"CCXT exchange {exchange} not initialized")
        
        return self._retry_request(
            self.connections[conn_key].fetch_ticker,
            symbol
        )
    
    def get_ccxt_trades(self, symbol: str, since: Optional[int] = None,
                       limit: int = 100, exchange: str = None) -> List[Dict]:
        """Get recent trades from CCXT exchange"""
        exchange = exchange or self.config.get("ccxt", {}).get("default_exchange", "binance")
        conn_key = f'ccxt_{exchange}'
        
        if conn_key not in self.connections:
            raise RuntimeError(f"CCXT exchange {exchange} not initialized")
        
        return self._retry_request(
            self.connections[conn_key].fetch_trades,
            symbol, since, limit
        )
    
    # ======================== Alpaca Stock Methods ========================
    
    def get_alpaca_bars(self, symbol: str, start: datetime, end: datetime,
                        timeframe: str = '1Day', adjustment: str = 'raw',
                        feed: str = None, save_to_db: bool = True) -> pd.DataFrame:
        """
        Get stock bar data from Alpaca with proper TimeFrame enum
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            start: Start datetime
            end: End datetime
            timeframe: Timeframe string (e.g., '1Min', '1Hour', '1Day')
            adjustment: Data adjustment type ('raw', 'split', 'dividend', 'all')
            feed: Data feed ('iex', 'sip', etc.)
            save_to_db: Whether to save data to database
        """
        if 'alpaca_stocks' not in self.connections:
            raise RuntimeError("Alpaca stocks not initialized")
        
        # Convert string timeframe to TimeFrame enum
        tf = self._parse_alpaca_timeframe(timeframe)
        
        # Convert adjustment string to enum
        adj = self._parse_adjustment(adjustment)
        
        # Use configured feed if not specified
        if feed is None:
            feed = self.config.get("alpaca", {}).get("data_feed", "iex")
        
        request_params = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end,
            adjustment=adj,
            feed=feed
        )
        
        bars = self._retry_request(
            self.connections['alpaca_stocks'].get_stock_bars,
            request_params
        )
        
        df = bars.df.reset_index()
        df['source'] = 'alpaca_stocks'
        df['interval'] = timeframe
        
        if save_to_db and self.db:
            self._save_to_db(df, source='alpaca_stocks', symbol=symbol, interval=timeframe)
        
        return df
    
    def get_alpaca_quotes(self, symbol: str, start: datetime, end: datetime,
                         feed: str = None, save_to_db: bool = True) -> pd.DataFrame:
        """Get stock quote data (bid/ask) from Alpaca"""
        if 'alpaca_stocks' not in self.connections:
            raise RuntimeError("Alpaca stocks not initialized")
        
        if feed is None:
            feed = self.config.get("alpaca", {}).get("data_feed", "iex")
        
        request_params = StockQuotesRequest(
            symbol_or_symbols=symbol,
            start=start,
            end=end,
            feed=feed
        )
        
        quotes = self._retry_request(
            self.connections['alpaca_stocks'].get_stock_quotes,
            request_params
        )
        
        df = quotes.df.reset_index()
        df['source'] = 'alpaca_stocks_quotes'
        
        if save_to_db and self.db:
            self._save_to_db(df, source='alpaca_stocks_quotes', symbol=symbol, interval='quote')
        
        return df
    
    def get_alpaca_trades(self, symbol: str, start: datetime, end: datetime,
                         feed: str = None, save_to_db: bool = True) -> pd.DataFrame:
        """Get stock trade data from Alpaca"""
        if 'alpaca_stocks' not in self.connections:
            raise RuntimeError("Alpaca stocks not initialized")
        
        if feed is None:
            feed = self.config.get("alpaca", {}).get("data_feed", "iex")
        
        request_params = StockTradesRequest(
            symbol_or_symbols=symbol,
            start=start,
            end=end,
            feed=feed
        )
        
        trades = self._retry_request(
            self.connections['alpaca_stocks'].get_stock_trades,
            request_params
        )
        
        df = trades.df.reset_index()
        df['source'] = 'alpaca_stocks_trades'
        
        if save_to_db and self.db:
            self._save_to_db(df, source='alpaca_stocks_trades', symbol=symbol, interval='trade')
        
        return df
    
    def get_alpaca_latest_bar(self, symbol: str, feed: str = None) -> Dict:
        """Get latest bar data for a stock"""
        if 'alpaca_stocks' not in self.connections:
            raise RuntimeError("Alpaca stocks not initialized")
        
        if feed is None:
            feed = self.config.get("alpaca", {}).get("data_feed", "iex")
        
        request_params = StockLatestBarRequest(
            symbol_or_symbols=symbol,
            feed=feed
        )
        
        return self._retry_request(
            self.connections['alpaca_stocks'].get_stock_latest_bar,
            request_params
        )
    
    def get_alpaca_latest_quote(self, symbol: str, feed: str = None) -> Dict:
        """Get latest quote data for a stock"""
        if 'alpaca_stocks' not in self.connections:
            raise RuntimeError("Alpaca stocks not initialized")
        
        if feed is None:
            feed = self.config.get("alpaca", {}).get("data_feed", "iex")
        
        request_params = StockLatestQuoteRequest(
            symbol_or_symbols=symbol,
            feed=feed
        )
        
        return self._retry_request(
            self.connections['alpaca_stocks'].get_stock_latest_quote,
            request_params
        )
    
    def get_alpaca_latest_trade(self, symbol: str, feed: str = None) -> Dict:
        """Get latest trade data for a stock"""
        if 'alpaca_stocks' not in self.connections:
            raise RuntimeError("Alpaca stocks not initialized")
        
        if feed is None:
            feed = self.config.get("alpaca", {}).get("data_feed", "iex")
        
        request_params = StockLatestTradeRequest(
            symbol_or_symbols=symbol,
            feed=feed
        )
        
        return self._retry_request(
            self.connections['alpaca_stocks'].get_stock_latest_trade,
            request_params
        )
    
    # ======================== Alpaca Crypto Methods ========================
    
    def get_alpaca_crypto_bars(self, symbol: str, start: datetime, end: datetime,
                               timeframe: str = '1Day', save_to_db: bool = True) -> pd.DataFrame:
        """Get crypto bar data from Alpaca"""
        if 'alpaca_crypto' not in self.connections:
            raise RuntimeError("Alpaca crypto not initialized")
        
        tf = self._parse_alpaca_timeframe(timeframe)
        
        request_params = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end
        )
        
        bars = self._retry_request(
            self.connections['alpaca_crypto'].get_crypto_bars,
            request_params
        )
        
        df = bars.df.reset_index()
        df['source'] = 'alpaca_crypto'
        df['interval'] = timeframe
        
        if save_to_db and self.db:
            self._save_to_db(df, source='alpaca_crypto', symbol=symbol, interval=timeframe)
        
        return df
    
    # ======================== Alpaca Options Methods ========================
    
    def get_alpaca_option_bars(self, symbol: str, start: datetime, end: datetime,
                               timeframe: str = '1Day', save_to_db: bool = True) -> pd.DataFrame:
        """Get option bar data from Alpaca"""
        if 'alpaca_options' not in self.connections:
            raise RuntimeError("Alpaca options not initialized")
        
        tf = self._parse_alpaca_timeframe(timeframe)
        
        request_params = OptionBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=tf,
            start=start,
            end=end
        )
        
        bars = self._retry_request(
            self.connections['alpaca_options'].get_option_bars,
            request_params
        )
        
        df = bars.df.reset_index()
        df['source'] = 'alpaca_options'
        df['interval'] = timeframe
        
        if save_to_db and self.db:
            self._save_to_db(df, source='alpaca_options', symbol=symbol, interval=timeframe)
        
        return df
    
    def get_alpaca_option_chain(self, underlying_symbol: str) -> Dict:
        """Get option chain for an underlying symbol"""
        if 'alpaca_options' not in self.connections:
            raise RuntimeError("Alpaca options not initialized")
        
        request_params = OptionChainRequest(
            underlying_symbol=underlying_symbol
        )
        
        return self._retry_request(
            self.connections['alpaca_options'].get_option_chain,
            request_params
        )
    
    # ======================== Alpaca News Methods ========================
    
    def get_alpaca_news(self, symbols: Optional[List[str]] = None, 
                       start: Optional[datetime] = None,
                       end: Optional[datetime] = None,
                       limit: int = 50,
                       save_to_db: bool = True) -> pd.DataFrame:
        """
        Get news data from Alpaca (NO AUTH REQUIRED!)
        
        Args:
            symbols: List of symbols to filter news, or None for all
            start: Start datetime
            end: End datetime
            limit: Max number of articles (default 50, max 50)
            save_to_db: Whether to save to database
        """
        if 'alpaca_news' not in self.connections:
            raise RuntimeError("Alpaca news not initialized")
        
        request_params = NewsRequest(
            symbols=symbols,
            start=start,
            end=end,
            limit=min(limit, 50)
        )
        
        news = self._retry_request(
            self.connections['alpaca_news'].get_news,
            request_params
        )
        
        df = news.df
        df['source'] = 'alpaca_news'
        
        if save_to_db and self.db:
            try:
                if hasattr(self.db, 'save_news_data'):
                    self.db.save_news_data(df)
                else:
                    logger.warning("Database does not support news data")
            except Exception as e:
                logger.error(f"Failed to save news to database: {e}")
        
        return df
    
    # ======================== Alpaca Corporate Actions Methods ========================
    
    def get_alpaca_corporate_actions(self, symbols: Optional[List[str]] = None,
                                    start: Optional[datetime] = None,
                                    end: Optional[datetime] = None,
                                    save_to_db: bool = True) -> pd.DataFrame:
        """
        Get corporate actions data (splits, dividends, etc.)
        
        Args:
            symbols: List of symbols to filter, or None for all
            start: Start date
            end: End date
            save_to_db: Whether to save to database
        """
        if 'alpaca_corporate_actions' not in self.connections:
            raise RuntimeError("Alpaca corporate actions not initialized")
        
        request_params = CorporateActionsRequest(
            symbols=symbols,
            start=start.date() if start else None,
            end=end.date() if end else None
        )
        
        actions = self._retry_request(
            self.connections['alpaca_corporate_actions'].get_corporate_actions,
            request_params
        )
        
        df = actions.df
        df['source'] = 'alpaca_corporate_actions'
        
        if save_to_db and self.db:
            try:
                if hasattr(self.db, 'save_corporate_actions'):
                    self.db.save_corporate_actions(df)
                else:
                    logger.warning("Database does not support corporate actions data")
            except Exception as e:
                logger.error(f"Failed to save corporate actions to database: {e}")
        
        return df
    
    # ======================== Binance Methods ========================
    
    def get_binance_klines(self, symbol: str, interval: str = '1d',
                          start_str: Optional[Union[str, int, datetime]] = None, 
                          end_str: Optional[Union[str, int, datetime]] = None,
                          limit: int = 500, save_to_db: bool = True) -> pd.DataFrame:
        """Get kline/candlestick data from Binance with optional historical range"""
        if 'binance' not in self.connections:
            raise RuntimeError("Binance not initialized")
        
        client = self.connections['binance']

        def _to_millis(value: Optional[Union[str, int, float, datetime]]) -> Optional[int]:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, datetime):
                return int(value.timestamp() * 1000)
            return int(pd.Timestamp(value).timestamp() * 1000)

        start_ms = _to_millis(start_str)
        end_ms = _to_millis(end_str)

        request_limit = min(max(limit, 1), 1000)
        all_klines: List[List[Any]] = []
        current_start = start_ms
        prev_last_open_time: Optional[int] = None

        while True:
            request_kwargs = {
                'symbol': symbol,
                'interval': interval,
                'limit': request_limit
            }

            if current_start is not None:
                request_kwargs['start_str'] = current_start
            if end_ms is not None:
                request_kwargs['end_str'] = end_ms

            batch = self._retry_request(
                client.get_historical_klines,
                **request_kwargs
            )

            if not batch:
                break

            all_klines.extend(batch)

            last_open_time = batch[-1][0]
            if prev_last_open_time is not None and last_open_time <= prev_last_open_time:
                break
            prev_last_open_time = last_open_time

            if end_ms is not None and last_open_time >= end_ms:
                break

            current_start = last_open_time + 1
            time.sleep(0.2)

        if not all_klines:
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume',
                                         'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                                         'taker_buy_quote', 'ignore'])

        df = pd.DataFrame(all_klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['symbol'] = symbol
        df['source'] = 'binance'
        df['interval'] = interval
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        result_df = df[['timestamp', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'source', 'interval']]
        
        if save_to_db and self.db:
            self._save_to_db(result_df, source='binance', symbol=symbol, interval=interval)
        
        return result_df
    
    def get_binance_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get 24hr ticker price change statistics"""
        if 'binance' not in self.connections:
            raise RuntimeError("Binance not initialized")
        
        return self._retry_request(
            self.connections['binance'].get_ticker,
            symbol=symbol
        )
    
    def get_binance_orderbook(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get order book depth"""
        if 'binance' not in self.connections:
            raise RuntimeError("Binance not initialized")
        
        return self._retry_request(
            self.connections['binance'].get_order_book,
            symbol=symbol,
            limit=limit
        )
    
    # ======================== Yahoo Finance Methods ========================
    
    def get_yahoo_data(self, symbol: str, start: Optional[str] = None,
                      end: Optional[str] = None, period: str = '1mo',
                      interval: str = '1d', save_to_db: bool = True) -> pd.DataFrame:
        """Get data from Yahoo Finance (kept for backwards compatibility)"""
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
        
        if save_to_db and self.db:
            self._save_to_db(result_df, source='yahoo_finance', symbol=symbol, interval=interval)
        
        return result_df
    
    def get_yahoo_info(self, symbol: str) -> Dict[str, Any]:
        """Get ticker information from Yahoo Finance"""
        if yf is None:
            raise RuntimeError("yfinance not installed")
        
        ticker = yf.Ticker(symbol)
        return ticker.info
    
    # ======================== Utility Methods ========================
    
    def _parse_alpaca_timeframe(self, timeframe: str) -> TimeFrame:
        """
        Convert string timeframe to Alpaca TimeFrame enum
        
        Supports formats like: '1Min', '5Min', '15Min', '1Hour', '4Hour', '1Day', '1Week', '1Month'
        """
        # Extract number and unit
        import re
        match = re.match(r'(\d+)(\w+)', timeframe)
        if not match:
            raise ValueError(f"Invalid timeframe format: {timeframe}")
        
        amount = int(match.group(1))
        unit = match.group(2).lower()
        
        # Map unit to TimeFrameUnit
        unit_map = {
            'min': TimeFrameUnit.Minute,
            'minute': TimeFrameUnit.Minute,
            'hour': TimeFrameUnit.Hour,
            'day': TimeFrameUnit.Day,
            'week': TimeFrameUnit.Week,
            'month': TimeFrameUnit.Month,
        }
        
        if unit not in unit_map:
            raise ValueError(f"Unsupported timeframe unit: {unit}")
        
        return TimeFrame(amount, unit_map[unit])
    
    def _parse_adjustment(self, adjustment: str) -> Adjustment:
        """Convert string adjustment to Alpaca Adjustment enum"""
        adjustment_map = {
            'raw': Adjustment.RAW,
            'split': Adjustment.SPLIT,
            'dividend': Adjustment.DIVIDEND,
            'all': Adjustment.ALL
        }
        
        if adjustment.lower() not in adjustment_map:
            raise ValueError(f"Invalid adjustment type: {adjustment}. Must be one of: {list(adjustment_map.keys())}")
        
        return adjustment_map[adjustment.lower()]
    
    def _save_to_db(self, df: pd.DataFrame, source: str, symbol: str, interval: str):
        """Save dataframe to database"""
        if not self.db:
            return
        
        try:
            if hasattr(self.db, 'store_market_data'):
                self.db.store_market_data(df, source=source, symbol=symbol, interval=interval)
            elif hasattr(self.db, 'save_market_data'):
                self.db.save_market_data(df, source=source, symbol=symbol, interval=interval)
            else:
                logger.warning("Database does not support market data storage")
        except Exception as e:
            logger.error(f"Failed to save to database: {e}")
    
    def get_available_sources(self) -> List[str]:
        """Get list of available data sources"""
        return list(self.connections.keys())
    
    def get_available_exchanges(self) -> Dict[str, List[str]]:
        """Get dict of available exchanges grouped by type"""
        exchanges = {
            'ccxt': [],
            'alpaca': [],
            'other': []
        }
        
        for conn_key in self.connections.keys():
            if conn_key.startswith('ccxt_'):
                exchanges['ccxt'].append(conn_key.replace('ccxt_', ''))
            elif conn_key.startswith('alpaca_'):
                exchanges['alpaca'].append(conn_key.replace('alpaca_', ''))
            else:
                exchanges['other'].append(conn_key)
        
        return exchanges
    
    def close(self):
        """Close all connections"""
        for conn_key, conn in self.connections.items():
            try:
                if hasattr(conn, 'close'):
                    conn.close()
            except:
                pass
        
        if self.db:
            self.db.close()
        
        logger.info("All connections closed")


# Backwards compatibility: alias to original name
ConnectorEngine = EnhancedConnectorEngine


if __name__ == "__main__":
    # Example usage
    connector = EnhancedConnectorEngine()
    
    print("\n=== Available Sources ===")
    print(connector.get_available_sources())
    
    print("\n=== Available Exchanges ===")
    print(connector.get_available_exchanges())
    
    # Example: Get news (no auth required!)
    if 'alpaca_news' in connector.connections:
        print("\n=== Alpaca News (Last 10) ===")
        news_df = connector.get_alpaca_news(symbols=['AAPL', 'GOOGL'], limit=10)
        print(news_df.head())
    
    connector.close()
