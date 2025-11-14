#!/usr/bin/env python3
"""
Scheduled Data Collection Script
Template for scheduled/automated data collection using cron or task scheduler
"""
import sys
import os
from pathlib import Path
from datetime import datetime
import logging

# Add parent directory to path to import engines
sys.path.insert(0, str(Path(__file__).parent.parent))

from engines.database import DatabaseEngine
from engines.connector import ConnectorEngine
from engines.rss import RSSEngine


# Setup logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"scheduled_collection_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ScheduledCollector:
    """Scheduled data collector"""
    
    def __init__(self):
        """Initialize engines"""
        logger.info("Initializing engines...")
        self.db = DatabaseEngine()
        self.connector = ConnectorEngine()
        self.rss = RSSEngine()
        
    def collect_watchlist(self, watchlist: list):
        """Collect data for watchlist symbols"""
        logger.info(f"Collecting data for {len(watchlist)} symbols")
        
        for symbol in watchlist:
            try:
                logger.info(f"Fetching {symbol}...")
                df = self.connector.get_yahoo_data(
                    symbol,
                    period='1d',
                    interval='1h',
                    save_to_db=True
                )
                logger.info(f"  ✓ {symbol}: {len(df)} rows")
            except Exception as e:
                logger.error(f"  ✗ {symbol}: {e}")
    
    def collect_crypto_pairs(self, pairs: list):
        """Collect crypto data"""
        logger.info(f"Collecting crypto data for {len(pairs)} pairs")
        
        for pair in pairs:
            try:
                logger.info(f"Fetching {pair}...")
                df = self.connector.get_ccxt_ohlcv(
                    pair,
                    timeframe='1h',
                    limit=24,
                    save_to_db=True
                )
                logger.info(f"  ✓ {pair}: {len(df)} rows")
            except Exception as e:
                logger.error(f"  ✗ {pair}: {e}")
    
    def collect_news(self):
        """Collect news from RSS feeds"""
        logger.info("Collecting news from RSS feeds")
        
        try:
            entries = self.rss.fetch_all_sources(save_to_db=True)
            logger.info(f"  ✓ Collected {len(entries)} news entries")
        except Exception as e:
            logger.error(f"  ✗ RSS collection failed: {e}")
    
    def maintenance(self):
        """Perform database maintenance"""
        logger.info("Performing maintenance...")
        
        try:
            # List current data
            tables = self.db.list_tables()
            logger.info(f"Current tables: {len(tables)}")
            
            files = self.db.list_parquet_files()
            logger.info(f"Parquet files: {len(files)}")
            
            # You can add cleanup logic here
            # For example, delete data older than X days
            
        except Exception as e:
            logger.error(f"Maintenance error: {e}")
    
    def run(self):
        """Run the scheduled collection"""
        logger.info("=" * 60)
        logger.info("STARTING SCHEDULED DATA COLLECTION")
        logger.info("=" * 60)
        
        try:
            # Define your watchlist
            watchlist = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA']
            crypto_pairs = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT']
            
            # Collect data
            self.collect_watchlist(watchlist)
            self.collect_crypto_pairs(crypto_pairs)
            self.collect_news()
            
            # Maintenance
            self.maintenance()
            
            logger.info("=" * 60)
            logger.info("SCHEDULED COLLECTION COMPLETED")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Collection failed: {e}", exc_info=True)
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up...")
        self.db.close()
        self.connector.close()
        self.rss.close()


def main():
    """Main entry point"""
    collector = ScheduledCollector()
    collector.run()


if __name__ == "__main__":
    main()
