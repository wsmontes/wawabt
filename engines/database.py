"""
Database Engine using DuckDB for managing parquet files
"""
import duckdb
import pandas as pd
from pathlib import Path
from typing import Optional, Union, List, Dict, Any
import json
from datetime import datetime


class DatabaseEngine:
    """
    DuckDB-based database engine for managing parquet files in the data folder
    """
    
    def __init__(self, config_path: str = "config/database.json", data_folder: str = "data"):
        """
        Initialize the database engine
        
        Args:
            config_path: Path to the database configuration JSON file
            data_folder: Root folder for storing parquet files
        """
        self.config = self._load_config(config_path)
        self.data_folder = Path(data_folder)
        self.data_folder.mkdir(exist_ok=True)
        
        # Initialize DuckDB connection (in-memory)
        self.conn = duckdb.connect(database=':memory:')
        
        # Apply configuration settings
        self._apply_settings()
        
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
            "database": {
                "data_folder": "data",
                "default_format": "parquet",
                "compression": "snappy"
            },
            "settings": {
                "memory_limit": "2GB",
                "threads": 4,
                "enable_object_cache": True
            }
        }
    
    def _apply_settings(self):
        """Apply DuckDB configuration settings"""
        settings = self.config.get("settings", {})
        
        if "memory_limit" in settings:
            self.conn.execute(f"SET memory_limit='{settings['memory_limit']}'")
        
        if "threads" in settings:
            self.conn.execute(f"SET threads={settings['threads']}")
        
        if settings.get("enable_object_cache", True):
            self.conn.execute("SET enable_object_cache=true")
    
    def create_table_from_parquet(self, table_name: str, parquet_path: Union[str, Path]):
        """
        Create a table from a parquet file
        
        Args:
            table_name: Name of the table to create
            parquet_path: Path to the parquet file
        """
        parquet_path = Path(parquet_path)
        if not parquet_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {parquet_path}")
        
        query = f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_parquet('{parquet_path}')"
        self.conn.execute(query)
        print(f"Table '{table_name}' created from {parquet_path}")
    
    def save_to_parquet(self, df: pd.DataFrame, filename: str, partition_by: Optional[List[str]] = None):
        """
        Save a DataFrame to a parquet file
        
        Args:
            df: DataFrame to save
            filename: Name of the parquet file (without extension)
            partition_by: Optional list of columns to partition by
        """
        output_path = self.data_folder / f"{filename}.parquet"
        
        compression = self.config.get("database", {}).get("compression", "snappy")
        
        if partition_by:
            # Create partitioned parquet
            partition_path = self.data_folder / filename
            partition_path.mkdir(exist_ok=True)
            df.to_parquet(
                partition_path,
                engine='pyarrow',
                compression=compression,
                partition_cols=partition_by
            )
            print(f"Data saved to partitioned parquet at {partition_path}")
        else:
            # Save as single parquet file
            df.to_parquet(output_path, engine='pyarrow', compression=compression)
            print(f"Data saved to {output_path}")
    
    def load_from_parquet(self, filename: str) -> pd.DataFrame:
        """
        Load data from a parquet file
        
        Args:
            filename: Name of the parquet file (with or without .parquet extension)
        
        Returns:
            DataFrame containing the data
        """
        if not filename.endswith('.parquet'):
            # Try both single file and partitioned directory
            single_file = self.data_folder / f"{filename}.parquet"
            partition_dir = self.data_folder / filename
            
            if single_file.exists():
                filepath = single_file
            elif partition_dir.exists():
                filepath = partition_dir
            else:
                raise FileNotFoundError(f"No parquet file or directory found for: {filename}")
        else:
            filepath = self.data_folder / filename
        
        return pd.read_parquet(filepath)
    
    def query(self, sql: str) -> pd.DataFrame:
        """
        Execute a SQL query and return results as DataFrame
        
        Args:
            sql: SQL query string
        
        Returns:
            Query results as DataFrame
        """
        return self.conn.execute(sql).df()
    
    def query_parquet(self, parquet_path: Union[str, Path], sql_filter: Optional[str] = None) -> pd.DataFrame:
        """
        Query a parquet file directly without loading it into a table
        
        Args:
            parquet_path: Path to parquet file or pattern
            sql_filter: Optional SQL WHERE clause (without WHERE keyword)
        
        Returns:
            Query results as DataFrame
        """
        parquet_path = Path(parquet_path)
        
        query = f"SELECT * FROM read_parquet('{parquet_path}')"
        if sql_filter:
            query += f" WHERE {sql_filter}"
        
        return self.conn.execute(query).df()
    
    def insert_dataframe(self, table_name: str, df: pd.DataFrame, if_exists: str = 'append'):
        """
        Insert a DataFrame into a table
        
        Args:
            table_name: Name of the table
            df: DataFrame to insert
            if_exists: 'append', 'replace', or 'fail'
        """
        if if_exists == 'replace':
            self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        elif if_exists == 'append':
            # Check if table exists
            tables = self.conn.execute("SHOW TABLES").df()
            if table_name in tables['name'].values:
                self.conn.execute(f"INSERT INTO {table_name} SELECT * FROM df")
            else:
                self.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        else:  # fail
            self.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        
        print(f"Data inserted into table '{table_name}'")
    
    def export_table_to_parquet(self, table_name: str, filename: Optional[str] = None):
        """
        Export a table to a parquet file
        
        Args:
            table_name: Name of the table to export
            filename: Output filename (defaults to table_name)
        """
        if filename is None:
            filename = table_name
        
        output_path = self.data_folder / f"{filename}.parquet"
        compression = self.config.get("database", {}).get("compression", "snappy")
        
        query = f"COPY {table_name} TO '{output_path}' (FORMAT PARQUET, COMPRESSION {compression})"
        self.conn.execute(query)
        print(f"Table '{table_name}' exported to {output_path}")
    
    def list_tables(self) -> List[str]:
        """List all tables in the database"""
        result = self.conn.execute("SHOW TABLES").df()
        return result['name'].tolist() if not result.empty else []
    
    def list_parquet_files(self) -> List[str]:
        """List all parquet files in the data folder"""
        parquet_files = []
        for item in self.data_folder.iterdir():
            if item.is_file() and item.suffix == '.parquet':
                parquet_files.append(item.name)
            elif item.is_dir():
                # Check if it's a partitioned parquet directory
                if any(item.glob('**/*.parquet')):
                    parquet_files.append(item.name)
        return parquet_files
    
    def get_table_info(self, table_name: str) -> pd.DataFrame:
        """Get schema information for a table"""
        return self.conn.execute(f"DESCRIBE {table_name}").df()
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            print("Database connection closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


def main():
    """CLI interface for database engine"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Database Engine CLI for managing parquet files with DuckDB')
    parser.add_argument('--config', default='config/database.json', help='Path to config file')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List tables command
    subparsers.add_parser('list-tables', help='List all tables in database')
    
    # List parquet files command
    subparsers.add_parser('list-files', help='List all parquet files')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Execute SQL query')
    query_parser.add_argument('sql', help='SQL query to execute')
    query_parser.add_argument('--output', help='Output file path (csv/parquet/json)')
    
    # Load parquet command
    load_parser = subparsers.add_parser('load', help='Load data from parquet file')
    load_parser.add_argument('filename', help='Parquet filename')
    load_parser.add_argument('--head', type=int, help='Show first N rows')
    load_parser.add_argument('--output', help='Output file path')
    
    # Create table command
    create_parser = subparsers.add_parser('create-table', help='Create table from parquet')
    create_parser.add_argument('table_name', help='Name of table to create')
    create_parser.add_argument('parquet_path', help='Path to parquet file')
    
    # Table info command
    info_parser = subparsers.add_parser('table-info', help='Get table schema information')
    info_parser.add_argument('table_name', help='Name of table')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export table to parquet')
    export_parser.add_argument('table_name', help='Name of table to export')
    export_parser.add_argument('--output', help='Output filename')
    
    # Query parquet command
    query_parquet_parser = subparsers.add_parser('query-parquet', help='Query parquet file directly')
    query_parquet_parser.add_argument('parquet_path', help='Path to parquet file')
    query_parquet_parser.add_argument('--filter', help='SQL WHERE clause filter')
    query_parquet_parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize database
    db = DatabaseEngine(args.config)
    
    try:
        if args.command == 'list-tables':
            tables = db.list_tables()
            print(f"Tables in database ({len(tables)}):")
            for table in tables:
                print(f"  - {table}")
        
        elif args.command == 'list-files':
            files = db.list_parquet_files()
            print(f"Parquet files ({len(files)}):")
            for file in files:
                print(f"  - {file}")
        
        elif args.command == 'query':
            result = db.query(args.sql)
            print(result)
            if args.output:
                if args.output.endswith('.csv'):
                    result.to_csv(args.output, index=False)
                elif args.output.endswith('.parquet'):
                    result.to_parquet(args.output, index=False)
                elif args.output.endswith('.json'):
                    result.to_json(args.output, orient='records')
                print(f"Results saved to {args.output}")
        
        elif args.command == 'load':
            df = db.load_from_parquet(args.filename)
            if args.head:
                print(df.head(args.head))
            else:
                print(df)
            if args.output:
                if args.output.endswith('.csv'):
                    df.to_csv(args.output, index=False)
                elif args.output.endswith('.json'):
                    df.to_json(args.output, orient='records')
                print(f"Data saved to {args.output}")
        
        elif args.command == 'create-table':
            db.create_table_from_parquet(args.table_name, args.parquet_path)
        
        elif args.command == 'table-info':
            info = db.get_table_info(args.table_name)
            print(info)
        
        elif args.command == 'export':
            db.export_table_to_parquet(args.table_name, args.output)
        
        elif args.command == 'query-parquet':
            result = db.query_parquet(args.parquet_path, args.filter)
            print(result)
            if args.output:
                if args.output.endswith('.csv'):
                    result.to_csv(args.output, index=False)
                elif args.output.endswith('.parquet'):
                    result.to_parquet(args.output, index=False)
                elif args.output.endswith('.json'):
                    result.to_json(args.output, orient='records')
                print(f"Results saved to {args.output}")
    
    finally:
        db.close()


if __name__ == "__main__":
    main()
