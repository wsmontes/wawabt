#!/usr/bin/env python
# -*- coding: utf-8; py-indent-offset:4 -*-
###############################################################################
#
# Copyright (C) 2025 Wagner Montes
#
# NewsCollectorPipeline: Orquestrador de coleta de notícias
# - Usa RSSEngine para RSS feeds
# - Usa ConnectorEngine.get_alpaca_news() para Alpaca News API
# - Usa NewsEngine para validação/deduplicação
# - Save em news_raw (SmartDatabaseManager)
#
###############################################################################
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import logging
from datetime import datetime, timedelta
from typing import List, Optional
import pandas as pd
import hashlib

from engines.rss import RSSEngine
from engines.connector import ConnectorEngine
from engines.news import NewsEngine
from engines.retry_utils import run_with_retry
from engines.smart_db import SmartDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NewsCollectorPipeline:
    """
    Pipeline orquestrador para coleta de notícias de múltiplas fontes.
    
    Responsabilidades:
    1. Coletar notícias via RSS (RSSEngine)
    2. Coletar notícias via Alpaca News API (ConnectorEngine)
    3. Validar e normalizar (NewsEngine)
    4. Deduplicar por content_hash
    5. Extrair símbolos mencionados
    6. Salvar em news_raw com status='pending'
    
    NÃO duplica código - apenas orquestra engines existentes.
    """
    
    def __init__(self, 
                 rss_config: str = 'config/rss_sources.json',
                 symbols_watchlist: Optional[List[str]] = None):
        """
        Initialize NewsCollectorPipeline.
        
        Args:
            rss_config: Path to RSS configuration
            symbols_watchlist: Optional list of symbols to track for Alpaca news
        """
        self.symbols_watchlist = symbols_watchlist or []
        
        # Initialize engines (reuse existing)
        logger.info("Initializing engines...")
        
        self.rss_engine = RSSEngine(
            config_path=rss_config,
            use_database=True,
            use_smart_db=True
        )
        
        self.connector = ConnectorEngine(use_smart_db=True)
        self.news_engine = NewsEngine(use_database=True)
        self.db = SmartDatabaseManager()
        
        logger.info("NewsCollectorPipeline initialized")
    
    def run(self, lookback_hours: int = 24):
        """
        Execute pipeline: collect news from all sources.
        
        Args:
            lookback_hours: How far back to look for news (default 24h)
        """
        logger.info(f"=== NewsCollectorPipeline.run() - lookback {lookback_hours}h ===")
        
        all_news = []
        
        # 1. Collect from RSS feeds
        logger.info("Collecting from RSS feeds...")
        rss_news = self._collect_rss()
        if not rss_news.empty:
            all_news.append(rss_news)
            logger.info(f"Collected {len(rss_news)} items from RSS")
        
        # 2. Collect from Alpaca News API
        logger.info("Collecting from Alpaca News API...")
        alpaca_news = self._collect_alpaca_news(lookback_hours)
        if not alpaca_news.empty:
            all_news.append(alpaca_news)
            logger.info(f"Collected {len(alpaca_news)} items from Alpaca")
        
        # 3. Combine all sources
        if not all_news:
            logger.info("No news collected")
            return
        
        combined = pd.concat(all_news, ignore_index=True)
        logger.info(f"Total items before dedup: {len(combined)}")
        
        # 4. Validate and normalize via NewsEngine
        validated = self._validate_news(combined)
        logger.info(f"Validated items: {len(validated)}")
        
        # 5. Deduplicate by content_hash
        deduplicated = self._deduplicate(validated)
        logger.info(f"After deduplication: {len(deduplicated)}")
        
        # 6. Extract symbols mentioned
        enriched = self._extract_symbols(deduplicated)
        
        # 7. Save to news_raw with status='pending'
        self._save_to_database(enriched)
        
        logger.info(f"Pipeline complete: {len(enriched)} new articles saved")
    
    def _collect_rss(self) -> pd.DataFrame:
        """Collect from RSS feeds using RSSEngine"""
        try:
            # RSSEngine.fetch_all_feeds() returns list of dicts
            feeds = run_with_retry(
                self.rss_engine.fetch_all_feeds,
                attempts=3,
                base_delay=1.0,
                logger=logger,
            )
            
            if not feeds:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(feeds)
            
            # Standardize columns
            df = df.rename(columns={
                'published': 'timestamp',
                'summary': 'description',
                'feed_name': 'source'
            })
            
            # Ensure required columns
            required = ['timestamp', 'title', 'source']
            for col in required:
                if col not in df.columns:
                    df[col] = ''
            
            return df[['timestamp', 'title', 'description', 'link', 'source']]
            
        except Exception as e:
            logger.error(f"RSS collection error: {e}")
            return pd.DataFrame()
    
    def _collect_alpaca_news(self, lookback_hours: int) -> pd.DataFrame:
        """Collect from Alpaca News API using ConnectorEngine"""
        try:
            end = datetime.now()
            start = end - timedelta(hours=lookback_hours)
            
            # Use existing method
            df = run_with_retry(
                self.connector.get_alpaca_news,
                symbols=self.symbols_watchlist if self.symbols_watchlist else None,
                start=start,
                end=end,
                limit=50,
                save_to_db=False,  # We'll save manually after dedup
                attempts=3,
                base_delay=1.0,
                logger=logger,
            )
            
            if df.empty:
                return pd.DataFrame()
            
            # Standardize columns
            df = df.rename(columns={
                'created_at': 'timestamp',
                'headline': 'title',
                'summary': 'description',
                'url': 'link'
            })
            
            df['source'] = 'alpaca_news'
            
            return df[['timestamp', 'title', 'description', 'link', 'source']]
            
        except Exception as e:
            logger.error(f"Alpaca news collection error: {e}")
            return pd.DataFrame()
    
    def _validate_news(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and normalize using NewsEngine"""
        if df.empty:
            return df
        
        validated_rows = []
        
        for _, row in df.iterrows():
            # NewsEngine.validate_timestamp() ensures UTC timezone
            timestamp = self.news_engine.validate_timestamp(row.get('timestamp'))
            
            if timestamp is None:
                logger.warning(f"Invalid timestamp, skipping: {row.get('title', 'Unknown')[:50]}")
                continue
            
            # Build standardized item
            item = {
                'timestamp': timestamp,
                'title': str(row.get('title', '')).strip(),
                'description': str(row.get('description', '')).strip(),
                'link': str(row.get('link', '')).strip(),
                'source': str(row.get('source', 'unknown')).strip(),
                'category': row.get('category', 'general'),
                'author': row.get('author', ''),
                'image_url': row.get('image_url', ''),
                'tags': row.get('tags', ''),
                'cryptos_mentioned': row.get('cryptos_mentioned', ''),
                'tickers_mentioned': row.get('tickers_mentioned', '')
            }
            
            # Skip if missing required fields
            if not item['title'] or not item['source']:
                continue
            
            validated_rows.append(item)
        
        return pd.DataFrame(validated_rows)
    
    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Deduplicate by content_hash"""
        if df.empty:
            return df
        
        # Generate content_hash (same as NewsEngine logic)
        df['content_hash'] = df.apply(
            lambda row: hashlib.md5(
                (row['title'] + row['source'] + str(row['timestamp'])).encode()
            ).hexdigest(),
            axis=1
        )
        
        # Check existing hashes in database
        existing_query = """
        SELECT DISTINCT content_hash 
        FROM news_raw
        """
        
        try:
            existing = self.db.query(existing_query)
            existing_hashes = set(existing['content_hash'].tolist()) if not existing.empty else set()
            
            # Filter out existing
            df = df[~df['content_hash'].isin(existing_hashes)]
            
        except Exception as e:
            logger.warning(f"Could not check existing hashes: {e}")
        
        # Also deduplicate within current batch
        df = df.drop_duplicates(subset=['content_hash'], keep='first')
        
        return df
    
    def _extract_symbols(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract stock/crypto symbols mentioned in title/description"""
        if df.empty:
            return df
        
        # Simple symbol extraction (can be enhanced with symbol_reference.py)
        import re
        
        def extract_tickers(text):
            """Extract $SYMBOL or SYMBOL: patterns"""
            if not text:
                return ''
            
            # Match $AAPL, AAPL:, etc.
            pattern = r'\$([A-Z]{1,5})\b|([A-Z]{2,5}):'
            matches = re.findall(pattern, text)
            
            # Flatten matches
            symbols = [m[0] or m[1] for m in matches if m[0] or m[1]]
            
            return ','.join(list(set(symbols)))
        
        # Extract from title + description
        df['text'] = df['title'] + ' ' + df['description']
        df['tickers_mentioned'] = df['text'].apply(extract_tickers)
        df = df.drop('text', axis=1)
        
        return df
    
    def _save_to_database(self, df: pd.DataFrame):
        """Save to news_raw table with status='pending'"""
        if df.empty:
            logger.info("No new items to save")
            return
        
        # Add pipeline metadata
        df['status'] = 'pending'
        df['collected_at'] = datetime.now()
        
        # Generate unique ID
        df['id'] = df.apply(
            lambda row: f"news_{row['source']}_{row['content_hash'][:8]}",
            axis=1
        )
        
        # Reorder columns
        columns = [
            'id', 'timestamp', 'title', 'description', 'link', 'source',
            'category', 'author', 'image_url', 'tags',
            'tickers_mentioned', 'cryptos_mentioned',
            'content_hash', 'status', 'collected_at'
        ]
        
        # Ensure all columns exist
        for col in columns:
            if col not in df.columns:
                df[col] = ''
        
        df = df[columns]
        
        # Save to database
        try:
            self.db.save_dataframe(df, 'news_raw', mode='append')
            logger.info(f"Saved {len(df)} items to news_raw")
        except Exception as e:
            logger.error(f"Database save error: {e}")


def main():
    """Test execution"""
    # Example watchlist
    watchlist = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'BTCUSD', 'ETHUSD']
    
    pipeline = NewsCollectorPipeline(symbols_watchlist=watchlist)
    pipeline.run(lookback_hours=24)


if __name__ == '__main__':
    main()
