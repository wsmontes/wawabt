#!/usr/bin/env python3
"""
Batch Data Collection Script
Template for collecting data for multiple symbols in batch
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

# Add parent directory to path to import engines
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.database import DatabaseEngine
from engines.connector import ConnectorEngine


def collect_batch_data(symbols: list, source: str = 'yahoo', **kwargs):
    """
    Collect data for multiple symbols in batch
    
    Args:
        symbols: List of stock symbols
        source: Data source ('yahoo', 'ccxt', 'binance', 'alpaca')
        **kwargs: Additional arguments for the specific data source
    """
    print(f"=== Batch Data Collection ===")
    print(f"Source: {source}")
    print(f"Symbols: {symbols}")
    print(f"Arguments: {kwargs}\n")
    
    connector = ConnectorEngine()
    db = DatabaseEngine()
    
    results = {
        'successful': [],
        'failed': []
    }
    
    try:
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i}/{len(symbols)}] Processing {symbol}...")
            
            try:
                if source == 'yahoo':
                    df = connector.get_yahoo_data(
                        symbol,
                        period=kwargs.get('period', '1mo'),
                        interval=kwargs.get('interval', '1d'),
                        save_to_db=True
                    )
                
                elif source == 'ccxt':
                    df = connector.get_ccxt_ohlcv(
                        symbol,
                        timeframe=kwargs.get('timeframe', '1d'),
                        limit=kwargs.get('limit', 100),
                        save_to_db=True
                    )
                
                elif source == 'binance':
                    df = connector.get_binance_klines(
                        symbol,
                        interval=kwargs.get('interval', '1d'),
                        limit=kwargs.get('limit', 500),
                        save_to_db=True
                    )
                
                else:
                    print(f"  ✗ Unsupported source: {source}")
                    results['failed'].append(symbol)
                    continue
                
                print(f"  ✓ Success: {len(df)} rows retrieved")
                results['successful'].append(symbol)
                
            except Exception as e:
                print(f"  ✗ Error: {e}")
                results['failed'].append(symbol)
        
        # Print summary
        print(f"\n=== Summary ===")
        print(f"Successful: {len(results['successful'])}/{len(symbols)}")
        print(f"Failed: {len(results['failed'])}/{len(symbols)}")
        
        if results['failed']:
            print(f"\nFailed symbols: {', '.join(results['failed'])}")
        
        # List saved data
        print(f"\n=== Saved Data ===")
        tables = db.list_tables()
        print(f"Total tables: {len(tables)}")
        for table in tables[-10:]:  # Show last 10 tables
            print(f"  - {table}")
        
        return results
        
    finally:
        connector.close()
        db.close()


def main():
    """Main entry point with CLI"""
    parser = argparse.ArgumentParser(description='Batch data collection script')
    parser.add_argument('symbols', nargs='+', help='List of symbols to collect')
    parser.add_argument('--source', default='yahoo', choices=['yahoo', 'ccxt', 'binance', 'alpaca'],
                       help='Data source')
    parser.add_argument('--period', default='1mo', help='Period for Yahoo Finance (1d, 5d, 1mo, 1y, max)')
    parser.add_argument('--interval', default='1d', help='Data interval')
    parser.add_argument('--timeframe', default='1d', help='Timeframe for CCXT')
    parser.add_argument('--limit', type=int, default=100, help='Number of candles to fetch')
    
    args = parser.parse_args()
    
    # Prepare kwargs
    kwargs = {
        'period': args.period,
        'interval': args.interval,
        'timeframe': args.timeframe,
        'limit': args.limit
    }
    
    # Run batch collection
    collect_batch_data(args.symbols, args.source, **kwargs)


if __name__ == "__main__":
    main()
