#!/usr/bin/env python3
"""
Symbol Reference Engine
Maintains official lists of stock and crypto symbols
"""
import sys
import os
from pathlib import Path
import pandas as pd
import json
import logging
from datetime import datetime
from typing import Dict, List, Set, Optional
import requests
from time import sleep

sys.path.insert(0, os.path.abspath('.'))

from engines.smart_db import SmartDatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SymbolReferenceEngine:
    """Engine to manage and validate financial symbols"""
    
    def __init__(self, cache_file: str = 'config/symbol_reference.json'):
        """Initialize symbol reference engine"""
        self.cache_file = Path(cache_file)
        self.smart_db = SmartDatabaseManager()
        self.symbols_data = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cached symbol data"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded {len(data.get('stocks', {}))} stocks, {len(data.get('cryptos', {}))} cryptos from cache")
                return data
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
        
        return {'stocks': {}, 'cryptos': {}, 'updated_at': None}
    
    def _save_cache(self):
        """Save symbol data to cache"""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.symbols_data['updated_at'] = datetime.now().isoformat()
        
        with open(self.cache_file, 'w') as f:
            json.dump(self.symbols_data, f, indent=2)
        
        logger.info(f"Cache saved: {len(self.symbols_data['stocks'])} stocks, {len(self.symbols_data['cryptos'])} cryptos")
    
    def fetch_coingecko_list(self) -> Dict[str, str]:
        """Fetch crypto list from CoinGecko"""
        logger.info("Fetching crypto list from CoinGecko...")
        
        try:
            url = "https://api.coingecko.com/api/v3/coins/list"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Map symbol to name and common trading pairs
            cryptos = {}
            for coin in data:
                symbol = coin['symbol'].upper()
                name = coin['name']
                
                # Add base symbol
                cryptos[symbol] = name
                
                # Add USDT pair (most common)
                cryptos[f"{symbol}USDT"] = f"{name} (USDT)"
                
                # Add common variations
                if symbol in ['BTC', 'ETH', 'BNB']:
                    cryptos[f"{symbol}USD"] = f"{name} (USD)"
            
            logger.info(f"Fetched {len(cryptos)} crypto symbols from CoinGecko")
            return cryptos
            
        except Exception as e:
            logger.error(f"Error fetching CoinGecko data: {e}")
            return {}
    
    def fetch_nasdaq_stocks(self) -> Dict[str, str]:
        """Fetch stock list from NASDAQ FTP"""
        logger.info("Fetching stock list from NASDAQ...")
        
        try:
            # NASDAQ provides daily symbol lists
            url = "ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt"
            
            # Try downloading
            import urllib.request
            response = urllib.request.urlopen(url, timeout=30)
            content = response.read().decode('utf-8')
            
            stocks = {}
            for line in content.split('\n')[1:]:  # Skip header
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        symbol = parts[0].strip()
                        name = parts[1].strip()
                        if symbol and name and symbol != 'Symbol':
                            stocks[symbol] = name
            
            logger.info(f"Fetched {len(stocks)} NASDAQ stocks")
            return stocks
            
        except Exception as e:
            logger.error(f"Error fetching NASDAQ data: {e}")
            return {}
    
    def fetch_nyse_stocks(self) -> Dict[str, str]:
        """Fetch stock list from NYSE FTP"""
        logger.info("Fetching stock list from NYSE...")
        
        try:
            url = "ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt"
            
            import urllib.request
            response = urllib.request.urlopen(url, timeout=30)
            content = response.read().decode('utf-8')
            
            stocks = {}
            for line in content.split('\n')[1:]:  # Skip header
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        symbol = parts[0].strip()
                        name = parts[1].strip()
                        if symbol and name and symbol != 'ACT Symbol':
                            stocks[symbol] = name
            
            logger.info(f"Fetched {len(stocks)} NYSE stocks")
            return stocks
            
        except Exception as e:
            logger.error(f"Error fetching NYSE data: {e}")
            return {}
    
    def get_symbols_from_database(self) -> Dict[str, List[str]]:
        """Get all symbols that actually exist in our database"""
        logger.info("Getting symbols from database...")
        
        market_data = self.smart_db.query_market_data()
        
        if market_data.empty:
            logger.warning("No market data in database")
            return {'stocks': [], 'cryptos': []}
        
        unique_symbols = market_data['symbol'].unique().tolist()
        
        # Separate stocks from cryptos (cryptos usually have USDT, USD, BTC suffixes)
        cryptos = [s for s in unique_symbols if any(suffix in s for suffix in ['USDT', 'USD', 'BTC', 'ETH'])]
        stocks = [s for s in unique_symbols if s not in cryptos]
        
        logger.info(f"Found in database: {len(stocks)} stocks, {len(cryptos)} cryptos")
        
        return {'stocks': stocks, 'cryptos': cryptos}
    
    def update_symbol_lists(self, use_external: bool = True):
        """Update symbol reference lists"""
        logger.info("Updating symbol reference lists...")
        
        # Get symbols from database (priority)
        db_symbols = self.get_symbols_from_database()
        
        # Start with database symbols
        stocks = {s: s for s in db_symbols['stocks']}
        cryptos = {s: s for s in db_symbols['cryptos']}
        
        if use_external:
            # Fetch from NASDAQ
            nasdaq_stocks = self.fetch_nasdaq_stocks()
            stocks.update(nasdaq_stocks)
            
            sleep(1)  # Rate limit
            
            # Fetch from NYSE
            nyse_stocks = self.fetch_nyse_stocks()
            stocks.update(nyse_stocks)
            
            sleep(1)  # Rate limit
            
            # Fetch from CoinGecko
            coingecko_cryptos = self.fetch_coingecko_list()
            cryptos.update(coingecko_cryptos)
        
        self.symbols_data['stocks'] = stocks
        self.symbols_data['cryptos'] = cryptos
        
        self._save_cache()
        
        logger.info(f"Symbol lists updated: {len(stocks)} stocks, {len(cryptos)} cryptos")
    
    def get_all_symbols(self) -> Set[str]:
        """Get set of all valid symbols"""
        all_symbols = set()
        all_symbols.update(self.symbols_data['stocks'].keys())
        all_symbols.update(self.symbols_data['cryptos'].keys())
        return all_symbols
    
    def is_valid_symbol(self, symbol: str) -> bool:
        """Check if symbol is valid"""
        symbol = symbol.upper()
        return (symbol in self.symbols_data['stocks'] or 
                symbol in self.symbols_data['cryptos'])
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get information about a symbol"""
        symbol = symbol.upper()
        
        if symbol in self.symbols_data['stocks']:
            return {
                'symbol': symbol,
                'name': self.symbols_data['stocks'][symbol],
                'type': 'stock'
            }
        elif symbol in self.symbols_data['cryptos']:
            return {
                'symbol': symbol,
                'name': self.symbols_data['cryptos'][symbol],
                'type': 'crypto'
            }
        
        return None
    
    def filter_valid_symbols(self, symbols: List[str]) -> List[str]:
        """Filter list to only valid symbols"""
        valid_symbols = self.get_all_symbols()
        return [s for s in symbols if s.upper() in valid_symbols]
    
    def match_text_to_symbols(self, text: str) -> List[str]:
        """Match text to known symbols - conservative approach"""
        if not text:
            return []
        
        text_upper = text.upper()
        matches = set()
        
        # Map of common name patterns to symbols (only major ones)
        name_to_symbol = {
            'BITCOIN': 'BTCUSDT',
            'ETHEREUM': 'ETHUSDT',
            'APPLE': 'AAPL',
            'MICROSOFT': 'MSFT',
            'GOOGLE': 'GOOGL',
            'AMAZON': 'AMZN',
            'TESLA': 'TSLA',
            'META': 'META',
            'FACEBOOK': 'META',
            'NVIDIA': 'NVDA',
        }
        
        # Check for explicit company/crypto names
        for name, symbol in name_to_symbol.items():
            if name in text_upper:
                matches.add(symbol)
        
        # Check for explicit ticker mentions with $ or in uppercase
        import re
        
        # Pattern 1: $SYMBOL (common in financial news)
        dollar_symbols = re.findall(r'\$([A-Z]{1,10})\b', text)
        for symbol in dollar_symbols:
            if self.is_valid_symbol(symbol):
                matches.add(symbol)
        
        # Pattern 2: Ticker in parentheses like "Apple (AAPL)"
        paren_symbols = re.findall(r'\(([A-Z]{2,10})\)', text)
        for symbol in paren_symbols:
            if self.is_valid_symbol(symbol):
                matches.add(symbol)
        
        # Pattern 3: Common crypto pairs (explicit)
        crypto_pairs = re.findall(r'\b([A-Z]{2,6})USDT\b', text_upper)
        for pair in crypto_pairs:
            full_symbol = f"{pair}USDT"
            if self.is_valid_symbol(full_symbol):
                matches.add(full_symbol)
        
        # Pattern 4: Standalone tickers (only if 2-5 chars and validated)
        # Only check words that are clearly separated
        words = re.findall(r'\b([A-Z]{2,5})\b', text)
        for word in words:
            # Skip common words that are not tickers
            if word in ['THE', 'AND', 'FOR', 'ARE', 'BUT', 'NOT', 'YOU', 'ALL', 
                       'CAN', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS', 
                       'NEW', 'NOW', 'OLD', 'SEE', 'TWO', 'WAY', 'WHO', 'WHY',
                       'USA', 'CEO', 'CFO', 'CTO', 'SEC', 'FDA', 'FBI', 'CIA', 
                       'NYSE', 'IPO', 'API', 'USD', 'EUR', 'GBP', 'JPY', 'ATH',
                       'ETF', 'IRS', 'LLC', 'INC', 'LTD', 'CORP', 'CO', 'GROUP']:
                continue
            
            # Only add if it's a known stock in our database
            if word in self.symbols_data['stocks']:
                matches.add(word)
        
        return list(matches)


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Symbol Reference Engine')
    parser.add_argument('--update', action='store_true',
                       help='Update symbol lists from external sources')
    parser.add_argument('--no-external', action='store_true',
                       help='Only use database symbols, skip external APIs')
    parser.add_argument('--validate', type=str,
                       help='Validate a symbol')
    parser.add_argument('--search', type=str,
                       help='Search for symbols in text')
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics')
    
    args = parser.parse_args()
    
    engine = SymbolReferenceEngine()
    
    if args.update:
        engine.update_symbol_lists(use_external=not args.no_external)
    
    elif args.validate:
        info = engine.get_symbol_info(args.validate)
        if info:
            print(f"✅ Valid {info['type']}: {info['symbol']} - {info['name']}")
        else:
            print(f"❌ Invalid symbol: {args.validate}")
    
    elif args.search:
        symbols = engine.match_text_to_symbols(args.search)
        if symbols:
            print(f"Found {len(symbols)} symbols:")
            for symbol in symbols:
                info = engine.get_symbol_info(symbol)
                if info:
                    print(f"  - {info['symbol']}: {info['name']} ({info['type']})")
        else:
            print("No symbols found in text")
    
    elif args.stats:
        print("="*70)
        print(" SYMBOL REFERENCE STATISTICS")
        print("="*70)
        print(f"Stocks: {len(engine.symbols_data['stocks']):,}")
        print(f"Cryptos: {len(engine.symbols_data['cryptos']):,}")
        print(f"Total: {len(engine.get_all_symbols()):,}")
        print(f"Last updated: {engine.symbols_data.get('updated_at', 'Never')}")
        print("="*70)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
