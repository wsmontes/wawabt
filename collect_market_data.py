#!/usr/bin/env python3
"""
Collect historical market data (OHLCV curves) for the last years
Supports stocks and crypto from multiple sources
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import time
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.abspath('.'))

from engines.connector import ConnectorEngine
from engines.smart_db import SmartDatabaseManager


class MarketDataCollector:
    """Collect historical market data for multiple symbols"""
    
    def __init__(self, use_smart_db: bool = True):
        """Initialize the market data collector"""
        self.use_smart_db = use_smart_db
        self.connector = ConnectorEngine(use_smart_db=use_smart_db)
        self.smart_db = SmartDatabaseManager() if use_smart_db else None
        
        # Statistics
        self.stats = {
            'total_symbols': 0,
            'successful_symbols': 0,
            'failed_symbols': 0,
            'total_records': 0,
            'symbols_processed': [],
            'symbols_failed': [],
            'start_time': datetime.now(),
            'end_time': None
        }
    
    def collect_stock_data(self, 
                          symbol: str,
                          years: int = 3,
                          interval: str = '1d',
                          source: str = 'yahoo') -> Optional[int]:
        """
        Collect stock data from Yahoo Finance
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'GOOGL')
            years: Number of years of historical data
            interval: Data interval (1d, 1h, etc.)
            source: Data source (yahoo, alpaca, etc.)
            
        Returns:
            Number of records collected
        """
        try:
            print(f"\n📈 Collecting: {symbol} ({interval}, {years} years)")
            
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=years * 365)
            
            # Fetch data
            if source == 'yahoo':
                df = self.connector.get_yahoo_data(
                    symbol=symbol,
                    period=f'{years}y',
                    interval=interval
                )
            else:
                print(f"   ⚠️  Source '{source}' not implemented yet")
                return None
            
            if df is None or df.empty:
                print(f"   ❌ No data retrieved")
                self.stats['failed_symbols'] += 1
                self.stats['symbols_failed'].append({
                    'symbol': symbol,
                    'reason': 'No data'
                })
                return None
            
            records = len(df)
            print(f"   ✅ Retrieved {records} records ({df.index.min()} to {df.index.max()})")
            
            self.stats['successful_symbols'] += 1
            self.stats['total_records'] += records
            self.stats['symbols_processed'].append({
                'symbol': symbol,
                'source': source,
                'interval': interval,
                'records': records
            })
            
            return records
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            self.stats['failed_symbols'] += 1
            self.stats['symbols_failed'].append({
                'symbol': symbol,
                'reason': str(e)[:50]
            })
            return None
    
    def collect_crypto_data(self,
                           symbol: str,
                           years: int = 3,
                           interval: str = '1d',
                           source: str = 'yahoo') -> Optional[int]:
        """
        Collect crypto data
        
        Args:
            symbol: Crypto symbol (e.g., 'BTC-USD', 'ETH-USD')
            years: Number of years of historical data
            interval: Data interval
            source: Data source (yahoo, binance, ccxt)
        """
        try:
            print(f"\n₿ Collecting: {symbol} ({interval}, {years} years)")
            
            if source == 'yahoo':
                df = self.connector.get_yahoo_data(
                    symbol=symbol,
                    period=f'{years}y',
                    interval=interval
                )
            elif source == 'binance':
                # Convert symbol format (BTC-USD -> BTCUSDT)
                binance_symbol = symbol.replace('-USD', 'USDT').replace('-', '')
                df = self.connector.get_binance_data(
                    symbol=binance_symbol,
                    interval=interval,
                    limit=1000  # Max for Binance
                )
            else:
                print(f"   ⚠️  Source '{source}' not implemented yet")
                return None
            
            if df is None or df.empty:
                print(f"   ❌ No data retrieved")
                self.stats['failed_symbols'] += 1
                self.stats['symbols_failed'].append({
                    'symbol': symbol,
                    'reason': 'No data'
                })
                return None
            
            records = len(df)
            print(f"   ✅ Retrieved {records} records ({df.index.min()} to {df.index.max()})")
            
            self.stats['successful_symbols'] += 1
            self.stats['total_records'] += records
            self.stats['symbols_processed'].append({
                'symbol': symbol,
                'source': source,
                'interval': interval,
                'records': records
            })
            
            return records
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            self.stats['failed_symbols'] += 1
            self.stats['symbols_failed'].append({
                'symbol': symbol,
                'reason': str(e)[:50]
            })
            return None
    
    def collect_all(self,
                    stocks: List[str] = None,
                    cryptos: List[str] = None,
                    years: int = 3,
                    interval: str = '1d',
                    delay: float = 0.5) -> Dict[str, Any]:
        """
        Collect data for multiple symbols
        
        Args:
            stocks: List of stock symbols
            cryptos: List of crypto symbols
            years: Years of historical data
            interval: Data interval
            delay: Delay between requests
        """
        print("="*70)
        print(" COLLECTING HISTORICAL MARKET DATA")
        print("="*70)
        print(f"\nStart time: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Period: {years} years, Interval: {interval}\n")
        
        # Default symbols if none provided
        if stocks is None:
            stocks = [
                'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META',
                'TSLA', 'NVDA', 'JPM', 'V', 'WMT',
                'JNJ', 'PG', 'MA', 'HD', 'DIS',
                'NFLX', 'PYPL', 'ADBE', 'CRM', 'INTC'
            ]
        
        if cryptos is None:
            cryptos = [
                'BTC-USD', 'ETH-USD', 'BNB-USD', 'XRP-USD', 'ADA-USD',
                'SOL-USD', 'DOGE-USD', 'DOT-USD', 'MATIC-USD', 'AVAX-USD'
            ]
        
        self.stats['total_symbols'] = len(stocks) + len(cryptos)
        
        print(f"📊 Symbols to collect:")
        print(f"   Stocks: {len(stocks)}")
        print(f"   Crypto: {len(cryptos)}")
        print(f"   Total: {self.stats['total_symbols']}")
        print("="*70)
        
        # Collect stocks
        if stocks:
            print(f"\n📈 COLLECTING STOCKS ({len(stocks)} symbols)\n")
            for i, symbol in enumerate(stocks, 1):
                print(f"[{i}/{len(stocks)}]", end=" ")
                self.collect_stock_data(symbol, years=years, interval=interval)
                if i < len(stocks):
                    time.sleep(delay)
        
        # Collect cryptos
        if cryptos:
            print(f"\n\n₿ COLLECTING CRYPTO ({len(cryptos)} symbols)\n")
            for i, symbol in enumerate(cryptos, 1):
                print(f"[{i}/{len(cryptos)}]", end=" ")
                self.collect_crypto_data(symbol, years=years, interval=interval)
                if i < len(cryptos):
                    time.sleep(delay)
        
        # Finalize stats
        self.stats['end_time'] = datetime.now()
        duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        self.stats['duration_seconds'] = duration
        
        return self.stats
    
    def print_summary(self):
        """Print collection summary"""
        print("\n" + "="*70)
        print(" COLLECTION SUMMARY")
        print("="*70)
        
        print(f"\n⏱️  Duration: {self.stats.get('duration_seconds', 0):.1f} seconds")
        
        print(f"\n📊 Symbols:")
        print(f"   Total:      {self.stats['total_symbols']}")
        print(f"   Successful: {self.stats['successful_symbols']} ✅")
        print(f"   Failed:     {self.stats['failed_symbols']} ❌")
        
        print(f"\n📈 Records:")
        print(f"   Total collected: {self.stats['total_records']:,}")
        
        if self.stats['symbols_processed']:
            print(f"\n✅ Successfully Collected ({len(self.stats['symbols_processed'])}):")
            for item in self.stats['symbols_processed'][:15]:  # Show first 15
                print(f"   • {item['symbol']:10} {item['records']:6,} records ({item['interval']})")
            
            if len(self.stats['symbols_processed']) > 15:
                remaining = len(self.stats['symbols_processed']) - 15
                print(f"   ... and {remaining} more")
        
        if self.stats['symbols_failed']:
            print(f"\n❌ Failed Symbols ({len(self.stats['symbols_failed'])}):")
            for item in self.stats['symbols_failed'][:10]:
                print(f"   • {item['symbol']}: {item['reason']}")
            
            if len(self.stats['symbols_failed']) > 10:
                print(f"   ... and {len(self.stats['symbols_failed']) - 10} more")
        
        # Database statistics
        if self.smart_db:
            print(f"\n💾 Database Status:")
            try:
                # Query market data
                market_dir = Path("data/market")
                if market_dir.exists():
                    parquet_files = list(market_dir.rglob("*.parquet"))
                    print(f"   Total parquet files: {len(parquet_files)}")
                    
                    # Count total records
                    import pandas as pd
                    total_records = 0
                    for pf in parquet_files[:50]:  # Sample first 50
                        try:
                            df = pd.read_parquet(pf)
                            total_records += len(df)
                        except:
                            pass
                    
                    if total_records > 0:
                        print(f"   Sample records (first 50 files): {total_records:,}")
                else:
                    print("   No market data directory found")
                    
            except Exception as e:
                print(f"   ⚠️  Could not query database: {e}")
        
        print("\n" + "="*70)


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect historical market data')
    parser.add_argument('--stocks', nargs='+', help='Stock symbols to collect')
    parser.add_argument('--cryptos', nargs='+', help='Crypto symbols to collect')
    parser.add_argument('--years', type=int, default=3, help='Years of historical data')
    parser.add_argument('--interval', default='1d', help='Data interval (1d, 1h, 5m, etc.)')
    parser.add_argument('--delay', type=float, default=0.5, help='Delay between requests')
    parser.add_argument('--no-smart-db', action='store_true', help='Disable SmartDatabaseManager')
    
    args = parser.parse_args()
    
    # Create collector
    collector = MarketDataCollector(use_smart_db=not args.no_smart_db)
    
    # Collect data
    try:
        stats = collector.collect_all(
            stocks=args.stocks,
            cryptos=args.cryptos,
            years=args.years,
            interval=args.interval,
            delay=args.delay
        )
        
        collector.print_summary()
        
        # Exit code based on success
        if stats['successful_symbols'] > 0:
            print(f"\n✅ Collection completed successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ No symbols were successfully collected")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Collection interrupted by user")
        collector.print_summary()
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
