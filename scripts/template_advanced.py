#!/usr/bin/env python3
"""
Advanced Script Template
Template for more complex data collection and analysis workflows
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path to import engines
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.database import DatabaseEngine
from engines.connector import ConnectorEngine
from engines.rss import RSSEngine
from engines.datasets import DatasetsEngine


class DataCollectionPipeline:
    """Advanced data collection pipeline"""
    
    def __init__(self):
        """Initialize all engines"""
        print("Initializing engines...")
        self.db = DatabaseEngine()
        self.connector = ConnectorEngine()
        self.rss = RSSEngine()
        self.datasets = DatasetsEngine()
        
    def collect_market_data(self, symbols: list, period: str = '1mo'):
        """Collect market data for multiple symbols"""
        print(f"\n=== Collecting Market Data ===")
        print(f"Symbols: {symbols}")
        
        all_data = []
        
        for symbol in symbols:
            try:
                print(f"\nFetching {symbol}...")
                df = self.connector.get_yahoo_data(
                    symbol, 
                    period=period, 
                    interval='1d',
                    save_to_db=True
                )
                all_data.append(df)
                print(f"  ✓ Retrieved {len(df)} rows")
            except Exception as e:
                print(f"  ✗ Error fetching {symbol}: {e}")
        
        if all_data:
            combined = pd.concat(all_data, ignore_index=True)
            print(f"\nTotal rows collected: {len(combined)}")
            return combined
        
        return None
    
    def collect_news_data(self, categories: list = None):
        """Collect RSS news data"""
        print(f"\n=== Collecting News Data ===")
        
        if categories:
            all_entries = []
            for category in categories:
                print(f"\nFetching category: {category}")
                entries = self.rss.fetch_by_category(category, save_to_db=True)
                all_entries.extend(entries)
                print(f"  ✓ Retrieved {len(entries)} entries")
        else:
            print("Fetching all RSS sources...")
            all_entries = self.rss.fetch_all_sources(save_to_db=True)
        
        print(f"\nTotal entries collected: {len(all_entries)}")
        return all_entries
    
    def analyze_data(self, table_name: str):
        """Perform basic analysis on saved data"""
        print(f"\n=== Analyzing Data: {table_name} ===")
        
        try:
            # Get basic stats
            df = self.db.query(f"SELECT * FROM {table_name}")
            
            if 'close' in df.columns:
                print("\nPrice Statistics:")
                print(f"  Mean: ${df['close'].mean():.2f}")
                print(f"  Min: ${df['close'].min():.2f}")
                print(f"  Max: ${df['close'].max():.2f}")
                print(f"  Std Dev: ${df['close'].std():.2f}")
            
            if 'volume' in df.columns:
                print("\nVolume Statistics:")
                print(f"  Mean: {df['volume'].mean():,.0f}")
                print(f"  Total: {df['volume'].sum():,.0f}")
            
            print(f"\nDate Range:")
            if 'timestamp' in df.columns:
                print(f"  From: {df['timestamp'].min()}")
                print(f"  To: {df['timestamp'].max()}")
            
            return df
            
        except Exception as e:
            print(f"Error analyzing data: {e}")
            return None
    
    def export_results(self, df: pd.DataFrame, name: str, formats: list = ['parquet', 'csv']):
        """Export results in multiple formats"""
        print(f"\n=== Exporting Results: {name} ===")
        
        output_dir = Path('data/exports')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for fmt in formats:
            filename = f"{name}_{timestamp}.{fmt}"
            output_path = output_dir / filename
            
            try:
                if fmt == 'parquet':
                    df.to_parquet(output_path, index=False)
                elif fmt == 'csv':
                    df.to_csv(output_path, index=False)
                elif fmt == 'json':
                    df.to_json(output_path, orient='records', date_format='iso')
                
                print(f"  ✓ Exported to {output_path}")
            except Exception as e:
                print(f"  ✗ Error exporting to {fmt}: {e}")
    
    def run_full_pipeline(self):
        """Run the complete data collection and analysis pipeline"""
        print("=" * 60)
        print("ADVANCED DATA COLLECTION PIPELINE")
        print("=" * 60)
        
        try:
            # 1. Collect market data
            symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA']
            market_data = self.collect_market_data(symbols, period='3mo')
            
            # 2. Collect news data
            news_data = self.collect_news_data(categories=['markets', 'finance'])
            
            # 3. List all saved tables
            print(f"\n=== Saved Tables ===")
            tables = self.db.list_tables()
            for table in tables:
                print(f"  - {table}")
            
            # 4. Analyze data
            if tables:
                for table in tables[:3]:  # Analyze first 3 tables
                    self.analyze_data(table)
            
            # 5. Export combined results
            if market_data is not None:
                self.export_results(market_data, 'combined_market_data')
            
            print("\n" + "=" * 60)
            print("PIPELINE COMPLETED SUCCESSFULLY")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n!!! Pipeline Error: {e}")
            import traceback
            traceback.print_exc()
    
    def cleanup(self):
        """Clean up resources"""
        print("\n=== Cleanup ===")
        self.db.close()
        self.connector.close()
        self.rss.close()
        self.datasets.close()
        print("All connections closed")


def main():
    """Main entry point"""
    pipeline = DataCollectionPipeline()
    
    try:
        pipeline.run_full_pipeline()
    finally:
        pipeline.cleanup()


if __name__ == "__main__":
    main()
