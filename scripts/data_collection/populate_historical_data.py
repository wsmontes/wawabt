#!/usr/bin/env python3
"""
Populate database with historical market data and news
- Last 2 years of data
- Top 50 crypto symbols
- Top 50 stock symbols
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
from time import sleep

sys.path.insert(0, os.path.abspath('.'))

from engines.connector import ConnectorEngine
from engines.smart_db import SmartDatabaseManager
from engines.rss import RSSEngine


# Top 50 Crypto symbols by market cap
TOP_50_CRYPTOS = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'ADAUSDT', 'DOGEUSDT', 'DOTUSDT', 'MATICUSDT', 'LTCUSDT',
    'TRXUSDT', 'AVAXUSDT', 'LINKUSDT', 'ATOMUSDT', 'XLMUSDT',
    'UNIUSDT', 'ETCUSDT', 'FILUSDT', 'APTUSDT', 'NEARUSDT',
    'VETUSDT', 'ALGOUSDT', 'ICPUSDT', 'FTMUSDT', 'AAVEUSDT',
    'SANDUSDT', 'MANAUSDT', 'AXSUSDT', 'THETAUSDT', 'EGLDUSDT',
    'XTZUSDT', 'EOSUSDT', 'FLOWUSDT', 'CHZUSDT', 'ENJUSDT',
    'ZILUSDT', 'BATUSDT', 'ZECUSDT', 'DASHUSDT', 'COMPUSDT',
    'MKRUSDT', 'RUNEUSDT', 'SUSHIUSDT', 'YFIUSDT', 'SNXUSDT',
    'CRVUSDT', '1INCHUSDT', 'KSMUSDT', 'ONEUSDT', 'HBARUSDT'
]

# Top 50 US Stocks by market cap and volume
TOP_50_STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
    'META', 'TSLA', 'BRK-B', 'V', 'JNJ',
    'WMT', 'XOM', 'UNH', 'JPM', 'MA',
    'PG', 'HD', 'CVX', 'LLY', 'ABBV',
    'MRK', 'KO', 'AVGO', 'PEP', 'COST',
    'TMO', 'MCD', 'CSCO', 'ADBE', 'ACN',
    'ABT', 'DHR', 'NKE', 'DIS', 'VZ',
    'CMCSA', 'TXN', 'NFLX', 'PM', 'NEE',
    'WFC', 'CRM', 'UPS', 'INTC', 'AMD',
    'QCOM', 'HON', 'RTX', 'BA', 'IBM'
]


class HistoricalDataPopulator:
    """Populate database with historical market data and news"""
    
    def __init__(self, years: int = 2):
        from engines.connector import EnhancedConnectorEngine
        self.connector = EnhancedConnectorEngine(use_smart_db=True)
        self.smart_db = SmartDatabaseManager()
        self.rss_engine = RSSEngine()
        self.years = years
        
        # Calculate date range
        self.end_date = datetime.now()
        self.start_date = self.end_date - timedelta(days=365 * years)
        
        self.stats = {
            'crypto_symbols': 0,
            'stock_symbols': 0,
            'total_market_records': 0,
            'total_news_records': 0,
            'failed_symbols': [],
            'errors': []
        }
    
    def populate_crypto_data(self, symbols: list, delay: float = 0.5):
        """
        Populate crypto market data from Binance
        """
        print("="*70)
        print(f" COLLECTING CRYPTO DATA - Last {self.years} Years")
        print("="*70)
        print(f"\n📊 Symbols: {len(symbols)}")
        print(f"📅 Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        print()
        
        for i, symbol in enumerate(symbols, 1):
            try:
                print(f"[{i}/{len(symbols)}] Fetching {symbol}...", end=' ')
                
                # Fetch data from Binance
                df = self.connector.get_binance_klines(
                    symbol=symbol,
                    interval='1d',
                    start_str=self.start_date.strftime('%Y-%m-%d'),
                    end_str=self.end_date.strftime('%Y-%m-%d')
                )
                
                if df is not None and not df.empty:
                    print(f"✓ {len(df)} records")
                    self.stats['crypto_symbols'] += 1
                    self.stats['total_market_records'] += len(df)
                else:
                    print(f"⚠️  No data")
                    self.stats['failed_symbols'].append({'symbol': symbol, 'type': 'crypto', 'reason': 'No data returned'})
                
                # Rate limiting
                sleep(delay)
                
            except Exception as e:
                print(f"❌ Error: {str(e)[:50]}")
                self.stats['failed_symbols'].append({'symbol': symbol, 'type': 'crypto', 'error': str(e)})
                self.stats['errors'].append({'symbol': symbol, 'error': str(e)})
        
        print(f"\n✅ Crypto data collection completed: {self.stats['crypto_symbols']}/{len(symbols)} symbols")
    
    def populate_stock_data(self, symbols: list, delay: float = 0.5):
        """
        Populate stock market data from Yahoo Finance
        """
        print("\n" + "="*70)
        print(f" COLLECTING STOCK DATA - Last {self.years} Years")
        print("="*70)
        print(f"\n📊 Symbols: {len(symbols)}")
        print(f"📅 Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
        print()
        
        for i, symbol in enumerate(symbols, 1):
            try:
                print(f"[{i}/{len(symbols)}] Fetching {symbol}...", end=' ')
                
                # Fetch data from Yahoo Finance  
                df = self.connector.get_yahoo_data(
                    symbol=symbol,
                    start=self.start_date.strftime('%Y-%m-%d'),
                    end=self.end_date.strftime('%Y-%m-%d'),
                    interval='1d'
                )
                
                if df is not None and not df.empty:
                    print(f"✓ {len(df)} records")
                    self.stats['stock_symbols'] += 1
                    self.stats['total_market_records'] += len(df)
                else:
                    print(f"⚠️  No data")
                    self.stats['failed_symbols'].append({'symbol': symbol, 'type': 'stock', 'reason': 'No data returned'})
                
                # Rate limiting
                sleep(delay)
                
            except Exception as e:
                print(f"❌ Error: {str(e)[:50]}")
                self.stats['failed_symbols'].append({'symbol': symbol, 'type': 'stock', 'error': str(e)})
                self.stats['errors'].append({'symbol': symbol, 'error': str(e)})
        
        print(f"\n✅ Stock data collection completed: {self.stats['stock_symbols']}/{len(symbols)} symbols")
    
    def populate_news_data(self, delay: float = 1.0):
        """
        Collect historical news from all RSS sources
        """
        print("\n" + "="*70)
        print(f" COLLECTING NEWS DATA")
        print("="*70)
        print()
        
        try:
            print("📰 Fetching from all RSS sources...")
            
            # Fetch from all configured sources
            results = self.rss_engine.fetch_all_sources(delay=delay)
            
            total_news = sum(len(entries) for entries in results.values() if entries)
            successful_sources = sum(1 for entries in results.values() if entries)
            
            self.stats['total_news_records'] = total_news
            
            print(f"\n✅ News collection completed: {total_news} articles from {successful_sources} sources")
            
        except Exception as e:
            print(f"❌ Error collecting news: {e}")
            self.stats['errors'].append({'type': 'news', 'error': str(e)})
    
    def print_summary(self):
        """Print final summary"""
        print("\n" + "="*70)
        print(" POPULATION SUMMARY")
        print("="*70)
        
        print(f"\n📊 Market Data:")
        print(f"   Crypto symbols:    {self.stats['crypto_symbols']}/{len(TOP_50_CRYPTOS)}")
        print(f"   Stock symbols:     {self.stats['stock_symbols']}/{len(TOP_50_STOCKS)}")
        print(f"   Total records:     {self.stats['total_market_records']:,}")
        
        print(f"\n📰 News Data:")
        print(f"   Total articles:    {self.stats['total_news_records']:,}")
        
        if self.stats['failed_symbols']:
            print(f"\n⚠️  Failed Symbols ({len(self.stats['failed_symbols'])}):")
            # Group by type
            failed_crypto = [s for s in self.stats['failed_symbols'] if s.get('type') == 'crypto']
            failed_stock = [s for s in self.stats['failed_symbols'] if s.get('type') == 'stock']
            
            if failed_crypto:
                print(f"   Crypto: {', '.join([s['symbol'] for s in failed_crypto[:10]])}")
                if len(failed_crypto) > 10:
                    print(f"           ... and {len(failed_crypto) - 10} more")
            
            if failed_stock:
                print(f"   Stocks: {', '.join([s['symbol'] for s in failed_stock[:10]])}")
                if len(failed_stock) > 10:
                    print(f"           ... and {len(failed_stock) - 10} more")
        
        if self.stats['errors']:
            print(f"\n❌ Errors ({len(self.stats['errors'])}):")
            for error in self.stats['errors'][:5]:
                print(f"   • {error.get('symbol', error.get('type', 'unknown'))}: {str(error['error'])[:60]}")
            if len(self.stats['errors']) > 5:
                print(f"   ... and {len(self.stats['errors']) - 5} more errors")
        
        # Database status
        print(f"\n💾 Database Status:")
        try:
            # Check market data
            sample_crypto = self.smart_db.query_market_data(symbol='BTCUSDT', source='binance', interval='1d')
            sample_stock = self.smart_db.query_market_data(symbol='AAPL', source='yahoo_finance', interval='1d')
            
            if not sample_crypto.empty:
                print(f"   ✓ Crypto data accessible: BTC has {len(sample_crypto)} records")
            if not sample_stock.empty:
                print(f"   ✓ Stock data accessible: AAPL has {len(sample_stock)} records")
            
            # Check news data
            news_data = self.smart_db.query_news_data()
            if not news_data.empty:
                print(f"   ✓ News data accessible: {len(news_data):,} total articles")
                
        except Exception as e:
            print(f"   ⚠️  Could not verify database: {e}")
        
        print("\n" + "="*70)


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate database with historical data')
    parser.add_argument('--years', type=int, default=2,
                       help='Number of years of historical data (default: 2)')
    parser.add_argument('--crypto-only', action='store_true',
                       help='Collect only crypto data')
    parser.add_argument('--stocks-only', action='store_true',
                       help='Collect only stock data')
    parser.add_argument('--news-only', action='store_true',
                       help='Collect only news data')
    parser.add_argument('--skip-news', action='store_true',
                       help='Skip news collection')
    parser.add_argument('--delay', type=float, default=0.5,
                       help='Delay between requests in seconds (default: 0.5)')
    parser.add_argument('--crypto-limit', type=int, default=50,
                       help='Number of crypto symbols to collect (default: 50)')
    parser.add_argument('--stock-limit', type=int, default=50,
                       help='Number of stock symbols to collect (default: 50)')
    
    args = parser.parse_args()
    
    populator = HistoricalDataPopulator(years=args.years)
    
    print("="*70)
    print(" HISTORICAL DATA POPULATOR")
    print("="*70)
    print(f"\n⏰ Date Range: {populator.start_date.strftime('%Y-%m-%d')} to {populator.end_date.strftime('%Y-%m-%d')}")
    print(f"📊 Crypto symbols: {args.crypto_limit}")
    print(f"📈 Stock symbols: {args.stock_limit}")
    print(f"⏱️  Delay: {args.delay}s between requests")
    print()
    
    # Collect data based on flags
    if args.news_only:
        populator.populate_news_data(delay=args.delay)
    elif args.crypto_only:
        populator.populate_crypto_data(TOP_50_CRYPTOS[:args.crypto_limit], delay=args.delay)
    elif args.stocks_only:
        populator.populate_stock_data(TOP_50_STOCKS[:args.stock_limit], delay=args.delay)
    else:
        # Collect everything
        populator.populate_crypto_data(TOP_50_CRYPTOS[:args.crypto_limit], delay=args.delay)
        populator.populate_stock_data(TOP_50_STOCKS[:args.stock_limit], delay=args.delay)
        
        if not args.skip_news:
            populator.populate_news_data(delay=args.delay)
    
    populator.print_summary()
    
    if populator.stats['total_market_records'] > 0 or populator.stats['total_news_records'] > 0:
        print("\n✅ Population completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ No data was collected")
        sys.exit(1)


if __name__ == "__main__":
    main()
