#!/usr/bin/env python3
"""
Ingest crypto market data CSV into the database
Supports OHLCV data with network/blockchain information
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd

sys.path.insert(0, os.path.abspath('.'))

from engines.smart_db import SmartDatabaseManager


class CryptoMarketDataIngestor:
    """Ingest crypto market data from CSV files into the database"""
    
    def __init__(self):
        self.smart_db = SmartDatabaseManager()
        self.stats = {
            'files_processed': 0,
            'total_records': 0,
            'successfully_saved': 0,
            'symbols_processed': 0,
            'failed': 0,
            'errors': []
        }
    
    def ingest_crypto_ohlcv(self, csv_path: str, source_name: str = 'Binance') -> bool:
        """
        Ingest crypto OHLCV data from CSV
        
        Expected columns: symbol, date, open, high, low, close, network
        """
        print(f"📊 Ingesting crypto market data from: {csv_path}")
        
        try:
            # Load CSV
            df = pd.read_csv(csv_path)
            print(f"   Loaded {len(df):,} records")
            
            # Show initial data info
            symbols = df['symbol'].nunique()
            date_range = f"{df['date'].min()} to {df['date'].max()}"
            networks = df['network'].nunique()
            
            print(f"   Symbols: {symbols}")
            print(f"   Date range: {date_range}")
            print(f"   Networks: {networks}")
            
            # Convert date to datetime with UTC timezone
            df['timestamp'] = pd.to_datetime(df['date'], utc=True)
            
            # Prepare data for SmartDatabaseManager
            # Rename columns to match expected format
            market_df = pd.DataFrame()
            market_df['timestamp'] = df['timestamp']
            market_df['symbol'] = df['symbol'].str.replace('USDT', '/USDT')  # Format: BTC/USDT
            market_df['open'] = df['open']
            market_df['high'] = df['high']
            market_df['low'] = df['low']
            market_df['close'] = df['close']
            market_df['volume'] = 0  # Not available in this dataset
            market_df['source'] = source_name
            market_df['interval'] = '1d'  # Daily data
            
            # Add network/blockchain info as metadata (optional)
            market_df['network'] = df['network']
            
            # Filter out invalid data
            market_df = market_df.dropna(subset=['timestamp', 'symbol', 'close'])
            
            print(f"   Valid records after filtering: {len(market_df):,}")
            
            if len(market_df) == 0:
                print("   ⚠️  No valid records to ingest")
                return False
            
            # Save to database - process in batches by symbol for better organization
            symbols_list = market_df['symbol'].unique()
            saved_files_total = 0
            
            print(f"\n   Processing {len(symbols_list)} symbols...")
            
            for i, symbol in enumerate(symbols_list, 1):
                symbol_data = market_df[market_df['symbol'] == symbol].copy()
                
                # Get interval from data
                interval = symbol_data['interval'].iloc[0] if 'interval' in symbol_data.columns else '1d'
                
                # Progress indicator
                if i % 10 == 0:
                    print(f"   [{i}/{len(symbols_list)}] Processing {symbol}... ({len(symbol_data)} records)")
                
                try:
                    # store_market_data expects: df, source, symbol, interval
                    self.smart_db.store_market_data(
                        df=symbol_data,
                        source=source_name,
                        symbol=symbol,
                        interval=interval
                    )
                    saved_files_total += 1
                except Exception as e:
                    print(f"   ⚠️  Error saving {symbol}: {e}")
                    self.stats['errors'].append({'symbol': symbol, 'error': str(e)})
            
            self.stats['files_processed'] += 1
            self.stats['total_records'] += len(df)
            self.stats['successfully_saved'] += len(market_df)
            self.stats['symbols_processed'] = len(symbols_list)
            
            print(f"\n   ✅ Successfully ingested {len(market_df):,} records")
            print(f"   📁 Saved to {saved_files_total} file(s)")
            print(f"   🪙 Processed {len(symbols_list)} unique symbols")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            self.stats['failed'] += 1
            self.stats['errors'].append({'file': csv_path, 'error': str(e)})
            import traceback
            traceback.print_exc()
            return False
    
    def print_summary(self):
        """Print ingestion summary"""
        print("\n" + "="*70)
        print(" MARKET DATA INGESTION SUMMARY")
        print("="*70)
        
        print(f"\n📊 Statistics:")
        print(f"   Files processed:      {self.stats['files_processed']}")
        print(f"   Total records:        {self.stats['total_records']:,}")
        print(f"   Successfully saved:   {self.stats['successfully_saved']:,}")
        print(f"   Symbols processed:    {self.stats['symbols_processed']}")
        print(f"   Failed:               {self.stats['failed']}")
        
        if self.stats['errors']:
            print(f"\n❌ Errors ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:10]:  # Show first 10 errors
                if 'symbol' in error:
                    print(f"   • {error['symbol']}: {error['error'][:80]}")
                else:
                    print(f"   • {error['file']}: {error['error'][:80]}")
            
            if len(self.stats['errors']) > 10:
                print(f"   ... and {len(self.stats['errors']) - 10} more errors")
        
        # Database status
        try:
            # Query one symbol to check
            sample_data = self.smart_db.query_market_data(
                symbol='BTC/USDT',
                source='Binance',
                interval='1d'
            )
            
            print(f"\n💾 Database Status:")
            if not sample_data.empty:
                print(f"   ✓ Data successfully accessible in database")
                print(f"   Sample: BTC/USDT - {len(sample_data)} record(s) found")
            else:
                print(f"   ⚠️  No data found for BTC/USDT (might be stored with different symbol)")
                
        except Exception as e:
            print(f"   ⚠️  Could not query database: {e}")
        
        # Show storage location
        print(f"\n📁 Storage Location:")
        print(f"   data/market/Binance/[SYMBOL]/1d.parquet")
        print(f"   Example: data/market/Binance/BTC_USDT/1d.parquet")
        
        print("\n" + "="*70)


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest crypto market data from CSV files')
    parser.add_argument('files', nargs='+', help='CSV file(s) to ingest')
    parser.add_argument('--source', default='Binance',
                       help='Source name (default: Binance)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without actually ingesting')
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No data will be ingested\n")
    
    ingestor = CryptoMarketDataIngestor()
    
    print("="*70)
    print(" CRYPTO MARKET DATA INGESTOR")
    print("="*70)
    print()
    
    for file_path in args.files:
        if not Path(file_path).exists():
            print(f"❌ File not found: {file_path}")
            continue
        
        if args.dry_run:
            # Just load and show info
            df = pd.read_csv(file_path)
            print(f"📊 {file_path}")
            print(f"   Records: {len(df):,}")
            print(f"   Symbols: {df['symbol'].nunique()}")
            print(f"   Columns: {', '.join(df.columns)}")
            print(f"   Date range: {df['date'].min()} to {df['date'].max()}")
            print()
        else:
            success = ingestor.ingest_crypto_ohlcv(file_path, source_name=args.source)
    
    if not args.dry_run:
        ingestor.print_summary()
        
        if ingestor.stats['successfully_saved'] > 0:
            print("\n✅ Ingestion completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ No records were successfully ingested")
            sys.exit(1)
    else:
        print("✅ Dry run completed - use without --dry-run to actually ingest data")


if __name__ == "__main__":
    main()
