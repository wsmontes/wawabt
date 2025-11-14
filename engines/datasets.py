"""
Datasets Engine for retrieving financial datasets from multiple sources
Supports: Kaggle, Hugging Face, Quandl, Alpha Vantage, and Polygon.io
"""
import json
import os
from typing import Optional, Dict, Any, List, Union
from pathlib import Path
import pandas as pd

try:
    from .database import DatabaseEngine
except ImportError:
    DatabaseEngine = None

try:
    import kaggle
    from kaggle.api.kaggle_api_extended import KaggleApi
except ImportError:
    kaggle = None
    KaggleApi = None

try:
    from datasets import load_dataset
    import huggingface_hub
except ImportError:
    load_dataset = None
    huggingface_hub = None

try:
    import quandl
except ImportError:
    quandl = None

try:
    import requests
except ImportError:
    requests = None

try:
    from polygon import RESTClient
except ImportError:
    RESTClient = None


class DatasetsEngine:
    """
    Multi-source dataset engine for financial and trading data
    """
    
    def __init__(self, config_path: str = "config/datasets.json",
                 use_database: bool = True,
                 db_config_path: str = "config/database.json",
                 use_smart_db: bool = True):
        """
        Initialize the datasets engine
        
        Args:
            config_path: Path to the datasets configuration JSON file
            use_database: Whether to enable database integration
            db_config_path: Path to database configuration
            use_smart_db: Whether to use SmartDatabaseManager (recommended)
        """
        self.config = self._load_config(config_path)
        self.data_folder = Path(self.config.get("data_folder", "data/datasets"))
        self.data_folder.mkdir(parents=True, exist_ok=True)
        
        # Initialize database if enabled
        self.db = None
        self.use_database = use_database
        if use_database and DatabaseEngine is not None:
            try:
                if use_smart_db:
                    try:
                        from engines.smart_db import SmartDatabaseManager
                        self.db = SmartDatabaseManager(db_config_path)
                        print("Smart Database integration enabled for Datasets")
                    except ImportError:
                        self.db = DatabaseEngine(db_config_path)
                        print("Legacy Database integration enabled for Datasets")
                else:
                    self.db = DatabaseEngine(db_config_path)
                    print("Legacy Database integration enabled for Datasets")
            except Exception as e:
                print(f"Failed to initialize database: {e}")
                self.db = None
        
        # Initialize API clients
        self._init_kaggle()
        self._init_quandl()
        self._init_polygon()
        
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
            "data_folder": "data/datasets",
            "kaggle": {
                "username": "",
                "key": "",
                "download_path": "data/datasets/kaggle"
            },
            "huggingface": {
                "token": "",
                "cache_dir": "data/datasets/huggingface"
            },
            "quandl": {
                "api_key": ""
            },
            "alpha_vantage": {
                "api_key": ""
            },
            "polygon": {
                "api_key": ""
            },
            "popular_datasets": {
                "kaggle": [
                    "borismarjanovic/price-volume-data-for-all-us-stocks-etfs",
                    "jacksoncrow/stock-market-dataset",
                    "dgawlik/nyse",
                    "paultimothymooney/stock-market-data",
                    "cnic92/200-financial-indicators-of-us-stocks-20142018"
                ],
                "huggingface": [
                    "gmongaras/nasdaq_stock_data",
                    "codesignal/stock-price-data",
                    "vivekkevin/financial-dataset"
                ]
            }
        }
    
    def _init_kaggle(self):
        """Initialize Kaggle API"""
        if kaggle is None:
            print("Kaggle not installed. Install with: pip install kaggle")
            self.kaggle_api = None
            return
        
        try:
            self.kaggle_api = KaggleApi()
            self.kaggle_api.authenticate()
            print("Kaggle API initialized")
        except Exception as e:
            print(f"Failed to initialize Kaggle API: {e}")
            print("Make sure you have ~/.kaggle/kaggle.json with your credentials")
            self.kaggle_api = None
    
    def _init_quandl(self):
        """Initialize Quandl API"""
        if quandl is None:
            print("Quandl not installed. Install with: pip install quandl")
            return
        
        api_key = self.config.get("quandl", {}).get("api_key", "")
        if api_key:
            quandl.ApiConfig.api_key = api_key
            print("Quandl API initialized")
        else:
            print("Quandl API key not provided in config")
    
    def _init_polygon(self):
        """Initialize Polygon.io API"""
        if RESTClient is None:
            print("Polygon not installed. Install with: pip install polygon-api-client")
            self.polygon_client = None
            return
        
        api_key = self.config.get("polygon", {}).get("api_key", "")
        if api_key:
            self.polygon_client = RESTClient(api_key)
            print("Polygon.io API initialized")
        else:
            print("Polygon.io API key not provided in config")
            self.polygon_client = None
    
    # ============ KAGGLE METHODS ============
    
    def list_kaggle_datasets(self, search: str = "stock market") -> List[Dict[str, str]]:
        """
        List Kaggle datasets matching search query
        
        Args:
            search: Search query
        
        Returns:
            List of dataset information
        """
        if self.kaggle_api is None:
            raise RuntimeError("Kaggle API not initialized")
        
        datasets = self.kaggle_api.dataset_list(search=search, page=1)
        
        results = []
        for dataset in datasets[:20]:  # Limit to top 20
            results.append({
                'ref': dataset.ref,
                'title': dataset.title,
                'size': dataset.size,
                'last_updated': str(dataset.lastUpdated),
                'download_count': dataset.downloadCount,
                'url': f"https://www.kaggle.com/datasets/{dataset.ref}"
            })
        
        return results
    
    def download_kaggle_dataset(self, dataset_ref: str, 
                               unzip: bool = True,
                               output_path: Optional[str] = None) -> Path:
        """
        Download a Kaggle dataset
        
        Args:
            dataset_ref: Dataset reference (e.g., 'username/dataset-name')
            unzip: Whether to unzip the downloaded file
            output_path: Custom output path
        
        Returns:
            Path to downloaded dataset
        """
        if self.kaggle_api is None:
            raise RuntimeError("Kaggle API not initialized")
        
        if output_path is None:
            output_path = self.data_folder / "kaggle" / dataset_ref.split('/')[-1]
        else:
            output_path = Path(output_path)
        
        output_path.mkdir(parents=True, exist_ok=True)
        
        print(f"Downloading Kaggle dataset: {dataset_ref}")
        self.kaggle_api.dataset_download_files(
            dataset_ref,
            path=str(output_path),
            unzip=unzip
        )
        
        print(f"Dataset downloaded to: {output_path}")
        return output_path
    
    def get_popular_kaggle_datasets(self) -> List[str]:
        """Get list of popular trading-related Kaggle datasets"""
        return self.config.get("popular_datasets", {}).get("kaggle", [])
    
    # ============ HUGGING FACE METHODS ============
    
    def search_huggingface_datasets(self, query: str = "stock", 
                                   limit: int = 20) -> List[Dict[str, str]]:
        """
        Search Hugging Face datasets
        
        Args:
            query: Search query
            limit: Maximum number of results
        
        Returns:
            List of dataset information
        """
        if huggingface_hub is None:
            raise RuntimeError("Hugging Face Hub not installed. Install with: pip install huggingface_hub datasets")
        
        datasets = list(huggingface_hub.list_datasets(search=query, limit=limit))
        
        results = []
        for dataset in datasets:
            results.append({
                'id': dataset.id,
                'author': dataset.author if hasattr(dataset, 'author') else 'Unknown',
                'downloads': dataset.downloads if hasattr(dataset, 'downloads') else 0,
                'url': f"https://huggingface.co/datasets/{dataset.id}"
            })
        
        return results
    
    def load_huggingface_dataset(self, dataset_name: str, 
                                split: Optional[str] = None,
                                cache_dir: Optional[str] = None) -> Any:
        """
        Load a Hugging Face dataset
        
        Args:
            dataset_name: Name of the dataset (e.g., 'username/dataset-name')
            split: Dataset split to load ('train', 'test', etc.)
            cache_dir: Custom cache directory
        
        Returns:
            Dataset object
        """
        if load_dataset is None:
            raise RuntimeError("Datasets library not installed. Install with: pip install datasets")
        
        if cache_dir is None:
            cache_dir = self.config.get("huggingface", {}).get("cache_dir")
        
        print(f"Loading Hugging Face dataset: {dataset_name}")
        dataset = load_dataset(dataset_name, split=split, cache_dir=cache_dir)
        
        print(f"Dataset loaded: {dataset}")
        return dataset
    
    def huggingface_to_dataframe(self, dataset) -> pd.DataFrame:
        """
        Convert Hugging Face dataset to pandas DataFrame
        
        Args:
            dataset: Hugging Face dataset object
        
        Returns:
            DataFrame
        """
        return pd.DataFrame(dataset)
    
    def get_popular_huggingface_datasets(self) -> List[str]:
        """Get list of popular trading-related Hugging Face datasets"""
        return self.config.get("popular_datasets", {}).get("huggingface", [])
    
    # ============ QUANDL METHODS ============
    
    def get_quandl_data(self, database_code: str, dataset_code: str,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       save_to_db: bool = True) -> pd.DataFrame:
        """
        Get data from Quandl
        
        Args:
            database_code: Database code (e.g., 'WIKI', 'EOD')
            dataset_code: Dataset code (e.g., 'AAPL')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            save_to_db: Whether to save data to database
        
        Returns:
            DataFrame with data
        """
        if quandl is None:
            raise RuntimeError("Quandl not installed")
        
        quandl_code = f"{database_code}/{dataset_code}"
        print(f"Fetching Quandl data: {quandl_code}")
        
        df = quandl.get(quandl_code, start_date=start_date, end_date=end_date)
        df = df.reset_index()
        df['source'] = 'quandl'
        df['dataset_code'] = dataset_code
        
        # Save to database if enabled
        if save_to_db and self.db:
            try:
                # Use smart database if available
                if hasattr(self.db, 'store_market_data'):
                    # Rename columns to match schema if needed
                    if 'Date' in df.columns:
                        df = df.rename(columns={'Date': 'timestamp'})
                    if 'Close' in df.columns:
                        # Map OHLCV columns if present
                        column_mapping = {
                            'Open': 'open',
                            'High': 'high',
                            'Low': 'low',
                            'Close': 'close',
                            'Volume': 'volume'
                        }
                        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
                    
                    df['symbol'] = dataset_code
                    df['interval'] = '1d'  # Quandl typically provides daily data
                    
                    self.db.store_market_data(
                        df=df,
                        source='quandl',
                        symbol=dataset_code,
                        interval='1d'
                    )
                    print(f"Data saved to smart database: quandl/{dataset_code}")
                else:
                    # Legacy database
                    table_name = f"quandl_{database_code}_{dataset_code}"
                    self.db.insert_dataframe(table_name, df, if_exists='append')
                    
                    filename = f"quandl_{database_code}_{dataset_code}"
                    self.db.save_to_parquet(df, filename)
                    print(f"Data saved to database and parquet: {filename}")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return df
    
    def search_quandl(self, query: str, per_page: int = 10) -> List[Dict[str, Any]]:
        """
        Search Quandl datasets
        
        Args:
            query: Search query
            per_page: Results per page
        
        Returns:
            List of dataset information
        """
        if quandl is None:
            raise RuntimeError("Quandl not installed")
        
        results = quandl.search(query, per_page=per_page)
        return results.to_dict('records')
    
    # ============ ALPHA VANTAGE METHODS ============
    
    def get_alpha_vantage_data(self, symbol: str, function: str = "TIME_SERIES_DAILY",
                              outputsize: str = "full", save_to_db: bool = True) -> pd.DataFrame:
        """
        Get data from Alpha Vantage
        
        Args:
            symbol: Stock symbol
            function: API function (TIME_SERIES_DAILY, TIME_SERIES_INTRADAY, etc.)
            outputsize: 'compact' or 'full'
            save_to_db: Whether to save data to database
        
        Returns:
            DataFrame with data
        """
        if requests is None:
            raise RuntimeError("Requests not installed")
        
        api_key = self.config.get("alpha_vantage", {}).get("api_key", "")
        if not api_key:
            raise ValueError("Alpha Vantage API key not provided in config")
        
        url = "https://www.alphavantage.co/query"
        params = {
            "function": function,
            "symbol": symbol,
            "apikey": api_key,
            "outputsize": outputsize,
            "datatype": "json"
        }
        
        print(f"Fetching Alpha Vantage data for {symbol}...")
        response = requests.get(url, params=params)
        data = response.json()
        
        # Parse the response based on function type
        if "Time Series" in str(data.keys()):
            time_series_key = [k for k in data.keys() if "Time Series" in k][0]
            df = pd.DataFrame.from_dict(data[time_series_key], orient='index')
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # Clean column names
            df.columns = [col.split('. ')[1] if '. ' in col else col for col in df.columns]
            df = df.apply(pd.to_numeric)
            df = df.reset_index()
            df.rename(columns={'index': 'timestamp'}, inplace=True)
            df['symbol'] = symbol
            df['source'] = 'alpha_vantage'
            
            # Save to database if enabled
            if save_to_db and self.db:
                try:
                    # Use smart database if available
                    if hasattr(self.db, 'store_market_data'):
                        # Map columns to match schema
                        column_mapping = {
                            'open': 'open',
                            'high': 'high',
                            'low': 'low',
                            'close': 'close',
                            'volume': 'volume'
                        }
                        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})
                        
                        # Determine interval from function name
                        interval = '1d'  # default
                        if 'INTRADAY' in function:
                            interval = '1h'  # could be parsed from function params
                        elif 'WEEKLY' in function:
                            interval = '1w'
                        elif 'MONTHLY' in function:
                            interval = '1M'
                        
                        self.db.store_market_data(
                            df=df,
                            source='alpha_vantage',
                            symbol=symbol,
                            interval=interval
                        )
                        print(f"Data saved to smart database: alpha_vantage/{symbol}")
                    else:
                        # Legacy database
                        table_name = f"alpha_vantage_{symbol}"
                        self.db.insert_dataframe(table_name, df, if_exists='append')
                        
                        filename = f"alpha_vantage_{symbol}"
                        self.db.save_to_parquet(df, filename)
                        print(f"Data saved to database and parquet: {filename}")
                except Exception as e:
                    print(f"Failed to save to database: {e}")
            
            return df
        else:
            raise ValueError(f"Unexpected response format: {data}")
    
    # ============ POLYGON.IO METHODS ============
    
    def get_polygon_aggregates(self, ticker: str, multiplier: int = 1,
                              timespan: str = "day", from_date: str = None,
                              to_date: str = None, limit: int = 5000,
                              save_to_db: bool = True) -> pd.DataFrame:
        """
        Get aggregate bars from Polygon.io
        
        Args:
            ticker: Stock ticker
            multiplier: Size of timespan multiplier
            timespan: Size of time window ('minute', 'hour', 'day', 'week', 'month', etc.)
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            limit: Number of results
            save_to_db: Whether to save data to database
        
        Returns:
            DataFrame with aggregate data
        """
        if self.polygon_client is None:
            raise RuntimeError("Polygon.io API not initialized")
        
        from datetime import datetime, timedelta
        
        if from_date is None:
            from_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if to_date is None:
            to_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"Fetching Polygon.io data for {ticker}...")
        
        aggs = []
        for agg in self.polygon_client.list_aggs(
            ticker=ticker,
            multiplier=multiplier,
            timespan=timespan,
            from_=from_date,
            to=to_date,
            limit=limit
        ):
            aggs.append({
                'timestamp': pd.to_datetime(agg.timestamp, unit='ms'),
                'open': agg.open,
                'high': agg.high,
                'low': agg.low,
                'close': agg.close,
                'volume': agg.volume,
                'vwap': agg.vwap if hasattr(agg, 'vwap') else None,
                'transactions': agg.transactions if hasattr(agg, 'transactions') else None
            })
        
        df = pd.DataFrame(aggs)
        df['symbol'] = ticker
        df['source'] = 'polygon'
        df['timespan'] = timespan
        
        # Save to database if enabled
        if save_to_db and self.db:
            try:
                # Use smart database if available
                if hasattr(self.db, 'store_market_data'):
                    # Convert timespan to interval format
                    interval_map = {
                        'minute': f'{multiplier}m',
                        'hour': f'{multiplier}h',
                        'day': f'{multiplier}d' if multiplier == 1 else f'{multiplier}d',
                        'week': f'{multiplier}w',
                        'month': f'{multiplier}M'
                    }
                    interval = interval_map.get(timespan, f'{multiplier}{timespan[0]}')
                    
                    self.db.store_market_data(
                        df=df,
                        source='polygon',
                        symbol=ticker,
                        interval=interval
                    )
                    print(f"Data saved to smart database: polygon/{ticker}")
                else:
                    # Legacy database
                    table_name = f"polygon_{ticker}_{timespan}"
                    self.db.insert_dataframe(table_name, df, if_exists='append')
                    
                    filename = f"polygon_{ticker}_{timespan}"
                    self.db.save_to_parquet(df, filename)
                    print(f"Data saved to database and parquet: {filename}")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return df
    
    def get_polygon_tickers(self, market: str = "stocks", 
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get list of tickers from Polygon.io
        
        Args:
            market: Market type ('stocks', 'crypto', 'fx', etc.)
            limit: Number of results
        
        Returns:
            List of ticker information
        """
        if self.polygon_client is None:
            raise RuntimeError("Polygon.io API not initialized")
        
        tickers = []
        for ticker in self.polygon_client.list_tickers(market=market, limit=limit):
            tickers.append({
                'ticker': ticker.ticker,
                'name': ticker.name,
                'market': ticker.market,
                'locale': ticker.locale,
                'primary_exchange': ticker.primary_exchange if hasattr(ticker, 'primary_exchange') else None,
                'type': ticker.type if hasattr(ticker, 'type') else None,
                'active': ticker.active if hasattr(ticker, 'active') else None,
                'currency_name': ticker.currency_name if hasattr(ticker, 'currency_name') else None
            })
        
        return tickers
    
    # ============ UTILITY METHODS ============
    
    def get_available_sources(self) -> List[str]:
        """Get list of available data sources"""
        sources = []
        
        if self.kaggle_api is not None:
            sources.append('kaggle')
        if load_dataset is not None:
            sources.append('huggingface')
        if quandl is not None:
            sources.append('quandl')
        if self.config.get("alpha_vantage", {}).get("api_key"):
            sources.append('alpha_vantage')
        if self.polygon_client is not None:
            sources.append('polygon')
        
        return sources
    
    def save_dataset(self, df: pd.DataFrame, name: str, format: str = "parquet",
                    save_to_db: bool = True):
        """
        Save a dataset to the data folder and optionally to database
        
        Args:
            df: DataFrame to save
            name: Name of the dataset
            format: File format ('parquet', 'csv', 'json')
            save_to_db: Whether to also save to database
        """
        output_path = self.data_folder / f"{name}.{format}"
        
        if format == "parquet":
            df.to_parquet(output_path, engine='pyarrow')
        elif format == "csv":
            df.to_csv(output_path, index=True)
        elif format == "json":
            df.to_json(output_path, orient='records', date_format='iso')
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        print(f"Dataset saved to: {output_path}")
        
        # Save to database if enabled
        if save_to_db and self.db:
            try:
                # Use smart database if available
                if hasattr(self.db, 'store_reference_data'):
                    # Determine if this looks like reference data (symbols, tickers, etc.)
                    is_reference = any(col in df.columns for col in ['symbol', 'ticker', 'name', 'exchange'])
                    
                    # Determine if this looks like market data
                    is_market_data = all(col in df.columns for col in ['timestamp', 'open', 'high', 'low', 'close'])
                    
                    if is_market_data and 'symbol' in df.columns:
                        # Store as market data
                        symbol = df['symbol'].iloc[0] if len(df) > 0 else 'unknown'
                        source = df['source'].iloc[0] if 'source' in df.columns else 'dataset'
                        interval = df['interval'].iloc[0] if 'interval' in df.columns else '1d'
                        
                        self.db.store_market_data(
                            df=df,
                            source=source,
                            symbol=symbol,
                            interval=interval
                        )
                        print(f"Dataset saved to smart database as market data: {source}/{symbol}")
                    elif is_reference:
                        # Store as reference data
                        entity_type = name.split('_')[0]  # e.g., 'symbols', 'tickers', etc.
                        self.db.store_reference_data(
                            df=df,
                            entity_type=entity_type
                        )
                        print(f"Dataset saved to smart database as reference data: {entity_type}")
                    else:
                        # Fall back to legacy for unknown data types
                        table_name = f"dataset_{name}"
                        self.db.insert_dataframe(table_name, df, if_exists='replace')
                        print(f"Dataset saved to database table: {table_name}")
                else:
                    # Legacy database
                    table_name = f"dataset_{name}"
                    self.db.insert_dataframe(table_name, df, if_exists='replace')
                    print(f"Dataset also saved to database table: {table_name}")
            except Exception as e:
                print(f"Failed to save to database: {e}")
        
        return output_path
    
    def query_saved_data(self, table_name: str, sql_filter: Optional[str] = None) -> Optional[pd.DataFrame]:
        """
        Query saved dataset from database
        
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
        """List all saved dataset tables"""
        if not self.db:
            return []
        return self.db.list_tables()
    
    def close(self):
        """Close database connection"""
        if self.db:
            self.db.close()
            print("Database connection closed")
    
    def list_downloaded_datasets(self) -> List[str]:
        """List all downloaded datasets in the data folder"""
        datasets = []
        
        for item in self.data_folder.rglob("*"):
            if item.is_file() and item.suffix in ['.parquet', '.csv', '.json']:
                datasets.append(str(item.relative_to(self.data_folder)))
        
        return datasets


def main():
    """CLI interface for datasets engine"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Datasets Engine CLI for massive financial datasets')
    parser.add_argument('--config', default='config/datasets.json', help='Path to config file')
    parser.add_argument('--no-db', action='store_true', help='Disable database integration')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List sources command
    subparsers.add_parser('list-sources', help='List available data sources')
    
    # Kaggle commands
    kaggle_search_parser = subparsers.add_parser('kaggle-search', help='Search Kaggle datasets')
    kaggle_search_parser.add_argument('query', help='Search query')
    
    kaggle_download_parser = subparsers.add_parser('kaggle-download', help='Download Kaggle dataset')
    kaggle_download_parser.add_argument('dataset_ref', help='Dataset reference (username/dataset-name)')
    kaggle_download_parser.add_argument('--no-unzip', action='store_true', help='Do not unzip')
    kaggle_download_parser.add_argument('--output', help='Output path')
    
    subparsers.add_parser('kaggle-popular', help='List popular trading datasets from Kaggle')
    
    # Hugging Face commands
    hf_search_parser = subparsers.add_parser('hf-search', help='Search Hugging Face datasets')
    hf_search_parser.add_argument('query', help='Search query')
    hf_search_parser.add_argument('--limit', type=int, default=20, help='Max results')
    
    hf_load_parser = subparsers.add_parser('hf-load', help='Load Hugging Face dataset')
    hf_load_parser.add_argument('dataset_name', help='Dataset name')
    hf_load_parser.add_argument('--split', help='Dataset split (train, test, etc.)')
    hf_load_parser.add_argument('--output', help='Output file path')
    hf_load_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    
    subparsers.add_parser('hf-popular', help='List popular trading datasets from Hugging Face')
    
    # Quandl commands
    quandl_parser = subparsers.add_parser('quandl', help='Get data from Quandl')
    quandl_parser.add_argument('database_code', help='Database code (e.g., WIKI, EOD)')
    quandl_parser.add_argument('dataset_code', help='Dataset code (e.g., AAPL)')
    quandl_parser.add_argument('--start', help='Start date (YYYY-MM-DD)')
    quandl_parser.add_argument('--end', help='End date (YYYY-MM-DD)')
    quandl_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    quandl_parser.add_argument('--output', help='Output file path')
    
    quandl_search_parser = subparsers.add_parser('quandl-search', help='Search Quandl datasets')
    quandl_search_parser.add_argument('query', help='Search query')
    
    # Alpha Vantage commands
    av_parser = subparsers.add_parser('alpha-vantage', help='Get data from Alpha Vantage')
    av_parser.add_argument('symbol', help='Stock symbol')
    av_parser.add_argument('--function', default='TIME_SERIES_DAILY', help='API function')
    av_parser.add_argument('--outputsize', default='full', choices=['compact', 'full'], help='Output size')
    av_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    av_parser.add_argument('--output', help='Output file path')
    
    # Polygon commands
    polygon_parser = subparsers.add_parser('polygon', help='Get data from Polygon.io')
    polygon_parser.add_argument('ticker', help='Stock ticker')
    polygon_parser.add_argument('--timespan', default='day', help='Timespan (minute, hour, day, week, month)')
    polygon_parser.add_argument('--multiplier', type=int, default=1, help='Timespan multiplier')
    polygon_parser.add_argument('--from', dest='from_date', help='Start date (YYYY-MM-DD)')
    polygon_parser.add_argument('--to', dest='to_date', help='End date (YYYY-MM-DD)')
    polygon_parser.add_argument('--limit', type=int, default=5000, help='Number of results')
    polygon_parser.add_argument('--no-save', action='store_true', help='Do not save to database')
    polygon_parser.add_argument('--output', help='Output file path')
    
    polygon_tickers_parser = subparsers.add_parser('polygon-tickers', help='Get tickers from Polygon.io')
    polygon_tickers_parser.add_argument('--market', default='stocks', help='Market type (stocks, crypto, fx)')
    polygon_tickers_parser.add_argument('--limit', type=int, default=100, help='Number of results')
    polygon_tickers_parser.add_argument('--output', help='Output file path')
    
    # List saved datasets
    subparsers.add_parser('list-datasets', help='List downloaded datasets')
    
    # List saved tables
    subparsers.add_parser('list-tables', help='List saved dataset tables')
    
    # Query saved data
    query_parser = subparsers.add_parser('query', help='Query saved dataset')
    query_parser.add_argument('table_name', help='Table name to query')
    query_parser.add_argument('--filter', help='SQL WHERE clause filter')
    query_parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize datasets engine
    datasets = DatasetsEngine(args.config, use_database=not args.no_db)
    
    try:
        if args.command == 'list-sources':
            sources = datasets.get_available_sources()
            print(f"Available sources ({len(sources)}):")
            for source in sources:
                print(f"  - {source}")
        
        elif args.command == 'kaggle-search':
            results = datasets.list_kaggle_datasets(args.query)
            print(f"Found {len(results)} datasets:")
            for ds in results:
                print(f"  - {ds['title']}")
                print(f"    Ref: {ds['ref']}")
                print(f"    Size: {ds['size']} | Downloads: {ds['download_count']}")
                print(f"    URL: {ds['url']}")
                print()
        
        elif args.command == 'kaggle-download':
            path = datasets.download_kaggle_dataset(
                args.dataset_ref,
                unzip=not args.no_unzip,
                output_path=args.output
            )
            print(f"Downloaded to: {path}")
        
        elif args.command == 'kaggle-popular':
            popular = datasets.get_popular_kaggle_datasets()
            print(f"Popular Kaggle trading datasets ({len(popular)}):")
            for ds in popular:
                print(f"  - {ds}")
        
        elif args.command == 'hf-search':
            results = datasets.search_huggingface_datasets(args.query, args.limit)
            print(f"Found {len(results)} datasets:")
            for ds in results:
                print(f"  - {ds['id']}")
                print(f"    Author: {ds['author']} | Downloads: {ds['downloads']}")
                print(f"    URL: {ds['url']}")
                print()
        
        elif args.command == 'hf-load':
            dataset = datasets.load_huggingface_dataset(args.dataset_name, args.split)
            df = datasets.huggingface_to_dataframe(dataset)
            print(f"Loaded dataset with {len(df)} rows")
            print(df.head())
            
            if not args.no_save and datasets.db:
                datasets.save_dataset(df, f"hf_{args.dataset_name.replace('/', '_')}", save_to_db=True)
            
            if args.output:
                _save_output(df, args.output)
        
        elif args.command == 'hf-popular':
            popular = datasets.get_popular_huggingface_datasets()
            print(f"Popular Hugging Face trading datasets ({len(popular)}):")
            for ds in popular:
                print(f"  - {ds}")
        
        elif args.command == 'quandl':
            df = datasets.get_quandl_data(
                args.database_code,
                args.dataset_code,
                start_date=args.start,
                end_date=args.end,
                save_to_db=not args.no_save
            )
            print(f"Retrieved {len(df)} rows")
            print(df.head())
            if args.output:
                _save_output(df, args.output)
        
        elif args.command == 'quandl-search':
            results = datasets.search_quandl(args.query)
            print(f"Found {len(results)} datasets:")
            for ds in results:
                print(f"  - {ds}")
        
        elif args.command == 'alpha-vantage':
            df = datasets.get_alpha_vantage_data(
                args.symbol,
                function=args.function,
                outputsize=args.outputsize,
                save_to_db=not args.no_save
            )
            print(f"Retrieved {len(df)} rows for {args.symbol}")
            print(df.head())
            if args.output:
                _save_output(df, args.output)
        
        elif args.command == 'polygon':
            df = datasets.get_polygon_aggregates(
                args.ticker,
                multiplier=args.multiplier,
                timespan=args.timespan,
                from_date=args.from_date,
                to_date=args.to_date,
                limit=args.limit,
                save_to_db=not args.no_save
            )
            print(f"Retrieved {len(df)} rows for {args.ticker}")
            print(df.head())
            if args.output:
                _save_output(df, args.output)
        
        elif args.command == 'polygon-tickers':
            tickers = datasets.get_polygon_tickers(args.market, args.limit)
            print(f"Found {len(tickers)} tickers:")
            for ticker in tickers[:20]:
                print(f"  - {ticker['ticker']}: {ticker['name']} ({ticker['type']})")
            if args.output:
                import pandas as pd
                df = pd.DataFrame(tickers)
                _save_output(df, args.output)
        
        elif args.command == 'list-datasets':
            datasets_list = datasets.list_downloaded_datasets()
            print(f"Downloaded datasets ({len(datasets_list)}):")
            for ds in datasets_list:
                print(f"  - {ds}")
        
        elif args.command == 'list-tables':
            tables = datasets.list_saved_tables()
            print(f"Saved tables ({len(tables)}):")
            for table in tables:
                print(f"  - {table}")
        
        elif args.command == 'query':
            df = datasets.query_saved_data(args.table_name, args.filter)
            if df is not None:
                print(df)
                if args.output:
                    _save_output(df, args.output)
    
    finally:
        datasets.close()


def _save_output(df, output_path):
    """Helper function to save DataFrame to file"""
    if output_path.endswith('.csv'):
        df.to_csv(output_path, index=False)
    elif output_path.endswith('.parquet'):
        df.to_parquet(output_path, index=False)
    elif output_path.endswith('.json'):
        df.to_json(output_path, orient='records', date_format='iso')
    print(f"Data saved to {output_path}")


if __name__ == "__main__":
    main()
