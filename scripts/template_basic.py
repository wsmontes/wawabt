#!/usr/bin/env python3
"""
Basic Script Template
A simple template for creating custom scripts using the engines
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to import engines
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.database import DatabaseEngine
from engines.connector import ConnectorEngine
from engines.rss import RSSEngine
from engines.datasets import DatasetsEngine


def main():
    """Main script logic"""
    print("=== Basic Script Template ===\n")
    
    # Initialize engines
    print("Initializing engines...")
    db = DatabaseEngine()
    connector = ConnectorEngine()
    # rss = RSSEngine()
    # datasets = DatasetsEngine()
    
    try:
        # Your script logic here
        print("\n--- Example: Fetch and store Yahoo Finance data ---")
        
        # Fetch data
        symbol = "AAPL"
        print(f"Fetching data for {symbol}...")
        df = connector.get_yahoo_data(symbol, period='1mo', interval='1d', save_to_db=True)
        
        print(f"\nRetrieved {len(df)} rows")
        print("\nFirst 5 rows:")
        print(df.head())
        
        print("\nLast 5 rows:")
        print(df.tail())
        
        # Query saved data
        print("\n--- Query saved data ---")
        tables = db.list_tables()
        print(f"Available tables: {tables}")
        
        if tables:
            table_name = tables[0]
            result = db.query(f"SELECT * FROM {table_name} LIMIT 5")
            print(f"\nQuerying table '{table_name}':")
            print(result)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up
        print("\n--- Cleanup ---")
        db.close()
        connector.close()
        print("Done!")


if __name__ == "__main__":
    main()
