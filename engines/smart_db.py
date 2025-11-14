"""
Smart Database Manager
Handles different data types with intelligent partitioning, deduplication, and organization
"""
import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
import json
from datetime import datetime, timedelta, timezone
import hashlib


class SmartDatabaseManager:
    """
    Intelligent database manager for handling multiple data types:
    - Market data (OHLCV) - partitioned by symbol
    - News/RSS data - partitioned by date
    - Reference data - single files per entity type
    - Analysis data - partitioned by analysis type and symbol
    - Metrics data - partitioned by metric type
    - Logs - partitioned by date
    """
    
    def __init__(self, config_path: str = "config/database.json"):
        """Initialize the smart database manager"""
        self.config = self._load_config(config_path)
        
        # Initialize persistent DuckDB connection
        db_file = self.config.get("database", {}).get("db_file", "data/market_data.duckdb")
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(database=db_file)
        
        self.data_structure = self.config.get("data_structure", {})
        self.schemas = self.config.get("schemas", {})
        
        self._apply_settings()
        self._create_virtual_tables()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config file {config_path} not found, using defaults")
            return {}
    
    def _apply_settings(self):
        """Apply DuckDB configuration settings"""
        settings = self.config.get("settings", {})
        
        if "memory_limit" in settings:
            self.conn.execute(f"SET memory_limit='{settings['memory_limit']}'")
        if "threads" in settings:
            self.conn.execute(f"SET threads={settings['threads']}")
        if settings.get("enable_object_cache", True):
            self.conn.execute("SET enable_object_cache=true")
    
    def _create_virtual_tables(self):
        """Create virtual tables that query parquet files directly"""
        for data_type, structure in self.data_structure.items():
            try:
                # Create schema if not exists
                schema_name = f"{data_type}_schema"
                self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            except:
                pass
    
    def _get_data_path(self, data_type: str, **kwargs) -> Path:
        """
        Generate file path based on data type and parameters
        
        Args:
            data_type: Type of data (market_data, news_data, etc.)
            **kwargs: Parameters for path generation (symbol, source, year, etc.)
        """
        structure = self.data_structure.get(data_type, {})
        path_pattern = structure.get("path_pattern", f"data/{data_type}/{{timestamp}}.parquet")
        
        # Replace placeholders
        path_str = path_pattern
        for key, value in kwargs.items():
            path_str = path_str.replace(f"{{{key}}}", str(value))
        
        # Handle date-based partitioning
        if '{year}' in path_str or '{month}' in path_str:
            now = datetime.now()
            path_str = path_str.replace('{year}', str(now.year))
            path_str = path_str.replace('{month}', f"{now.month:02d}")
        
        # Handle timestamp in filename
        if '{timestamp}' in path_str:
            path_str = path_str.replace('{timestamp}', datetime.now().strftime('%Y%m%d_%H%M%S'))
        
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        return path
    
    def _calculate_hash(self, df: pd.DataFrame, columns: List[str]) -> pd.Series:
        """Calculate hash for deduplication"""
        hash_data = df[columns].astype(str).apply(lambda x: '|'.join(x), axis=1)
        return hash_data.apply(lambda x: hashlib.md5(x.encode()).hexdigest())
    
    def _deduplicate(self, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """Remove duplicates based on data type configuration"""
        if not self.config.get("settings", {}).get("deduplication_enabled", True):
            return df
        
        structure = self.data_structure.get(data_type, {})
        dedup_columns = structure.get("deduplication", "").split(",")
        dedup_columns = [col.strip() for col in dedup_columns if col.strip()]
        
        if dedup_columns:
            # Check which columns exist in the dataframe
            existing_cols = [col for col in dedup_columns if col in df.columns]
            if existing_cols:
                df = df.drop_duplicates(subset=existing_cols, keep='last')
                print(f"Deduplicated on: {', '.join(existing_cols)}")
        
        return df
    
    # ============ MARKET DATA METHODS ============
    
    def store_market_data(self, df: pd.DataFrame, source: str, symbol: str, interval: str):
        """
        Store market data with intelligent partitioning by symbol
        Ensures uniqueness: symbol + timestamp + source + interval
        """
        # Add metadata
        df = df.copy()
        if 'source' not in df.columns:
            df['source'] = source
        if 'symbol' not in df.columns:
            df['symbol'] = symbol
        if 'interval' not in df.columns:
            df['interval'] = interval
        if 'created_at' not in df.columns:
            df['created_at'] = datetime.now()
        
        # Normalize timestamp to timezone-naive for consistency
        if 'timestamp' in df.columns:
            if not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Remove timezone info if present
            if hasattr(df['timestamp'].dtype, 'tz') and df['timestamp'].dtype.tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        
        # Calculate hash for deduplication
        hash_cols = ['symbol', 'timestamp', 'source', 'interval']
        existing_hash_cols = [col for col in hash_cols if col in df.columns]
        if existing_hash_cols:
            df['data_hash'] = self._calculate_hash(df, existing_hash_cols)
        
        # Deduplicate
        df = self._deduplicate(df, 'market_data')
        
        # Get file path
        file_path = self._get_data_path('market_data', source=source, symbol=symbol, interval=interval)
        
        # Merge with existing data if file exists
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            # Normalize existing timestamps too
            if 'timestamp' in existing_df.columns and hasattr(existing_df['timestamp'].dtype, 'tz') and existing_df['timestamp'].dtype.tz is not None:
                existing_df['timestamp'] = existing_df['timestamp'].dt.tz_localize(None)
            
            df = pd.concat([existing_df, df], ignore_index=True)
            df = self._deduplicate(df, 'market_data')
            df = df.sort_values('timestamp')
        
        # Save to parquet
        df.to_parquet(file_path, engine='pyarrow', compression='snappy', index=False)
        
        # Create/update virtual table
        table_name = f"market_{source}_{symbol}_{interval}".replace('/', '_').replace('-', '_')
        self.conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{file_path}')")
        
        print(f"✓ Stored {len(df)} market data rows: {symbol} ({source}/{interval})")
        return file_path
    
    def query_market_data(self, symbol: Optional[str] = None, source: Optional[str] = None,
                         start_date: Optional[str] = None, end_date: Optional[str] = None,
                         interval: Optional[str] = None) -> pd.DataFrame:
        """Query market data across all sources with filters"""
        # Check if any parquet files exist before attempting query
        market_dir = Path("data/market")
        if not market_dir.exists() or not any(market_dir.rglob("*.parquet")):
            print(f"[SmartDB] No parquet files found in data/market")
            return pd.DataFrame()
        
        pattern = "data/market/**/*.parquet"
        
        query = f"SELECT * FROM read_parquet('{pattern}')"
        conditions = []
        
        if symbol:
            conditions.append(f"symbol = '{symbol}'")
        if source:
            conditions.append(f"source = '{source}'")
        if interval:
            conditions.append(f"interval = '{interval}'")
        if start_date:
            conditions.append(f"timestamp >= '{start_date}'")
        if end_date:
            conditions.append(f"timestamp <= '{end_date}'")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp"
        
        print(f"[SmartDB] Executing query: {query}")
        
        try:
            result = self.conn.execute(query).df()
            print(f"[SmartDB] Query successful: {len(result)} rows")
            return result
        except Exception as e:
            print(f"[SmartDB] Query error: {e}")
            return pd.DataFrame()
    
    # ============ NEWS DATA METHODS ============
    
    def store_news_data(self, df: pd.DataFrame, source: str):
        """
        Store news/RSS data partitioned by date OF THE DATA (not current date)
        Ensures uniqueness: link + timestamp
        """
        df = df.copy()
        if 'source' not in df.columns:
            df['source'] = source
        if 'created_at' not in df.columns:
            df['created_at'] = datetime.now(timezone.utc)
        
        # Ensure timestamp is datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        
        # Calculate hash for deduplication
        if 'link' in df.columns and 'timestamp' in df.columns:
            df['content_hash'] = self._calculate_hash(df, ['link', 'timestamp'])
        
        # Deduplicate
        df = self._deduplicate(df, 'news_data')
        
        # Partition by year/month of the DATA timestamp (not current date)
        df['_year'] = df['timestamp'].dt.year
        df['_month'] = df['timestamp'].dt.month
        
        saved_files = []
        total_saved = 0
        
        # Process each partition separately
        for (year, month), group_df in df.groupby(['_year', '_month']):
            # Remove auxiliary columns
            group_df = group_df.drop(columns=['_year', '_month'])
            
            # Get file path based on data timestamp
            file_path = self._get_data_path('news_data', source=source, year=int(year), month=int(month))
            
            # Merge with existing data
            if file_path.exists():
                existing_df = pd.read_parquet(file_path)
                
                # Normalize timestamps to timezone-aware UTC
                if 'timestamp' in existing_df.columns:
                    existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'], utc=True)
                if 'created_at' in existing_df.columns:
                    existing_df['created_at'] = pd.to_datetime(existing_df['created_at'], utc=True)
                
                group_df = pd.concat([existing_df, group_df], ignore_index=True)
                group_df = self._deduplicate(group_df, 'news_data')
                group_df = group_df.sort_values('timestamp')
            
            # Save to parquet
            group_df.to_parquet(file_path, engine='pyarrow', compression='snappy', index=False)
            saved_files.append(file_path)
            total_saved += len(group_df)
            
            # Create/update virtual table
            clean_source = source.replace('/', '_').replace('-', '_').replace(' ', '_')
            table_name = f"news_{clean_source}_{year}_{month:02d}"
            self.conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{file_path}')")
        
        # Create unified view for the source
        clean_source = source.replace('/', '_').replace('-', '_').replace(' ', '_')
        news_dir = Path("data/news") / source
        if news_dir.exists():
            pattern = str(news_dir / "**/*.parquet")
            self.conn.execute(f"CREATE OR REPLACE VIEW news_{clean_source} AS SELECT * FROM read_parquet('{pattern}')")
        
        print(f"✓ Stored {total_saved} news entries in {len(saved_files)} file(s): {source}")
        return saved_files
    
    def query_news_data(self, source: Optional[str] = None, category: Optional[str] = None,
                       start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """Query news data across all sources with filters"""
        # Check if any parquet files exist
        news_dir = Path("data/news")
        if not news_dir.exists() or not any(news_dir.rglob("*.parquet")):
            print(f"[SmartDB] No parquet files found in data/news")
            return pd.DataFrame()
        
        pattern = "data/news/**/*.parquet"
        
        # Use union_by_name to handle schema differences
        query = f"SELECT * FROM read_parquet('{pattern}', union_by_name=true)"
        conditions = []
        
        if source:
            conditions.append(f"source = '{source}'")
        if category:
            conditions.append(f"category = '{category}'")
        if start_date:
            conditions.append(f"timestamp >= '{start_date}'")
        if end_date:
            conditions.append(f"timestamp <= '{end_date}'")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC"
        
        try:
            return self.conn.execute(query).df()
        except Exception as e:
            print(f"Query error: {e}")
            return pd.DataFrame()
    
    # ============ REFERENCE DATA METHODS ============
    
    def store_reference_data(self, df: pd.DataFrame, entity_type: str):
        """
        Store reference data (symbols, exchanges, etc.)
        Single file per entity type, updated on merge
        """
        df = df.copy()
        if 'last_updated' not in df.columns:
            df['last_updated'] = datetime.now()
        
        file_path = self._get_data_path('reference_data', entity_type=entity_type)
        
        # Merge with existing data
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            
            # Determine key column
            key_col = 'symbol' if entity_type == 'symbols' else f"{entity_type}_id"
            if key_col in df.columns and key_col in existing_df.columns:
                # Update existing records, add new ones
                existing_df = existing_df[~existing_df[key_col].isin(df[key_col])]
                df = pd.concat([existing_df, df], ignore_index=True)
        
        df.to_parquet(file_path, engine='pyarrow', compression='snappy', index=False)
        
        table_name = f"ref_{entity_type}"
        self.conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{file_path}')")
        
        print(f"✓ Stored {len(df)} reference records: {entity_type}")
        return file_path
    
    # ============ ANALYSIS DATA METHODS ============
    
    def store_analysis_data(self, df: pd.DataFrame, analysis_type: str, symbol: str):
        """
        Store analysis/ML predictions partitioned by analysis type and symbol
        Ensures uniqueness: symbol + timestamp + analysis_type + model_version
        """
        df = df.copy()
        if 'analysis_type' not in df.columns:
            df['analysis_type'] = analysis_type
        if 'symbol' not in df.columns:
            df['symbol'] = symbol
        if 'created_at' not in df.columns:
            df['created_at'] = datetime.now()
        
        # Deduplicate
        df = self._deduplicate(df, 'analysis_data')
        
        # Get file path with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = self._get_data_path('analysis_data', 
                                       analysis_type=analysis_type,
                                       symbol=symbol,
                                       timestamp=timestamp)
        
        df.to_parquet(file_path, engine='pyarrow', compression='snappy', index=False)
        
        print(f"✓ Stored {len(df)} analysis records: {analysis_type}/{symbol}")
        return file_path
    
    def query_analysis_data(self, analysis_type: Optional[str] = None, 
                           symbol: Optional[str] = None) -> pd.DataFrame:
        """Query analysis data"""
        pattern = "data/analysis/**/*.parquet"
        
        query = f"SELECT * FROM read_parquet('{pattern}')"
        conditions = []
        
        if analysis_type:
            conditions.append(f"analysis_type = '{analysis_type}'")
        if symbol:
            conditions.append(f"symbol = '{symbol}'")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC"
        
        try:
            return self.conn.execute(query).df()
        except Exception as e:
            print(f"Query error: {e}")
            return pd.DataFrame()
    
    # ============ METRICS DATA METHODS ============
    
    def store_metrics_data(self, df: pd.DataFrame, metric_type: str, symbol: str):
        """
        Store calculated metrics partitioned by metric type
        Ensures uniqueness: symbol + timestamp + metric_type
        """
        df = df.copy()
        if 'metric_type' not in df.columns:
            df['metric_type'] = metric_type
        if 'symbol' not in df.columns:
            df['symbol'] = symbol
        if 'created_at' not in df.columns:
            df['created_at'] = datetime.now()
        
        df = self._deduplicate(df, 'metrics_data')
        
        file_path = self._get_data_path('metrics_data', metric_type=metric_type, symbol=symbol)
        
        # Merge with existing
        if file_path.exists():
            existing_df = pd.read_parquet(file_path)
            df = pd.concat([existing_df, df], ignore_index=True)
            df = self._deduplicate(df, 'metrics_data')
            df = df.sort_values('timestamp')
        
        df.to_parquet(file_path, engine='pyarrow', compression='snappy', index=False)
        
        print(f"✓ Stored {len(df)} metrics: {metric_type}/{symbol}")
        return file_path
    
    # ============ UTILITY METHODS ============
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Get summary of all stored data"""
        summary = {}
        
        for data_type in self.data_structure.keys():
            try:
                pattern = self.data_structure[data_type]['path_pattern']
                # Count files matching pattern
                base_path = Path(pattern.split('{')[0])
                if base_path.exists():
                    files = list(base_path.rglob('*.parquet'))
                    total_size = sum(f.stat().st_size for f in files) / (1024**2)  # MB
                    summary[data_type] = {
                        'files': len(files),
                        'size_mb': round(total_size, 2)
                    }
            except:
                pass
        
        return summary
    
    def cleanup_old_data(self, data_type: str = None):
        """Remove old data based on retention policy"""
        print(f"=== Cleanup: {data_type or 'all'} ===")
        
        data_types = [data_type] if data_type else self.data_structure.keys()
        
        for dt in data_types:
            structure = self.data_structure.get(dt, {})
            retention_days = structure.get('retention_days', 0)
            
            if retention_days == 0:
                continue  # Keep forever
            
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            print(f"{dt}: removing data older than {cutoff_date.date()}")
            
            # Implementation depends on partition strategy
            # This is a placeholder for the actual cleanup logic
    
    def vacuum(self):
        """Optimize database"""
        print("Running VACUUM...")
        self.conn.execute("VACUUM")
        print("✓ Database optimized")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("Database connection closed")


if __name__ == "__main__":
    # Test the smart database manager
    db = SmartDatabaseManager()
    
    # Show data summary
    summary = db.get_data_summary()
    print("\nData Summary:")
    for data_type, stats in summary.items():
        print(f"  {data_type}: {stats['files']} files, {stats['size_mb']} MB")
    
    db.close()
